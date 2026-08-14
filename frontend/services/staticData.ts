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
 *   nearest snapshotted range.
 * - getTrendingEntities serves the all-time snapshot regardless of days, and
 *   returns [] for countries outside the snapshot set (DataContext hides those
 *   from the pickers in static mode) and for newspapers without a per-source
 *   file (meta.trending_sources clamps that picker).
 * - getContestedRanking serves one fixed 30-day moral-dimension snapshot
 *   regardless of days/dimension params; limit slices client-side.
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

  getEntityDistribution: async (id: number) =>
    (await entityBundle(id)).distribution,

  getHistoricalSentiment: async (entityId: number, params: any = {}) => {
    const bundle = await entityBundle(entityId);
    if (bundle.format >= 2) {
      const days = Math.min(params.days ?? 30, bundle.base_days);
      return sliceHistorical(bundle.historical, days);
    }
    return bundle.historical[String(nearestDays(params.days ?? 30, HIST_DAYS))];
  },

  getSourceHistoricalSentiment: async (entityId: number, params: any = {}) => {
    const bundle = await entityBundle(entityId);
    const data = bundle.format >= 2
      ? sliceSourceHistorical(bundle.source_historical,
          Math.min(params.days ?? 30, bundle.base_days))
      : bundle.source_historical[String(nearestDays(params.days ?? 30, HIST_DAYS))];
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
    const days = nearestDays(params.days ?? 30, COUNTRY_DAYS);
    return load(`country/${country}_${days}.json`);
  },

  // Derived from the country snapshot's per-entity `newspapers` breakdown —
  // there's no separate per-newspaper snapshot file, so this filters/reshapes
  // the country data we already have rather than requiring a new export.
  getNewspaperTopEntities: async (newspaperName: string, params: any = {}) => {
    const sources = await load('sources.json');
    const source = sources.find((s: any) => s.name === newspaperName);
    const country = source?.country ?? 'Unknown';
    const days = nearestDays(params.days ?? 30, COUNTRY_DAYS);
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
