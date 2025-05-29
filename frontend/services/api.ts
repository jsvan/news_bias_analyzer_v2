import axios from 'axios';

// Create axios instance for backend API
const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000
});

// Entity API methods
export const entityApi = {
  // Get list of entities
  getEntities: async (params = {}) => {
    const response = await api.get('/entities', { params });
    return response.data;
  },
  
  // Get entity details by ID
  getEntity: async (id: number) => {
    const response = await api.get(`/entities/${id}`);
    return response.data;
  },
  
  // Get entity sentiment data
  getEntitySentiment: async (id: number) => {
    const response = await api.get(`/entities/${id}/sentiment`);
    return response.data;
  },
  
  // Get entity sentiment distribution
  getEntityDistribution: async (id: number, country?: string, sourceId?: number) => {
    let url = `/stats/entity_distribution/${id}`;
    const params: any = {};
    
    if (country) params.country = country;
    if (sourceId) params.source_id = sourceId;
    
    const response = await api.get(url, { params });
    return response.data;
  },
  
  // Get sources that mention an entity
  getEntitySources: async (id: number) => {
    const response = await api.get(`/entities/${id}/sources`);
    return response.data;
  }
};

// News Sources API methods
export const sourcesApi = {
  // Get list of news sources
  getSources: async (params = {}) => {
    const response = await api.get('/sources', { params });
    return response.data;
  },
  
  // Get source details by ID
  getSource: async (id: number) => {
    const response = await api.get(`/sources/${id}`);
    return response.data;
  },
  
  // Get source sentiment data
  getSourceSentiment: async (id: number) => {
    const response = await api.get(`/sources/${id}/sentiment`);
    return response.data;
  }
};

// Stats API methods
export const statsApi = {
  // Get bias distribution data
  getBiasDistribution: async (country?: string) => {
    const params = country ? { country } : {};
    const response = await api.get('/stats/bias_distribution', { params });
    return response.data;
  },
  
  // Get historical sentiment data
  getHistoricalSentiment: async (entityId: number, params = {}) => {
    const response = await api.get(`/stats/historical_sentiment?entity_id=${entityId}`, { params });
    return response.data;
  },
  
  // Get source-specific historical sentiment data
  getSourceHistoricalSentiment: async (entityId: number, params: any = {}) => {
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
  }
};

// Export the base API instance
export { api };