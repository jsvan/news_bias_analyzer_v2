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

// No mock data - this system requires real analysis for accuracy

// Helper function to check if API is unavailable (no fallback data for accuracy)
const isApiUnavailable = () => isGitHubPages() && !apiAvailable;

// Entity API methods
export const entityApi = {
  // Get list of entities
  getEntities: async (params = {}) => {
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
  
  // Get entity sentiment distribution
  getEntityDistribution: async (id: number, country?: string, sourceId?: number) => {
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real distribution data.');
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
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real source data.');
    }
    
    const response = await api.get(`/entities/${id}/sources`);
    return response.data;
  },

  // Search entities with autocomplete
  searchEntities: async (query: string, limit: number = 15) => {
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
  
  // Get historical sentiment data
  getHistoricalSentiment: async (entityId: number, params = {}) => {
    if (isApiUnavailable()) {
      throw new Error('API unavailable: Please run the backend server to access real historical sentiment data.');
    }
    
    const response = await api.get(`/stats/historical_sentiment?entity_id=${entityId}`, { params });
    return response.data;
  },
  
  // Get source-specific historical sentiment data
  getSourceHistoricalSentiment: async (entityId: number, params: any = {}) => {
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
  }
};

// Export the base API instance
export { api };