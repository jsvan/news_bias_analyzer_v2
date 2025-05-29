// Configuration management for the Chrome extension
export const CONFIG = {
  // API Configuration
  API_ENDPOINT: 'http://localhost:8000',
  
  // Cache settings
  CACHE_TTL: 300000, // 5 minutes
  
  // UI Constants
  MAX_ENTITIES_DISPLAY: 50,
  HISTOGRAM_WIDTH: 320,
  HISTOGRAM_HEIGHT: 200,
  
  // Analysis settings
  DEFAULT_TIME_RANGE: 30, // days
  DEFAULT_DIMENSION: 'moral',
  
  // Error messages
  ERRORS: {
    API_UNREACHABLE: 'Server unreachable: Please make sure the API server is running',
    CONTENT_EXTRACTION_FAILED: 'Could not extract article content from this page',
    ANALYSIS_FAILED: 'An error occurred while analyzing this article',
    INSUFFICIENT_DATA: 'Not enough data for meaningful analysis'
  }
};