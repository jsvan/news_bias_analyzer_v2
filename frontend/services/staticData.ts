/**
 * Static snapshot data layer.
 *
 * Serves the same shapes as the live API from precomputed JSON files written by
 * server/export_snapshots.py into public/snapshots/. Used when isStaticMode()
 * (GitHub Pages, or VITE_DATA_MODE=static). Only the methods the pages actually
 * call are implemented.
 *
 * Snapshot format 2: each entity bundle carries ONE timestamped daily series
 * (the base_days=365 API response) for historical and source_historical; the
 * slice* helpers below derive any shorter window from it, reproducing each
 * endpoint's own summary math (mention-weighted mean for the entity summary,
 * unweighted daily mean for per-source summaries). Format-1 bundles (a full
 * copy per window) are still readable for cache-skew resilience.
 *
 * Known degradations vs the live API, by design:
 * - Search covers only the snapshotted top-N entities.
 * - getSourceHistoricalSentiment returns country-level aggregates (the no-filter
 *   branch of the live endpoint); a countries filter selects among those rather
 *   than expanding to per-source series.
 * - entity history windows clamp to base_days; country pages clamp to the
 *   nearest snapshotted range. An all-time request (the falsy ALL_TIME
 *   sentinel, 0) serves the widest window available.
 * - getTrendingEntities serves the all-time snapshot regardless of days, and
 *   returns [] for countries outside the snapshot set (DataContext hides those
 *   from the pickers in static mode) and for newspapers without a per-source
 *   file (meta.trending_sources clamps that picker).
 * - getContestedRanking serves one fixed 30-day moral-dimension snapshot
 *   regardless of days/dimension params; limit slices client-side.
 * - getEntityDistribution assembles national/source layers from baked pieces,
 *   so they exist only where snapshotted: countries with enough scored
 *   mentions, and a paper's own top entities (its source/{id}.json bundle).
 *   Days are ignored (all-time-ish: the snapshot's own window).
 * - getSourceEntityHistory serves the paper bundle's base_days series; papers
 *   without a bundle return [].
 * - getSourceMap / getGlobalAgenda serve one fixed 4-week moral-dimension
 *   snapshot regardless of params (the only shapes the panels request).
 * - getSourceNeighbors is derived client-side from the snapshotted matrix
 *   pairs — same math as the live endpoint, just precomputed data.
 */

// Snapshotted ranges — keep in sync with server/export_snapshots.py.
export const HIST_DAYS = [7, 30, 90, 180, 365];
export const COUNTRY_DAYS = [7, 30, 90];

export function nearestDays(requested: number, available: number[]): number {
  return available.reduce((best, d) =>
    Math.abs(d - requested) < Math.abs(best - requested) ? d : best);
}

const cache = new Map<string, Promise<any>>();

function load(relPath: string): Promise<any> {
  if (!cache.has(relPath)) {
    const url = `${import.meta.env.BASE_URL}snapshots/${relPath}`;
    cache.set(relPath, fetch(url).then((res) => {
      if (!res.ok) {
        cache.delete(relPath);
        throw new Error(`Snapshot not available: ${relPath} (${res.status}). ` +
          'Run server/export_snapshots.py and redeploy.');
      }
      return res.json();
    }));
  }
  return cache.get(relPath)!;
}

const entityBundle = (id: number) => load(`entity/${id}.json`);

// Per-newspaper bundle (source/{id}.json): the paper's top entities with its own
// sentiment PDFs and daily series. Exists for exactly meta.trending_sources.
const sourceBundle = (id: number) => load(`source/${id}.json`);

// Search matches the canonical name OR any merged alias spelling
// (entities.json carries `aliases` for merged groups — e.g. "Zelenskyy"
// finds "Volodymyr Zelensky"), mirroring the live API's tiered search.
// Accent-insensitive so "erdogan" finds "Recep Tayyip Erdoğan" and "jose"
// finds "José Mourinho" — canonical names carry curated diacritics that
// nobody types into a search box.
const fold = (s: string) =>
  s.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '');

function entityMatches(e: any, q: string): boolean {
  const needle = fold(q);
  if (fold(e.name).includes(needle)) return true;
  return (e.aliases ?? []).some((a: string) => fold(a).includes(needle));
}

// ---- Window slicing (snapshot format 2) ------------------------------------
// The base response's daily rows are date-stamped (YYYY-MM-DD, so string
// comparison is chronological); a shorter window is just the rows on or after
// its start date, with the summary recomputed the way the live endpoint does.

function windowStart(endIso: string, days: number): string {
  const end = new Date(`${endIso}T00:00:00Z`);
  end.setUTCDate(end.getUTCDate() - days);
  return end.toISOString().slice(0, 10);
}

function sliceHistorical(base: any, days: number) {
  const start = windowStart(base.date_range.end, days);
  const daily = base.daily_data.filter((r: any) => r.date >= start);
  const mentions = daily.reduce((s: number, r: any) => s + r.mention_count, 0);
  // Mention-weighted: matches the live endpoint's AVG over individual mentions.
  const wavg = (k: string) => mentions
    ? daily.reduce((s: number, r: any) => s + r[k] * r.mention_count, 0) / mentions
    : 0;
  return {
    ...base,
    date_range: { start, end: base.date_range.end, days },
    daily_data: daily,
    summary: {
      avg_power_score: wavg('power_score'),
      avg_moral_score: wavg('moral_score'),
      total_mentions: mentions,
    },
  };
}

function sliceSourceHistorical(base: any, days: number) {
  const start = windowStart(base.date_range.end, days);
  const sliced: [string, any][] = [];
  for (const [key, src] of Object.entries<any>(base.sources)) {
    const daily = src.daily_data.filter((r: any) => r.date >= start);
    if (!daily.length) continue;  // source has no data inside this window
    // Unweighted mean of daily values: matches the live endpoint's summary.
    const mean = (k: string) =>
      daily.reduce((s: number, r: any) => s + r[k], 0) / daily.length;
    sliced.push([key, {
      ...src,
      daily_data: daily,
      summary: {
        avg_power_score: mean('power_score'),
        avg_moral_score: mean('moral_score'),
        total_mentions: daily.reduce((s: number, r: any) => s + r.mention_count, 0),
        days_with_data: daily.length,
      },
    }]);
  }
  // The live endpoint orders sources by total mentions within the window.
  sliced.sort((a, b) => b[1].summary.total_mentions - a[1].summary.total_mentions);
  return {
    ...base,
    date_range: { start, end: base.date_range.end, days },
    sources: Object.fromEntries(sliced),
  };
}

export const staticData = {
  getMeta: async () => load('meta.json'),

  getEntities: async (params: any = {}) => {
    const entities = await load('entities.json');
    let result = entities;
    if (params.entity_type) result = result.filter((e: any) => e.type === params.entity_type);
    if (params.search) {
      const q = String(params.search).toLowerCase();
      result = result.filter((e: any) => entityMatches(e, q));
    }
    return result.slice(0, params.limit ?? 100);
  },

  searchEntities: async (query: string, limit: number = 15) => {
    const q = query.toLowerCase();
    const entities = await load('entities.json');
    return entities
      .filter((e: any) => entityMatches(e, q))
      .slice(0, limit);
  },

  getSources: async () => load('sources.json'),

  getTrendingEntities: async (limit: number = 25, _days?: number, country?: string, sourceId?: number) => {
    try {
      // Per-source files only exist for papers with enough data
      // (meta.trending_sources is the authoritative list).
      const rel = sourceId
        ? `stats/trending_source_${sourceId}.json`
        : country ? `stats/trending_${country}.json` : 'stats/trending_global.json';
      const rows = await load(rel);
      return rows.slice(0, limit);
    } catch {
      // Non-snapshotted country/source, or a pre-trending snapshot still cached.
      return [];
    }
  },

  // "The front line" panel. The exporter writes the endpoint's response shape
  // for the one parameterization the panel requests (30 days, moral).
  getContestedRanking: async (params: any = {}) => {
    const data = await load('stats/contested.json');
    return { ...data, entities: (data.entities ?? []).slice(0, params.limit ?? 20) };
  },

  // Source Space page: the stored weekly similarity matrix (constellations),
  // the MDS source map, and the shared international agenda.
  getSimilarityMatrix: async () => load('stats/similarity_matrix.json'),

  getSourceMap: async () => load('stats/source_map.json'),

  getGlobalAgenda: async (params: any = {}) => {
    const data = await load('stats/global_agenda.json');
    return { ...data, entities: (data.entities ?? []).slice(0, params.limit ?? 100) };
  },

  // Mirrors similarity_endpoints.get_source_neighbors on the snapshotted pairs:
  // rows sorted nearest-first; farthest only when there are more rows than the
  // limit (same guard as the live endpoint).
  getSourceNeighbors: async (sourceId: number, limit: number = 5) => {
    const m = await load('stats/similarity_matrix.json');
    const bySource = new Map<number, any>(
      (m.sources ?? []).map((s: any) => [s.source_id, s]));
    const rows = (m.pairs ?? [])
      .filter((p: any) => p.source_id_1 === sourceId || p.source_id_2 === sourceId)
      .map((p: any) => {
        const otherId = p.source_id_1 === sourceId ? p.source_id_2 : p.source_id_1;
        const other = bySource.get(otherId);
        return {
          source_id: otherId,
          name: other?.name ?? String(otherId),
          country: other?.country ?? null,
          score: p.score,
          common_entities: p.common_entities,
        };
      })
      .sort((a: any, b: any) => b.score - a.score);
    return {
      source_id: sourceId,
      source_name: bySource.get(sourceId)?.name ?? String(sourceId),
      window_start: m.window_start ?? null,
      window_end: m.window_end ?? null,
      nearest: rows.slice(0, limit),
      farthest: rows.length > limit ? rows.slice(-limit).reverse() : [],
    };
  },

  // Assembles the live endpoint's layered shape from bundle pieces: global from
  // the entity bundle, national from its baked per-country layers, source from
  // that paper's own bundle. A layer that wasn't snapshotted (thin country
  // coverage, entity outside the paper's top set) is simply absent — the same
  // contract as the live endpoint returning no layer for no data.
  getEntityDistribution: async (id: number, country?: string, sourceId?: number) => {
    const bundle = await entityBundle(id);
    const base = bundle.distribution;
    const distributions: any = { ...(base?.distributions ?? {}) };
    if (country && bundle.national_distributions?.[country]) {
      distributions.national = bundle.national_distributions[country];
    }
    if (sourceId) {
      try {
        const sb = await sourceBundle(sourceId);
        const ent = (sb.entities ?? []).find((e: any) => e.id === id);
        if (ent?.distribution) distributions.source = ent.distribution;
      } catch {
        // paper not snapshotted — no source layer
      }
    }
    return { ...base, distributions };
  },

  // One paper's daily series for one entity, from its bundle. [] when the paper
  // isn't snapshotted or the entity isn't among its baked top entities.
  getSourceEntityHistory: async (sourceId: number, entityId: number) => {
    try {
      const sb = await sourceBundle(sourceId);
      return sb.entities?.find((e: any) => e.id === entityId)?.daily ?? [];
    } catch {
      return [];
    }
  },

  getHistoricalSentiment: async (entityId: number, params: any = {}) => {
    const bundle = await entityBundle(entityId);
    // The ALL_TIME sentinel (0) is falsy BY DESIGN: the live path's
    // `if (params.days)` guards omit the param and the backend returns
    // everything. Here "everything" is the widest snapshotted window — a
    // plain `?? 30` would let 0 through as a zero-day slice (one row, and
    // the trend chart shows "not enough data" for every entity).
    const days = params.days || Math.max(...HIST_DAYS);
    if (bundle.format >= 2) {
      return sliceHistorical(bundle.historical, Math.min(days, bundle.base_days));
    }
    return bundle.historical[String(nearestDays(days, HIST_DAYS))];
  },

  getSourceHistoricalSentiment: async (entityId: number, params: any = {}) => {
    const bundle = await entityBundle(entityId);
    // ALL_TIME (0) = widest window, as in getHistoricalSentiment above.
    const days = params.days || Math.max(...HIST_DAYS);
    const data = bundle.format >= 2
      ? sliceSourceHistorical(bundle.source_historical,
          Math.min(days, bundle.base_days))
      : bundle.source_historical[String(nearestDays(days, HIST_DAYS))];
    if (params.countries?.length) {
      const wanted = new Set(params.countries);
      const sources: Record<string, any> = {};
      for (const [key, value] of Object.entries<any>(data.sources)) {
        if (wanted.has(value.country)) sources[key] = value;
      }
      return { ...data, countries_filter: params.countries, sources };
    }
    return data;
  },

  getCountryTopEntities: async (country: string, params: any = {}) => {
    // ALL_TIME (0) maps to the widest snapshotted window, not nearest-to-zero.
    const days = nearestDays(params.days || Math.max(...COUNTRY_DAYS), COUNTRY_DAYS);
    return load(`country/${country}_${days}.json`);
  },

  // Derived from the country snapshot's per-entity `newspapers` breakdown —
  // there's no separate per-newspaper snapshot file, so this filters/reshapes
  // the country data we already have rather than requiring a new export.
  getNewspaperTopEntities: async (newspaperName: string, params: any = {}) => {
    const sources = await load('sources.json');
    const source = sources.find((s: any) => s.name === newspaperName);
    const country = source?.country ?? 'Unknown';
    const days = nearestDays(params.days || Math.max(...COUNTRY_DAYS), COUNTRY_DAYS);
    const countryData = await load(`country/${country}_${days}.json`);

    const entities = (countryData.entities ?? [])
      .filter((e: any) => e.newspapers?.[newspaperName]?.length)
      .map((e: any) => {
        const trends = e.newspapers[newspaperName];
        return {
          entity_name: e.entity_name,
          entity_type: e.entity_type,
          mention_count: trends.reduce((s: number, t: any) => s + t.mention_count, 0),
          avg_power_score: trends.reduce((s: number, t: any) => s + t.power_score, 0) / trends.length,
          avg_moral_score: trends.reduce((s: number, t: any) => s + t.moral_score, 0) / trends.length,
          newspapers: { [newspaperName]: trends },
        };
      })
      .sort((a: any, b: any) => b.mention_count - a.mention_count)
      .slice(0, params.limit ?? 10);

    return { newspaper_name: newspaperName, country, entities, time_period_days: days };
  },
};
