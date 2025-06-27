import axios from 'axios';
import { config, isGitHubPages, checkApiAvailability } from './config/environment';

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

// Check API availability on startup for GitHub Pages
if (isGitHubPages()) {
  checkApiAvailability(config.apiBaseUrl).then((available) => {
    apiAvailable = available;
    if (!available) {
      console.warn('⚠️ API not available - running in offline mode with mock data');
    }
  });
}

// Request interceptor for handling offline mode
api.interceptors.request.use(
  (config) => {
    if (isGitHubPages() && !apiAvailable) {
      // For GitHub Pages without API, we'll handle this in individual methods
      console.debug('🔌 API unavailable, will use mock data');
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

// Mock data for offline/GitHub Pages mode
const mockData = {
  entities: [
    { id: 1, name: "Joe Biden", type: "PERSON", mention_count: 1250 },
    { id: 2, name: "Donald Trump", type: "PERSON", mention_count: 980 },
    { id: 3, name: "United States", type: "GPE", mention_count: 2100 },
    { id: 4, name: "China", type: "GPE", mention_count: 890 },
    { id: 5, name: "Russia", type: "GPE", mention_count: 760 },
  ],
  sources: [
    { id: 1, name: "BBC", country: "United Kingdom", language: "en" },
    { id: 2, name: "CNN", country: "United States", language: "en" },
    { id: 3, name: "Al Jazeera", country: "Qatar", language: "en" },
    { id: 4, name: "Reuters", country: "United Kingdom", language: "en" },
  ],
};

// Helper function to check if we should use mock data
const shouldUseMockData = () => isGitHubPages() && !apiAvailable;

// Entity API methods
export const entityApi = {
  // Get list of entities
  getEntities: async (params = {}) => {
    if (shouldUseMockData()) {
      // Return mock data for GitHub Pages
      await new Promise(resolve => setTimeout(resolve, 300)); // Simulate network delay
      return mockData.entities;
    }
    
    const response = await api.get('/entities', { params });
    return response.data;
  },
  
  // Get entity details by ID
  getEntity: async (id: number) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 200));
      const entity = mockData.entities.find(e => e.id === id);
      if (!entity) throw new Error('Entity not found');
      return {
        ...entity,
        sentiment: { power_score: 0.2, moral_score: 0.1 },
        top_sources: mockData.sources.slice(0, 3)
      };
    }
    
    const response = await api.get(`/entities/${id}`);
    return response.data;
  },
  
  // Get entity sentiment data
  getEntitySentiment: async (id: number) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 200));
      // Generate mock sentiment data
      const mockSentimentData = Array.from({ length: 30 }, (_, i) => ({
        date: new Date(Date.now() - i * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        power_score: Math.random() * 0.6 - 0.3,
        moral_score: Math.random() * 0.6 - 0.3,
        source: mockData.sources[Math.floor(Math.random() * mockData.sources.length)].name
      }));
      return mockSentimentData;
    }
    
    const response = await api.get(`/entities/${id}/sentiment`);
    return response.data;
  },
  
  // Get entity sentiment distribution
  getEntityDistribution: async (id: number, country?: string, sourceId?: number) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 250));
      // Generate mock distribution data
      return {
        entity: mockData.entities.find(e => e.id === id),
        distributions: {
          global: {
            power: { mean: 0.1, std: 0.2, count: 100 },
            moral: { mean: 0.05, std: 0.15, count: 100 }
          }
        }
      };
    }
    
    let url = `/stats/entity_distribution/${id}`;
    const params: any = {};
    
    if (country) params.country = country;
    if (sourceId) params.source_id = sourceId;
    
    const response = await api.get(url, { params });
    return response.data;
  },
  
  // Get sources that mention an entity
  getEntitySources: async (id: number) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 150));
      return mockData.sources;
    }
    
    const response = await api.get(`/entities/${id}/sources`);
    return response.data;
  },

  // Search entities with autocomplete
  searchEntities: async (query: string, limit: number = 15) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 200));
      // Filter mock entities by query
      const filtered = mockData.entities.filter(entity =>
        entity.name.toLowerCase().includes(query.toLowerCase())
      ).slice(0, limit);
      return filtered;
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
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 200));
      return mockData.sources;
    }
    
    const response = await api.get('/sources', { params });
    return response.data;
  },
  
  // Get source details by ID
  getSource: async (id: number) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 150));
      const source = mockData.sources.find(s => s.id === id);
      if (!source) throw new Error('Source not found');
      return {
        ...source,
        article_count: Math.floor(Math.random() * 1000) + 100,
        sentiment: { power_score: Math.random() * 0.4 - 0.2, moral_score: Math.random() * 0.4 - 0.2 },
        top_entities: mockData.entities.slice(0, 5)
      };
    }
    
    const response = await api.get(`/sources/${id}`);
    return response.data;
  },
  
  // Get source sentiment data
  getSourceSentiment: async (id: number) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 200));
      // Generate mock time series data
      return Array.from({ length: 30 }, (_, i) => ({
        date: new Date(Date.now() - i * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        power_score: Math.random() * 0.6 - 0.3,
        moral_score: Math.random() * 0.6 - 0.3
      }));
    }
    
    const response = await api.get(`/sources/${id}/sentiment`);
    return response.data;
  }
};

// Stats API methods
export const statsApi = {
  // Get bias distribution data
  getBiasDistribution: async (country?: string) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 300));
      // Generate mock bias distribution data
      return {
        country: country || 'Global',
        distributions: Array.from({ length: 50 }, (_, i) => ({
          value: (i - 25) / 25, // Range from -1 to 1
          frequency: Math.exp(-Math.pow((i - 25) / 10, 2)) // Normal-ish distribution
        }))
      };
    }
    
    const params = country ? { country } : {};
    const response = await api.get('/stats/bias_distribution', { params });
    return response.data;
  },
  
  // Get historical sentiment data
  getHistoricalSentiment: async (entityId: number, params = {}) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 250));
      const entity = mockData.entities.find(e => e.id === entityId);
      return {
        entity: entity || { id: entityId, name: 'Unknown Entity', type: 'UNKNOWN' },
        date_range: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          end: new Date().toISOString().split('T')[0],
          days: 30
        },
        daily_data: Array.from({ length: 30 }, (_, i) => ({
          date: new Date(Date.now() - i * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          power_score: Math.random() * 0.6 - 0.3,
          moral_score: Math.random() * 0.6 - 0.3,
          mention_count: Math.floor(Math.random() * 20) + 1
        })),
        summary: {
          avg_power_score: Math.random() * 0.4 - 0.2,
          avg_moral_score: Math.random() * 0.4 - 0.2,
          total_mentions: Math.floor(Math.random() * 500) + 100
        }
      };
    }
    
    const response = await api.get(`/stats/historical_sentiment?entity_id=${entityId}`, { params });
    return response.data;
  },
  
  // Get source-specific historical sentiment data
  getSourceHistoricalSentiment: async (entityId: number, params: any = {}) => {
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 300));
      const entity = mockData.entities.find(e => e.id === entityId);
      const countries = params.countries || ['United States', 'United Kingdom', 'Qatar'];
      
      return {
        entity: entity || { id: entityId, name: 'Unknown Entity', type: 'UNKNOWN' },
        date_range: {
          start: new Date(Date.now() - (params.days || 30) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          end: new Date().toISOString().split('T')[0],
          days: params.days || 30
        },
        sources: countries.map(country => {
          const source = mockData.sources.find(s => s.country === country);
          return {
            source_name: source?.name || `Source from ${country}`,
            country: country,
            data: Array.from({ length: params.days || 30 }, (_, i) => ({
              date: new Date(Date.now() - i * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
              power_score: Math.random() * 0.6 - 0.3,
              moral_score: Math.random() * 0.6 - 0.3,
              mention_count: Math.floor(Math.random() * 10) + 1
            }))
          };
        })
      };
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
    if (shouldUseMockData()) {
      await new Promise(resolve => setTimeout(resolve, 250));
      return {
        country: country,
        date_range: {
          start: new Date(Date.now() - (params.days || 30) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          end: new Date().toISOString().split('T')[0],
          days: params.days || 30
        },
        entities: mockData.entities.slice(0, params.limit || 10).map(entity => ({
          ...entity,
          mention_count: Math.floor(Math.random() * 200) + 50,
          avg_power_score: Math.random() * 0.6 - 0.3,
          avg_moral_score: Math.random() * 0.6 - 0.3
        }))
      };
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
  }
};

// Export the base API instance
export { api };