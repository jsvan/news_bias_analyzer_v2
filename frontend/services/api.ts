import axios from 'axios';
import { config, isGitHubPages, isStaticMode, checkApiAvailability } from './config/environment';
import { staticData } from './staticData';
import { SnapshotMeta } from '../types';

// Create axios instance for backend API
const api = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: config.api.timeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API availability state
let apiAvailable = true;

// Check API availability on startup for GitHub Pages (static mode skips the API entirely)
if (isGitHubPages() && !isStaticMode()) {
  checkApiAvailability(config.apiBaseUrl).then((available) => {
    apiAvailable = available;
    if (!available) {
      console.warn('⚠️ API not available - requests will fail with explicit errors (no mock data exists)');
    }
  });
}

// Request interceptor for handling offline mode
api.interceptors.request.use(
  (config) => {
    if (isGitHubPages() && !apiAvailable) {
      // For GitHub Pages without API, individual methods throw explicit errors
      console.debug('🔌 API unavailable');
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling and retries
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Handle network errors or API unavailability
    if (!error.response && !originalRequest._retry && config.api.retryAttempts > 0) {
      originalRequest._retry = true;
      originalRequest._retryCount = (originalRequest._retryCount || 0) + 1;
      
      if (originalRequest._retryCount <= config.api.retryAttempts) {
        console.warn(`🔄 API request failed, retrying... (${originalRequest._retryCount}/${config.api.retryAttempts})`);
        
        // Exponential backoff
        const delay = Math.pow(2, originalRequest._retryCount) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
        
        return api(originalRequest);
      }
    }
    
    // Mark API as unavailable for GitHub Pages
    if (isGitHubPages() && !error.response) {
      apiAvailable = false;
      console.warn('⚠️ API marked as unavailable');
    }
    
    return Promise.reject(error);
  }
);

// No mock data - this system requires real analysis for accuracy

// Helper function to check if API is unavailable (no fallback data for accuracy)
const isApiUnavailable = () => isGitHubPages() && !apiAvailable;

// Entity API methods
export const entityApi = {
  // Get list of entities
  getEntities: async (params = {}) => {
    if (isStaticMode()) return staticData.getEntities(params);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real news analysis data.');
    }

    const response = await api.get('/entities', { params });
    return response.data;
  },
  
  // Get entity details by ID
  getEntity: async (id: number) => {
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real entity data.');
    }
    
    const response = await api.get(`/entities/${id}`);
    return response.data;
  },
  
  // Get entity sentiment data
  getEntitySentiment: async (id: number) => {
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real sentiment data.');
    }
    
    const response = await api.get(`/entities/${id}/sentiment`);
    return response.data;
  },
  
  // Get entity sentiment distribution. `layers` (comma subset of
  // global,national,source) restricts what the backend computes — a
  // single-layer request skips the global KDE entirely, which matters for
  // per-entity gap-fill fan-outs. Static mode assembles layers from bundles.
  getEntityDistribution: async (id: number, country?: string, sourceId?: number, days?: number, layers?: string) => {
    if (isStaticMode()) return staticData.getEntityDistribution(id, country, sourceId);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real distribution data.');
    }

    let url = `/stats/entity_distribution/${id}`;
    const params: any = {};

    if (country) params.country = country;
    if (sourceId) params.source_id = sourceId;
    if (days) params.days = days; // ALL_TIME sentinel (0) omitted = all-time
    if (layers) params.layers = layers;

    const response = await api.get(url, { params });
    return response.data;
  },
  
  // Get sources that mention an entity
  getEntitySources: async (id: number) => {
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real source data.');
    }
    
    const response = await api.get(`/entities/${id}/sources`);
    return response.data;
  },

  // Search entities with autocomplete
  searchEntities: async (query: string, limit: number = 15) => {
    if (isStaticMode()) return staticData.searchEntities(query, limit);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to search real entities.');
    }
    
    const response = await api.get('/entities/search', {
      params: { q: query, limit }
    });
    return response.data;
  }
};

// News Sources API methods
export const sourcesApi = {
  // Get list of news sources
  getSources: async (params = {}) => {
    if (isStaticMode()) return staticData.getSources();
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real news sources.');
    }
    
    const response = await api.get('/sources', { params });
    return response.data;
  },
  
  // Get source details by ID
  getSource: async (id: number) => {
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real source data.');
    }
    
    const response = await api.get(`/sources/${id}`);
    return response.data;
  },
  
  // Get source sentiment data
  getSourceSentiment: async (id: number) => {
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real source sentiment data.');
    }
    
    const response = await api.get(`/sources/${id}/sentiment`);
    return response.data;
  }
};

// Snapshot freshness metadata. Only meaningful in static-snapshot mode (GitHub Pages) -
// a live API connection reflects the current DB by definition, so there's no separate
// "snapshot age" to report; callers should treat a null return as "not applicable, don't
// show a staleness banner" rather than "unknown/stale".
export const metaApi = {
  getMeta: async (): Promise<SnapshotMeta | null> => {
    if (isStaticMode()) return staticData.getMeta();
    return null;
  },
};

// Stats API methods
export const statsApi = {
  // Get bias distribution data
  getBiasDistribution: async (country?: string) => {
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real bias distribution data.');
    }
    
    const params = country ? { country } : {};
    const response = await api.get('/stats/bias_distribution', { params });
    return response.data;
  },
  
  // Most-mentioned entities with average power/moral scores. days omitted = all time;
  // country omitted = all sources worldwide (the global baseline); sourceId set =
  // one newspaper's reading (the backend requires >=3 mentions per entity there).
  getTrendingEntities: async (limit: number = 25, days?: number, country?: string, sourceId?: number) => {
    if (isStaticMode()) return staticData.getTrendingEntities(limit, days, country, sourceId);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access entity sentiment data.');
    }

    const params: any = { limit };
    if (days) params.days = days;
    if (country) params.country = country;
    if (sourceId) params.source_id = sourceId;
    const response = await api.get('/stats/trending_entities', { params });
    return response.data;
  },

  // Get historical sentiment data
  getHistoricalSentiment: async (entityId: number, params: any = {}) => {
    if (isStaticMode()) return staticData.getHistoricalSentiment(entityId, params);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real historical sentiment data.');
    }

    // ALL_TIME sentinel (0) means no day filter — omit it or the backend 422s on ge=1
    const query: any = { ...params };
    if (!query.days) delete query.days;
    const response = await api.get(`/stats/historical_sentiment?entity_id=${entityId}`, { params: query });
    return response.data;
  },
  
  // Get source-specific historical sentiment data
  getSourceHistoricalSentiment: async (entityId: number, params: any = {}) => {
    if (isStaticMode()) return staticData.getSourceHistoricalSentiment(entityId, params);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real source historical sentiment data.');
    }
    
    // Build the URL with proper query parameters
    let url = `/stats/source_historical_sentiment?entity_id=${entityId}`;
    
    // Add other parameters
    if (params.days) {
      url += `&days=${params.days}`;
    }
    
    // Handle countries array properly for FastAPI
    if (params.countries && Array.isArray(params.countries)) {
      params.countries.forEach((country: string) => {
        url += `&countries=${encodeURIComponent(country)}`;
      });
    }
    
    const response = await api.get(url);
    return response.data;
  },

  // Get top entities for a specific country
  getCountryTopEntities: async (country: string, params: any = {}) => {
    if (isStaticMode()) return staticData.getCountryTopEntities(country, params);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real country entity data.');
    }
    
    let url = `/stats/country/${encodeURIComponent(country)}/top-entities`;
    
    const queryParams = new URLSearchParams();
    if (params.days) queryParams.append('days', params.days.toString());
    if (params.limit) queryParams.append('limit', params.limit.toString());
    
    if (queryParams.toString()) {
      url += `?${queryParams.toString()}`;
    }
    
    const response = await api.get(url);
    return response.data;
  },

  // One paper's daily sentiment series for one entity. Live: the per-source
  // branch of source_historical_sentiment (countries=[paper's country]) keyed
  // "Name (Country)"; static: the paper's baked bundle. Returns TrendPoint[].
  getSourceEntityHistory: async (
    source: { id: number; name: string; country: string },
    entityId: number,
    params: { days?: number } = {}
  ) => {
    if (isStaticMode()) return staticData.getSourceEntityHistory(source.id, entityId);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real source historical sentiment data.');
    }

    let url = `/stats/source_historical_sentiment?entity_id=${entityId}`;
    if (params.days) url += `&days=${params.days}`; // ALL_TIME sentinel (0) omitted
    url += `&countries=${encodeURIComponent(source.country)}`;
    const response = await api.get(url);
    return response.data?.sources?.[`${source.name} (${source.country})`]?.daily_data ?? [];
  },

  // Get top entities for a specific newspaper
  getNewspaperTopEntities: async (newspaperName: string, params: any = {}) => {
    if (isStaticMode()) return staticData.getNewspaperTopEntities(newspaperName, params);
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real newspaper entity data.');
    }
    
    let url = `/stats/newspaper/${encodeURIComponent(newspaperName)}/top-entities`;
    
    const queryParams = new URLSearchParams();
    if (params.days) queryParams.append('days', params.days.toString());
    if (params.limit) queryParams.append('limit', params.limit.toString());
    
    if (queryParams.toString()) {
      url += `?${queryParams.toString()}`;
    }
    
    const response = await api.get(url);
    return response.data;
  }
};

// Narrative statistics (server/routers/narrative_endpoints.py) - wires
// analyzer/narrative_metrics.py's kernels into real cross-source queries. The contested
// ranking, source map, and global agenda are part of the static-snapshot export
// (server/export_snapshots.py); the rest is live-API only for now.
export const narrativeApi = {
  getContestedRanking: async (params: { days?: number; dimension?: 'power' | 'moral'; limit?: number } = {}) => {
    if (isStaticMode()) return staticData.getContestedRanking(params);
    if (isApiUnavailable()) {
      throw new Error('Contested-entity ranking requires a live backend and is not available in this demo.');
    }
    const response = await api.get('/narrative/contested', { params });
    return response.data;
  },
  getArchetype: async (entityId: number, params: { weeks?: number; country?: string } = {}) => {
    if (isStaticMode() || isApiUnavailable()) {
      throw new Error('The archetype trajectory requires a live backend and is not available in this demo.');
    }
    const response = await api.get(`/narrative/archetype/${entityId}`, { params });
    return response.data;
  },
  getSourceMap: async (params: { weeks?: number; dimension?: 'power' | 'moral' } = {}) => {
    if (isStaticMode()) return staticData.getSourceMap();
    if (isApiUnavailable()) {
      throw new Error('The source map requires a live backend and is not available in this demo.');
    }
    const response = await api.get('/narrative/source-map', { params });
    return response.data;
  },
  // Entities ranked by how many countries' sources covered them — the shared
  // international agenda the source map is built on.
  getGlobalAgenda: async (params: { weeks?: number; limit?: number } = {}) => {
    if (isStaticMode()) return staticData.getGlobalAgenda(params);
    if (isApiUnavailable()) {
      throw new Error('The global agenda requires a live backend and is not available in this demo.');
    }
    const response = await api.get('/narrative/global-agenda', { params });
    return response.data;
  },
  getSalienceAsymmetry: async (params: { country_a: string; country_b: string; days?: number; limit?: number }) => {
    if (isStaticMode() || isApiUnavailable()) {
      throw new Error('Salience asymmetry requires a live backend and is not available in this demo.');
    }
    const response = await api.get('/narrative/salience', { params });
    return response.data;
  },
};

// Entity relatedness (server/routers/embeddings_endpoints.py) - nearest neighbors from
// analyzer/entity_embeddings.py's weekly learned embeddings. Two independent vectors:
// "cooccurrence" (topical - what gets mentioned alongside) and "sentiment" (rhetorical -
// what gets talked about the same way by the same sources). Live-API only for now.
export const embeddingsApi = {
  getRelated: async (entityId: number, params: { vector?: 'cooccurrence' | 'sentiment'; limit?: number } = {}) => {
    if (isStaticMode() || isApiUnavailable()) {
      throw new Error('Related-entity lookups require a live backend and are not available in this demo.');
    }
    const response = await api.get(`/narrative/related/${entityId}`, { params });
    return response.data;
  },
};

// Statistical surprise / drift detection (server/routers/drift_endpoints.py) - wires
// analyzer/narrative_metrics.py::pettitt_test into real changepoint queries. Distinguishes
// a GLOBAL shift (everyone moved together, an expected real-world event) from a
// SOURCE-specific residual shift (this source moved alone, unexplained by the global
// trend - the actually-interesting editorial-stance signal). Live-API only for now.
export const driftApi = {
  getEntityDrift: async (entityId: number, params: { dimension?: 'power' | 'moral' } = {}) => {
    if (isStaticMode() || isApiUnavailable()) {
      throw new Error('Drift detection requires a live backend and is not available in this demo.');
    }
    const response = await api.get(`/narrative/drift/${entityId}`, { params });
    return response.data;
  },
  getDriftFeed: async (params: { dimension?: 'power' | 'moral'; limit?: number; scope?: 'all' | 'global' | 'source' } = {}) => {
    if (isStaticMode() || isApiUnavailable()) {
      throw new Error('Drift feed requires a live backend and is not available in this demo.');
    }
    const response = await api.get('/narrative/drift-feed', { params });
    return response.data;
  },
};

// Source similarity (server/routers/similarity_endpoints.py) - the weekly Pearson
// matrix over common entities (analyzer/source_similarity.py kernels, computed by
// clustering/source_similarity.py) plus cluster assignments and per-source
// nearest/farthest neighbors. The MDS source map draws these same correlations in
// 2D. Snapshotted for static mode; neighbors are derived from the matrix pairs
// client-side there.
export const similarityApi = {
  getMatrix: async () => {
    if (isStaticMode()) return staticData.getSimilarityMatrix();
    if (isApiUnavailable()) {
      throw new Error('The source-similarity matrix requires a live backend and is not available in this demo.');
    }
    const response = await api.get('/similarity/matrix');
    return response.data;
  },
  getSourceNeighbors: async (sourceId: number, params: { limit?: number } = {}) => {
    if (isStaticMode()) return staticData.getSourceNeighbors(sourceId, params.limit ?? 5);
    if (isApiUnavailable()) {
      throw new Error('Source neighbors require a live backend and are not available in this demo.');
    }
    const response = await api.get(`/similarity/sources/${sourceId}/neighbors`, { params });
    return response.data;
  },
};

// Export the base API instance
export { api };