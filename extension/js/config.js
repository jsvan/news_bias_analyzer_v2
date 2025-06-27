// Configuration management for the Chrome extension
// Detects environment and sets appropriate API endpoints

/**
 * Environment detection for Chrome extension
 */
function detectEnvironment() {
  // Check if we're in development (local files or localhost)
  const isDevelopment = location.protocol === 'file:' || 
                       location.hostname === 'localhost' || 
                       location.hostname === '127.0.0.1';
  
  // Check for staging environment (can be set via build process)
  const isStaging = window.EXTENSION_ENV === 'staging';
  
  return isDevelopment ? 'development' : (isStaging ? 'staging' : 'production');
}

/**
 * Get API configuration based on environment
 */
function getApiConfig() {
  const environment = detectEnvironment();
  
  switch (environment) {
    case 'development':
      return {
        API_ENDPOINT: 'http://localhost:8000',
        ENVIRONMENT: 'development'
      };
      
    case 'staging':
      return {
        API_ENDPOINT: 'https://api-staging.news-bias-analyzer.example.com',
        ENVIRONMENT: 'staging'
      };
      
    case 'production':
      return {
        API_ENDPOINT: 'https://api.news-bias-analyzer.example.com',
        ENVIRONMENT: 'production'
      };
      
    default:
      console.warn('Unknown environment, falling back to development');
      return {
        API_ENDPOINT: 'http://localhost:8000',
        ENVIRONMENT: 'development'
      };
  }
}

// Get environment-specific configuration
const apiConfig = getApiConfig();

export const CONFIG = {
  // API Configuration (environment-aware)
  API_ENDPOINT: apiConfig.API_ENDPOINT,
  ENVIRONMENT: apiConfig.ENVIRONMENT,
  
  // Cache settings
  CACHE_TTL: 300000, // 5 minutes
  
  // UI Constants
  MAX_ENTITIES_DISPLAY: 50,
  HISTOGRAM_WIDTH: 320,
  HISTOGRAM_HEIGHT: 200,
  
  // Analysis settings
  DEFAULT_TIME_RANGE: 30, // days
  DEFAULT_DIMENSION: 'moral',
  
  // API settings based on environment
  API_TIMEOUT: apiConfig.ENVIRONMENT === 'development' ? 10000 : 20000,
  API_RETRY_ATTEMPTS: apiConfig.ENVIRONMENT === 'development' ? 2 : 3,
  
  // Feature flags based on environment
  FEATURES: {
    ENABLE_DEBUG_LOGS: apiConfig.ENVIRONMENT === 'development',
    ENABLE_ANALYTICS: apiConfig.ENVIRONMENT === 'production',
    ENABLE_OFFLINE_MODE: apiConfig.ENVIRONMENT !== 'development'
  },
  
  // Error messages
  ERRORS: {
    API_UNREACHABLE: 'Server unreachable: Please make sure the API server is running',
    CONTENT_EXTRACTION_FAILED: 'Could not extract article content from this page',
    ANALYSIS_FAILED: 'An error occurred while analyzing this article',
    INSUFFICIENT_DATA: 'Not enough data for meaningful analysis',
    NETWORK_ERROR: 'Network error: Please check your internet connection',
    PRODUCTION_API_UNAVAILABLE: 'News Bias Analyzer API is temporarily unavailable. Please try again later.'
  }
};

// Log current configuration (development only)
if (CONFIG.FEATURES.ENABLE_DEBUG_LOGS) {
  console.log('🔧 Extension Configuration:', {
    environment: CONFIG.ENVIRONMENT,
    apiEndpoint: CONFIG.API_ENDPOINT,
    features: CONFIG.FEATURES
  });
}