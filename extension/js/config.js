// Configuration for the Chrome extension.
// The API endpoint comes from chrome.storage (set in the options page),
// defaulting to a local server. background.js uses the same storage key.

const DEFAULT_API_ENDPOINT = 'http://localhost:8000';

export const CONFIG = {
  // API Configuration — updated asynchronously from chrome.storage below.
  // Read this at request time (not once at startup) to pick up user settings.
  API_ENDPOINT: DEFAULT_API_ENDPOINT,

  // Cache settings
  CACHE_TTL: 300000, // 5 minutes

  // UI Constants
  MAX_ENTITIES_DISPLAY: 50,
  HISTOGRAM_WIDTH: 320,
  HISTOGRAM_HEIGHT: 200,

  // Analysis settings
  DEFAULT_TIME_RANGE: 30, // days
  DEFAULT_DIMENSION: 'moral',

  // API settings
  API_TIMEOUT: 20000,
  API_RETRY_ATTEMPTS: 3,

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

// Load the user-configured endpoint (same 'settings' key as options.js/background.js).
if (typeof chrome !== 'undefined' && chrome.storage) {
  chrome.storage.sync.get('settings', (data) => {
    if (data.settings && data.settings.apiEndpoint) {
      CONFIG.API_ENDPOINT = data.settings.apiEndpoint;
    }
  });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'sync' && changes.settings && changes.settings.newValue?.apiEndpoint) {
      CONFIG.API_ENDPOINT = changes.settings.newValue.apiEndpoint;
    }
  });
}
