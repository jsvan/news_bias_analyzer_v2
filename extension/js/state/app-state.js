// Application State Management with Observer Pattern
import { CONFIG } from '../config.js';

export class AppState {
  constructor() {
    // Core application state
    this.state = {
      // Article and analysis data
      currentArticle: null,
      analysisResult: null,
      
      // UI state
      activeTab: 'entity-tab',
      currentView: 'initial', // 'initial', 'loading', 'results', 'detailed', 'no-article', 'error'
      
      // Cache management
      cache: new Map(),
      
      // Error state
      lastError: null,
      
      // Tab-specific data
      tabData: {
        entities: [],
        similarityData: null,
        trackingData: null,
        distributionData: null
      }
    };

    // Observer pattern for state changes
    this.observers = new Map();
    
    // Initialize cache cleanup
    this.initializeCacheCleanup();
  }

  // Observer pattern methods
  subscribe(key, callback) {
    if (!this.observers.has(key)) {
      this.observers.set(key, []);
    }
    this.observers.get(key).push(callback);
    
    // Return unsubscribe function
    return () => {
      const callbacks = this.observers.get(key);
      if (callbacks) {
        const index = callbacks.indexOf(callback);
        if (index > -1) {
          callbacks.splice(index, 1);
        }
      }
    };
  }

  notify(key, data = null) {
    const callbacks = this.observers.get(key);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data, this.state);
        } catch (error) {
          console.error('Error in state observer:', error);
        }
      });
    }
  }

  // State management methods
  setCurrentArticle(article) {
    this.state.currentArticle = article;
    this.notify('currentArticle', article);
  }

  setAnalysisResult(result) {
    this.state.analysisResult = result;
    this.notify('analysisResult', result);
    
    // Cache the result
    if (result && result.url) {
      this.cacheAnalysisResult(result);
    }
  }

  setActiveTab(tabId) {
    this.state.activeTab = tabId;
    this.notify('activeTab', tabId);
  }

  setCurrentView(view) {
    this.state.currentView = view;
    this.notify('currentView', view);
  }

  setError(error) {
    this.state.lastError = error;
    this.notify('error', error);
  }

  clearError() {
    this.state.lastError = null;
    this.notify('error', null);
  }

  // Getters
  getCurrentArticle() {
    return this.state.currentArticle;
  }

  getAnalysisResult() {
    return this.state.analysisResult;
  }

  getActiveTab() {
    return this.state.activeTab;
  }

  getCurrentView() {
    return this.state.currentView;
  }

  getLastError() {
    return this.state.lastError;
  }

  // Cache management
  cacheAnalysisResult(result) {
    if (!result.url) return;
    
    const cacheKey = this.generateCacheKey(result.url);
    const cacheEntry = {
      result: result,
      timestamp: Date.now(),
      tabId: result.tabId || null
    };
    
    this.state.cache.set(cacheKey, cacheEntry);
    
    // Also cache in Chrome storage for persistence
    this.cacheToChromeStorage(cacheKey, cacheEntry);
  }

  getCachedAnalysis(url, tabId = null) {
    const cacheKey = this.generateCacheKey(url);
    const cached = this.state.cache.get(cacheKey);
    
    if (cached && this.isCacheValid(cached)) {
      return cached.result;
    }
    
    return null;
  }

  async loadCacheFromChromeStorage(url, tabId = null) {
    return new Promise((resolve) => {
      const cacheKey = this.generateCacheKey(url);
      const tabKey = tabId ? `tab_${tabId}` : null;
      
      const keysToCheck = [cacheKey];
      if (tabKey) keysToCheck.push(tabKey);
      
      chrome.storage.local.get(keysToCheck, (result) => {
        // Try tab-specific cache first, then URL cache
        const cached = result[tabKey] || result[cacheKey];
        
        if (cached && this.isCacheValid(cached)) {
          // Add to in-memory cache
          this.state.cache.set(cacheKey, cached);
          resolve(cached.result);
        } else {
          resolve(null);
        }
      });
    });
  }

  cacheToChromeStorage(cacheKey, cacheEntry) {
    const storageData = {};
    storageData[cacheKey] = cacheEntry;
    
    // Also cache by tab if available
    if (cacheEntry.tabId) {
      storageData[`tab_${cacheEntry.tabId}`] = cacheEntry;
    }
    
    chrome.storage.local.set(storageData);
  }

  generateCacheKey(url) {
    // Simple hash function for consistent cache keys
    let hash = 0;
    for (let i = 0; i < url.length; i++) {
      const char = url.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return 'analysis_' + Math.abs(hash).toString(16);
  }

  isCacheValid(cacheEntry) {
    if (!cacheEntry || !cacheEntry.timestamp) return false;
    
    const age = Date.now() - cacheEntry.timestamp;
    return age < CONFIG.CACHE_TTL;
  }

  // Cache cleanup
  initializeCacheCleanup() {
    // Clean up expired cache entries every 5 minutes
    setInterval(() => {
      this.cleanupExpiredCache();
    }, 5 * 60 * 1000);
  }

  cleanupExpiredCache() {
    const now = Date.now();
    const expiredKeys = [];
    
    for (const [key, entry] of this.state.cache.entries()) {
      if (!this.isCacheValid(entry)) {
        expiredKeys.push(key);
      }
    }
    
    // Remove from in-memory cache
    expiredKeys.forEach(key => {
      this.state.cache.delete(key);
    });
    
    // Clean up Chrome storage
    if (expiredKeys.length > 0) {
      chrome.storage.local.remove(expiredKeys);
    }
  }

  // Reset state (useful for testing or complete refresh)
  reset() {
    const oldState = { ...this.state };
    
    this.state = {
      currentArticle: null,
      analysisResult: null,
      activeTab: 'entity-tab',
      currentView: 'initial',
      cache: new Map(),
      lastError: null,
      tabData: {
        entities: [],
        similarityData: null,
        trackingData: null,
        distributionData: null
      }
    };
    
    this.notify('reset', { oldState, newState: this.state });
  }

  // Debugging helpers
  getStateSnapshot() {
    return {
      ...this.state,
      cache: Array.from(this.state.cache.entries()),
      observers: Array.from(this.observers.keys())
    };
  }

  logState() {
    console.log('Current AppState:', this.getStateSnapshot());
  }
}

// Create singleton instance
export const appState = new AppState();