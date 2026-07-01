/**
 * Static snapshot data layer.
 *
 * Serves the same shapes as the live API from precomputed JSON files written by
 * server/export_snapshots.py into public/snapshots/. Used when isStaticMode()
 * (GitHub Pages, or VITE_DATA_MODE=static). Only the methods the pages actually
 * call are implemented.
 *
 * Known degradations vs the live API, by design:
 * - Search covers only the snapshotted top-N entities.
 * - getSourceHistoricalSentiment returns country-level aggregates (the no-filter
 *   branch of the live endpoint); a countries filter selects among those rather
 *   than expanding to per-source series.
 * - days values are clamped to the nearest snapshotted range.
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

export const staticData = {
  getEntities: async (params: any = {}) => {
    const entities = await load('entities.json');
    let result = entities;
    if (params.entity_type) result = result.filter((e: any) => e.type === params.entity_type);
    if (params.search) {
      const q = String(params.search).toLowerCase();
      result = result.filter((e: any) => e.name.toLowerCase().includes(q));
    }
    return result.slice(0, params.limit ?? 100);
  },

  searchEntities: async (query: string, limit: number = 15) => {
    const q = query.toLowerCase();
    const entities = await load('entities.json');
    return entities
      .filter((e: any) => e.name.toLowerCase().includes(q))
      .slice(0, limit);
  },

  getSources: async () => load('sources.json'),

  getEntityDistribution: async (id: number) =>
    (await entityBundle(id)).distribution,

  getHistoricalSentiment: async (entityId: number, params: any = {}) => {
    const days = nearestDays(params.days ?? 30, HIST_DAYS);
    return (await entityBundle(entityId)).historical[String(days)];
  },

  getSourceHistoricalSentiment: async (entityId: number, params: any = {}) => {
    const days = nearestDays(params.days ?? 30, HIST_DAYS);
    const data = (await entityBundle(entityId)).source_historical[String(days)];
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
};
