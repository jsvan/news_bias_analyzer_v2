// Background script for News Bias Analyzer extension

// Configuration - will be populated from storage settings
let CONFIG = {
  API_ENDPOINT: 'http://localhost:8000',
  ANALYSIS_MODE: 'live', // 'live' or 'demo'
  AUTO_ANALYZE: false,
  SAVE_HISTORY: true,
  MAX_HISTORY_ITEMS: 50,
  FORCE_REANALYSIS: false // Whether to force API to reanalyze even if in database
};

// Initialize extension
chrome.runtime.onInstalled.addListener(async () => {
  console.log('News Bias Analyzer extension installed');
  
  // Initialize default settings if not present
  const settings = await chrome.storage.sync.get(['settings']);
  
  if (!settings.settings) {
    // Set default settings
    const defaultSettings = {
      apiEndpoint: 'http://localhost:8000',
      analysisMode: 'live', // Use live mode to connect to our API
      autoAnalyze: false,
      saveHistory: true,
      maxHistoryItems: 50,
      theme: 'light',
      forceReanalysis: false
    };
    
    // Save default settings
    await chrome.storage.sync.set({ settings: defaultSettings });
    CONFIG.API_ENDPOINT = defaultSettings.apiEndpoint;
    CONFIG.ANALYSIS_MODE = defaultSettings.analysisMode;
    CONFIG.AUTO_ANALYZE = defaultSettings.autoAnalyze;
    CONFIG.SAVE_HISTORY = defaultSettings.saveHistory;
    CONFIG.MAX_HISTORY_ITEMS = defaultSettings.maxHistoryItems;
    CONFIG.FORCE_REANALYSIS = defaultSettings.forceReanalysis;
  } else {
    // Load existing settings
    CONFIG.API_ENDPOINT = settings.settings.apiEndpoint;
    CONFIG.ANALYSIS_MODE = settings.settings.analysisMode;
    CONFIG.AUTO_ANALYZE = settings.settings.autoAnalyze;
    CONFIG.SAVE_HISTORY = settings.settings.saveHistory;
    CONFIG.MAX_HISTORY_ITEMS = settings.settings.maxHistoryItems;
    CONFIG.FORCE_REANALYSIS = settings.settings.forceReanalysis !== undefined ? 
                             settings.settings.forceReanalysis : false;
  }
  
  // Create context menu item for analysis
  chrome.contextMenus.create({
    id: 'analyzeArticle',
    title: 'Analyze this article for bias',
    contexts: ['page']
  });
});

// Reload configuration when settings are changed
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'sync' && changes.settings) {
    const newSettings = changes.settings.newValue;
    CONFIG.API_ENDPOINT = newSettings.apiEndpoint;
    CONFIG.ANALYSIS_MODE = newSettings.analysisMode;
    CONFIG.AUTO_ANALYZE = newSettings.autoAnalyze;
    CONFIG.SAVE_HISTORY = newSettings.saveHistory;
    CONFIG.MAX_HISTORY_ITEMS = newSettings.maxHistoryItems;
    CONFIG.FORCE_REANALYSIS = newSettings.forceReanalysis !== undefined ? 
                             newSettings.forceReanalysis : false;
  }
});

// Listen for context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'analyzeArticle' && tab) {
    // Send message to content script to extract article content
    chrome.tabs.sendMessage(tab.id, { action: 'getPageContent' }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Error communicating with content script:', chrome.runtime.lastError);
        return;
      }
      
      if (response && response.content) {
        analyzeArticleContent(response.content, tab);
      }
    });
  }
});

// Auto-analyze when a news page loads if enabled
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && CONFIG.AUTO_ANALYZE) {
    // Check if this is a news site
    if (isNewsSite(tab.url)) {
      // Send message to content script to extract article content
      chrome.tabs.sendMessage(tabId, { action: 'getPageContent' }, (response) => {
        if (chrome.runtime.lastError) {
          // Content script might not be ready yet, or not applicable to this page
          return;
        }

        if (response && response.content) {
          analyzeArticleContent(response.content, tab);
        }
      });
    }
  }

  // When navigating to a new page, clear tab-specific cache but keep URL-based cache
  if (changeInfo.status === 'loading') {
    // Clear badge
    chrome.action.setBadgeText({
      text: '',
      tabId: tabId
    });

    // Clear cached analysis for this tab but preserve URL-based caches
    chrome.storage.local.remove([`tab_${tabId}`], function() {
      // Notify popup if it's open to refresh the view
      // The popup will check URL-based cache on initialization
      chrome.runtime.sendMessage({
        action: 'resetAnalysis',
        tabId: tabId,
        url: tab.url // Include URL for possible immediate rechecking
      });
    });
  }
});

// Check if URL is from a news site
function isNewsSite(url) {
  try {
    const domain = new URL(url).hostname;
    const newsDomains = [
      'nytimes.com', 'washingtonpost.com', 'wsj.com', 'bbc.com', 'bbc.co.uk',
      'cnn.com', 'foxnews.com', 'nbcnews.com', 'abcnews.go.com', 'cbsnews.com',
      'reuters.com', 'apnews.com', 'theguardian.com', 'huffpost.com', 'politico.com',
      'time.com', 'usatoday.com', 'latimes.com', 'chicagotribune.com', 'nypost.com',
      'newsweek.com', 'aljazeera.com', 'france24.com', 'dw.com', 'rt.com'
    ];
    
    return newsDomains.some(newsDomain => domain.includes(newsDomain));
  } catch (e) {
    return false;
  }
}

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Handle message based on action
  switch (request.action) {
    case 'analyzeContent':
      analyzeArticleContent(request.content, sender.tab);
      sendResponse({status: 'Processing'});
      break;
      
    case 'storeAnalysisResult':
      storeAnalysisResult(request.result, sender.tab?.id);
      sendResponse({status: 'Stored'});
      break;
      
    case 'setAnalysisBadge':
      setBadgeForAnalysis(request.result, sender.tab?.id);
      sendResponse({status: 'Badge set'});
      break;
      
    case 'getSettings':
      getSettings().then(settings => sendResponse({settings}));
      return true; // Keep channel open for async response
      
    case 'saveSettings':
      saveSettings(request.settings)
        .then(() => sendResponse({status: 'Settings saved'}))
        .catch(error => sendResponse({status: 'Error', error}));
      return true; // Keep channel open for async response
      
    case 'getAnalysisHistory':
      getAnalysisHistory().then(history => sendResponse({history}));
      return true; // Keep channel open for async response
      
    case 'clearAnalysisHistory':
      clearAnalysisHistory().then(() => sendResponse({status: 'History cleared'}));
      return true; // Keep channel open for async response
  }
  
  return true; // Keep the message channel open for async responses
});

// Load settings from storage
async function getSettings() {
  const data = await chrome.storage.sync.get(['settings']);
  return data.settings || {};
}

// Save settings to storage
async function saveSettings(settings) {
  await chrome.storage.sync.set({ settings });
  return { success: true };
}

// Get analysis history
async function getAnalysisHistory() {
  const data = await chrome.storage.local.get(['analysisHistory']);
  return data.analysisHistory || [];
}

// Clear analysis history
async function clearAnalysisHistory() {
  await chrome.storage.local.remove(['analysisHistory']);
  return { success: true };
}

// Analyze article content through the API
function analyzeArticleContent(content, tab) {
  // Set badge to show processing
  if (tab && tab.id) {
    chrome.action.setBadgeText({ 
      text: '...',
      tabId: tab.id
    });
    chrome.action.setBadgeBackgroundColor({
      color: '#8d99ae',
      tabId: tab.id
    });
  }
  
  // Choose analysis mode based on settings
  if (CONFIG.ANALYSIS_MODE === 'demo') {
    simulateApiAnalysis(content, tab);
  } else {
    callAnalysisApi(content, tab);
  }
}

// Simulate API analysis (for demo mode)
function simulateApiAnalysis(content, tab) {
  // Simulate API call delay
  setTimeout(() => {
    // Generate mock result
    const mockResult = {
      source: content.source,
      title: content.headline,
      url: content.url,
      publish_date: content.publishDate || new Date().toISOString(),
      composite_score: {
        percentile: Math.floor(Math.random() * 100),
        p_value: Math.random() * 0.2
      },
      entities: [
        {
          name: "United States",
          type: "country",
          power_score: 3.8,
          moral_score: 0.5,
          national_significance: 0.032,
          global_significance: 0.067,
          mentions: [
            {
              text: "The United States announced new sanctions",
              context: "diplomatic response"
            },
            {
              text: "U.S. officials emphasized",
              context: "policy statement"
            }
          ]
        },
        {
          name: "President Johnson",
          type: "person",
          power_score: 4.2,
          moral_score: -1.3,
          national_significance: 0.012,
          global_significance: 0.008,
          mentions: [
            {
              text: "President Johnson declared",
              context: "official statement"
            },
            {
              text: "Johnson's controversial decision",
              context: "policy analysis"
            }
          ]
        },
        {
          name: "European Union",
          type: "organization",
          power_score: 1.4,
          moral_score: 2.8,
          national_significance: 0.089,
          global_significance: 0.113,
          mentions: [
            {
              text: "The EU expressed concern",
              context: "diplomatic response"
            },
            {
              text: "European leaders have struggled",
              context: "political analysis"
            }
          ]
        },
        {
          name: "Democratic Party",
          type: "political_party",
          power_score: -0.8,
          moral_score: 1.1,
          national_significance: 0.217,
          global_significance: 0.186,
          mentions: [
            {
              text: "Democrats criticized the approach",
              context: "political response"
            },
            {
              text: "The party's position has been consistent",
              context: "political analysis"
            }
          ]
        }
      ]
    };
    
    // Process the mocked result
    processAnalysisResult(mockResult, tab);
    
  }, 2000);
}

// Normalize URL by removing tracking parameters
function normalizeUrl(url) {
  try {
    const urlObj = new URL(url);
    
    // List of common tracking parameters to remove
    const trackingParams = [
      'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
      'fbclid', 'gclid', 'msclkid', 'zanpid', 'dclid', 'igshid', 
      'ref', 'referrer', 'source', 'campaign', 'ref_src', 'ref_url',
      '_hsenc', '_hsmi', 'mc_cid', 'mc_eid', 'yclid', 'twclid'
    ];
    
    // Remove tracking parameters
    trackingParams.forEach(param => {
      urlObj.searchParams.delete(param);
    });
    
    // Remove anchors (fragments) as they're often used for tracking too
    urlObj.hash = '';
    
    return urlObj.toString();
  } catch (e) {
    console.error('Error normalizing URL:', e);
    return url; // Return original URL if normalization fails
  }
}

// Call the real API for analysis
async function callAnalysisApi(content, tab) {
  // Normalize URL to remove tracking parameters
  const normalizedUrl = normalizeUrl(content.url);
  
  // Call API with the force parameter based on settings
  fetch(`${CONFIG.API_ENDPOINT}/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      url: normalizedUrl, // Use normalized URL
      source: content.source,
      title: content.headline,
      text: content.content,
      publish_date: content.publishDate,
      force_reanalysis: CONFIG.FORCE_REANALYSIS // Tell API whether to use database or reanalyze
    })
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }
    return response.json();
  })
  .then(result => {
    // Add data source info for user feedback
    result.from_cache = !result.newly_analyzed;
    
    // Process the result
    processAnalysisResult(result, tab);
  })
  .catch(error => {
    console.error('Error analyzing article:', error);
    
    // Set error badge and notify popup
    handleAnalysisError(error, tab);
  });
}

// Process analysis result
function processAnalysisResult(result, tab) {
  // Add timestamp
  result.analyzed_at = new Date().toISOString();
  
  // Store and process the result
  storeAnalysisResult(result, tab?.id);
  setBadgeForAnalysis(result, tab?.id);
  
  // Save to history if enabled
  if (CONFIG.SAVE_HISTORY) {
    saveToAnalysisHistory(result);
  }
  
  // Notify popup if it's open
  chrome.runtime.sendMessage({
    action: 'newAnalysisResult',
    result: result
  });
}

// Handle analysis error
function handleAnalysisError(error, tab) {
  // Set error badge
  if (tab && tab.id) {
    chrome.action.setBadgeText({ 
      text: 'ERR',
      tabId: tab.id
    });
    chrome.action.setBadgeBackgroundColor({
      color: '#ef476f',
      tabId: tab.id
    });
  }
  
  // Notify popup if it's open
  chrome.runtime.sendMessage({
    action: 'analysisError',
    error: error.message
  });
}

// Store analysis result in local storage (by both tab ID and URL)
function storeAnalysisResult(result, tabId) {
  if (!tabId) return;

  // Get URL from result or use a safe fallback
  const url = result.url || (result.article ? result.article.url : 'unknown');

  if (!url || url === 'unknown') {
    console.warn('Cannot store analysis without a valid URL');
    return;
  }

  // Generate keys for storage
  const tabKey = `tab_${tabId}`;
  const urlKey = generateArticleId(url);

  // Create storage object with current timestamp
  const storageObject = {
    tabId: tabId,
    url: url,
    result: result,
    timestamp: Date.now()
  };

  // Store by both tab ID and URL for persistent access
  chrome.storage.local.set({
    [tabKey]: storageObject,
    [urlKey]: storageObject
  });

  console.log('Stored analysis by URL:', url, 'with ID:', urlKey);

  // Remove old storage format if it exists
  chrome.storage.local.remove(['currentTabId']);
}

// Helper function to generate a stable ID from URL (copied from popup.js for consistency)
function generateArticleId(url) {
  // Simple hash function for consistent article IDs
  if (!url) return 'unknown_article';

  let hash = 0;
  for (let i = 0; i < url.length; i++) {
    const char = url.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return 'article_' + Math.abs(hash).toString(16);
}

// Save result to analysis history
async function saveToAnalysisHistory(result) {
  try {
    // Get existing history
    const data = await chrome.storage.local.get(['analysisHistory']);
    let history = data.analysisHistory || [];
    
    // Add new item to beginning
    history.unshift({
      url: result.url,
      title: result.title,
      source: result.source,
      timestamp: Date.now(),
      result: result
    });
    
    // Limit history size
    if (history.length > CONFIG.MAX_HISTORY_ITEMS) {
      history = history.slice(0, CONFIG.MAX_HISTORY_ITEMS);
    }
    
    // Save updated history
    await chrome.storage.local.set({ analysisHistory: history });
  } catch (error) {
    console.error('Error saving to analysis history:', error);
  }
}

// Set badge based on analysis result
function setBadgeForAnalysis(result, tabId) {
  if (!tabId) return;
  
  // Get the composite score percentile
  const percentile = result.composite_score.percentile;
  
  // Set badge color based on percentile
  let badgeColor;
  let badgeText;
  
  if (percentile < 10) {
    // Very unusual
    badgeColor = '#ef476f'; // Red
    badgeText = '!';
  } else if (percentile < 25) {
    // Unusual
    badgeColor = '#ffd166'; // Yellow
    badgeText = '?';
  } else {
    // Typical
    badgeColor = '#06d6a0'; // Green
    badgeText = '✓';
  }
  
  // Set badge
  chrome.action.setBadgeText({ 
    text: badgeText,
    tabId: tabId
  });
  chrome.action.setBadgeBackgroundColor({
    color: badgeColor,
    tabId: tabId
  });
}