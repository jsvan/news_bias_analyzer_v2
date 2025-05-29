// API Service Layer - Centralized API communication
import { CONFIG } from '../config.js';

export class ApiService {
  constructor() {
    this.baseUrl = CONFIG.API_ENDPOINT;
  }

  // Health check endpoint
  async checkHealth() {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return { ok: response.ok, status: response.status };
    } catch (error) {
      return { ok: false, error: error.message };
    }
  }

  // Article analysis endpoints
  async analyzeArticle(articleData, forceReanalysis = false) {
    const payload = {
      url: articleData.url,
      source: articleData.source,
      title: articleData.title,
      text: articleData.text,
      force_reanalysis: forceReanalysis
    };

    const response = await fetch(`${this.baseUrl}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Analysis failed: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  }

  async getAnalysisByUrl(url) {
    const response = await fetch(`${this.baseUrl}/analysis/by-url?url=${encodeURIComponent(url)}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get analysis: ${response.status}`);
    }

    return await response.json();
  }

  // Content extraction
  async extractContent(url) {
    const response = await fetch(`${this.baseUrl}/extract`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url })
    });

    if (!response.ok) {
      const errorMessages = {
        500: "Content extraction failed: Server error (500). Make sure trafilatura is installed on the server.",
        404: "Content extraction failed: API endpoint not found (404).",
        401: "Content extraction failed: Unauthorized (401).",
        403: "Content extraction failed: Forbidden (403).",
        429: "Content extraction failed: Too many requests (429)."
      };

      const errorMessage = errorMessages[response.status] ||
        `Content extraction failed with status ${response.status}`;

      throw new Error(errorMessage);
    }

    return await response.json();
  }

  // Statistics endpoints
  async getSentimentDistribution(entityName, dimension, country = null) {
    let url = `${this.baseUrl}/stats/sentiment/distribution?entity_name=${encodeURIComponent(entityName)}&dimension=${dimension}`;
    if (country) {
      url += `&country=${encodeURIComponent(country)}`;
    }

    const response = await fetch(url);
    
    if (!response.ok) {
      if (response.status === 400) {
        throw new Error('INSUFFICIENT_DATA');
      }
      throw new Error(`Failed to get sentiment distribution: ${response.status}`);
    }

    return await response.json();
  }

  async getAvailableCountries(entityName, dimension) {
    const url = `${this.baseUrl}/stats/entity/available-countries?entity_name=${encodeURIComponent(entityName)}&dimension=${dimension}`;
    
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`Failed to get available countries: ${response.status}`);
    }

    return await response.json();
  }

  async getGlobalEntityCounts() {
    const response = await fetch(`${this.baseUrl}/stats/entity/global-counts`);
    
    if (!response.ok) {
      throw new Error(`Failed to get global counts: ${response.status}`);
    }

    return await response.json();
  }

  async getEntityTracking(entityName, days, windowSize = 7, sourceId = null) {
    let url = `${this.baseUrl}/stats/entity/tracking?entity_name=${encodeURIComponent(entityName)}&days=${days}&window_size=${windowSize}`;
    if (sourceId) {
      url += `&source_id=${sourceId}`;
    }

    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`Failed to get entity tracking: ${response.status}`);
    }

    return await response.json();
  }

  // Similar articles endpoint
  async getSimilarArticles(articleId, options = {}) {
    const {
      limit = 10,
      daysWindow = 3,
      minEntityOverlap = 0.3
    } = options;

    const url = `${this.baseUrl}/stats/article/${articleId}/similar?limit=${limit}&days_window=${daysWindow}&min_entity_overlap=${minEntityOverlap}`;
    
    const response = await fetch(url);
    
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('ARTICLE_NOT_FOUND');
      }
      throw new Error(`Failed to get similar articles: ${response.status}`);
    }

    return await response.json();
  }

  // Similarity endpoints
  async getSourceByName(sourceName) {
    // This would be implemented based on your similarity API
    // Placeholder for now
    throw new Error('Source similarity API not yet integrated');
  }

  async getSourceSimilarity(sourceId) {
    // This would be implemented based on your similarity API
    // Placeholder for now
    throw new Error('Source similarity API not yet integrated');
  }

  async getVolatileEntities(limit = 10) {
    // This would be implemented based on your similarity API
    // Placeholder for now
    throw new Error('Volatile entities API not yet integrated');
  }

  async getSourceClusters(country = null) {
    // This would be implemented based on your similarity API
    // Placeholder for now
    throw new Error('Source clusters API not yet integrated');
  }

  // Helper method for consistent error handling
  async _handleResponse(response, context = '') {
    if (!response.ok) {
      const error = new Error(`API request failed: ${response.status} ${response.statusText}`);
      error.status = response.status;
      error.context = context;
      throw error;
    }

    try {
      return await response.json();
    } catch (parseError) {
      throw new Error(`Failed to parse API response: ${parseError.message}`);
    }
  }

  // Request with timeout wrapper
  async _fetchWithTimeout(url, options = {}, timeout = 30000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out');
      }
      throw error;
    }
  }
}