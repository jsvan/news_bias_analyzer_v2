document.addEventListener('DOMContentLoaded', () => {
  // DOM elements
  const initialState = document.getElementById('initial-state');
  const loadingState = document.getElementById('loading-state');
  const resultsState = document.getElementById('results-state');
  const noArticleState = document.getElementById('no-article-state');
  const errorState = document.getElementById('error-state');
  const detailedView = document.getElementById('detailed-view');
  
  const analyzeBtn = document.getElementById('analyze-btn');
  const forceAnalyzeBtn = document.getElementById('force-analyze-btn');
  const retryBtn = document.getElementById('retry-btn');
  const viewDetailsBtn = document.getElementById('view-details-btn');
  const analyzeAgainBtn = document.getElementById('analyze-again-btn');
  const backBtn = document.getElementById('back-btn');
  
  const sourceEl = document.querySelector('#article-source span');
  const titleEl = document.getElementById('article-title');
  const entitiesListEl = document.getElementById('entities-list');
  const compositeIndicator = document.getElementById('composite-indicator');
  const compositePercentile = document.getElementById('composite-percentile');
  
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  
  // Configuration
  const API_ENDPOINT = 'http://localhost:8000';

  // App state
  let currentArticle = null;
  let analysisResult = null;
  
  // Helper function to generate a stable ID from URL
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

  // Initialize
  initializeExtension();
  
  // Event Listeners
  analyzeBtn.addEventListener('click', startAnalysis);
  forceAnalyzeBtn.addEventListener('click', startAnalysis);
  retryBtn.addEventListener('click', startAnalysis);
  viewDetailsBtn.addEventListener('click', showDetailedView);
  analyzeAgainBtn.addEventListener('click', resetToInitialState);
  backBtn.addEventListener('click', hideDetailedView);
  
  // Tab navigation
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      // Remove active class from all tabs
      tabButtons.forEach(btn => btn.classList.remove('active'));
      tabContents.forEach(content => content.classList.remove('active'));

      // Add active class to current tab
      button.classList.add('active');
      document.getElementById(button.dataset.tab).classList.add('active');
    });
  });
  
  // Initialize the extension
  function initializeExtension() {
    // Get current tab ID
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const currentTab = tabs[0];

      if (!currentTab) {
        showState(initialState);
        return;
      }

      // Check if we have cached results for the current tab
      const tabKey = `tab_${currentTab.id}`;
      chrome.storage.local.get([tabKey], (result) => {
        if (result[tabKey] && result[tabKey].result) {
          // We have cached results for this tab
          analysisResult = result[tabKey].result;
          displayResults(analysisResult);
        } else {
          // No cached results in tab-based storage, check URL-based storage
          const urlKey = generateArticleId(currentTab.url);
          chrome.storage.local.get([urlKey], (urlResult) => {
            if (urlResult[urlKey] && urlResult[urlKey].result) {
              // Found cached results
              console.log('Found cached analysis for URL:', currentTab.url);
              analysisResult = urlResult[urlKey].result;

              // Also cache in tab storage for faster future access
              chrome.storage.local.set({
                [tabKey]: {
                  tabId: currentTab.id,
                  url: currentTab.url,
                  result: analysisResult,
                  timestamp: Date.now()
                }
              });

              displayResults(analysisResult);
            } else {
              // No cached results at all, show initial state
              showState(initialState);
            }
          });
        }
      });
    });
  }
  
  // Start analysis
  function startAnalysis() {
    showState(loadingState);

    // Get the current tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const currentTab = tabs[0];

      // Use API for content extraction
      tryExtractContent(currentTab)
        .then(extractedContent => {
          if (extractedContent) {
            // Successfully extracted content from the API
            currentArticle = extractedContent;
            analyzeWithApi(currentArticle);
          } else {
            // Show error if API extraction fails
            showError('Content extraction failed. Please make sure the API server is running.');
          }
        })
        .catch(error => {
          console.error("Error with content extraction API:", error);
          showError('Server unreachable: Please make sure the API server is running at ' + API_ENDPOINT);
        });
    });
  }

  // Extract content using the /extract API endpoint
  function tryExtractContent(tab) {
    console.log("Extracting content using API...");

    return fetch(`${API_ENDPOINT}/extract`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: tab.url })
    })
    .then(response => {
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
      return response.json();
    })
    .then(data => {
      if (!data.text || data.text.trim() === '') {
        throw new Error("Content extraction failed: No text content found on the page.");
      }

      console.log("Content extracted successfully from API", {
        url: data.url,
        source: data.source,
        titleLength: data.title ? data.title.length : 0,
        textLength: data.text ? data.text.length : 0
      });

      // Format the extracted content
      return {
        url: data.url,
        source: data.source || new URL(data.url).hostname,
        headline: data.title,
        content: data.text,
        publishDate: data.publish_date
      };
    })
    .catch(error => {
      console.error("Content extraction failed:", error.message);
      throw error;
    });
  }
  
  // Real API call to our local API server
  function analyzeWithApi(article) {
    // Show loading state
    showState(loadingState);
    
    // Log the article data being sent
    console.log('Sending article to API:', {
      url: article.url,
      source: article.source,
      title: article.headline,
      textLength: article.content ? article.content.length : 0
    });
    
    // Log the API endpoint
    console.log('API endpoint:', `${API_ENDPOINT}/analyze`);
    
    // Create the request payload
    const payload = {
      url: article.url,
      source: article.source,
      title: article.headline,
      text: article.content
    };
    
    // Log the full request details
    console.log('API request details:', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      bodyLength: JSON.stringify(payload).length
    });
    
    fetch(`${API_ENDPOINT}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    })
    .then(response => {
      // Log raw response info
      console.log('API response received:', {
        status: response.status,
        statusText: response.statusText,
        headers: {
          'content-type': response.headers.get('content-type'),
          'content-length': response.headers.get('content-length')
        }
      });
      
      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}: ${response.statusText}`);
      }
      
      // Clone the response so we can log it and still use it
      const clonedResponse = response.clone();
      
      // Log the raw response text for debugging
      clonedResponse.text().then(text => {
        console.log('Raw API response:', text.substring(0, 500) + (text.length > 500 ? '...' : ''));
        
        try {
          // Try to parse the JSON manually to see if there's an issue
          const parsedJson = JSON.parse(text);
          console.log('Response parsed successfully as JSON');
        } catch (e) {
          console.error('Response is not valid JSON:', e);
        }
      });
      
      return response.json();
    })
    .then(result => {
      // Log the parsed result
      console.log('API result parsed:', result);
      
      // Check for API errors
      if (result.error) {
        throw new Error(result.error);
      }
      
      // Safely handle missing result properties with fallbacks
      const entities = result && result.entities ? result.entities : [];
      const quotes = result && result.quotes ? result.quotes : [];
      
      // Format the result for the UI
      const formattedResult = {
        id: generateArticleId(article.url),
        url: article.url,
        title: article.headline,
        source: article.source,
        entities: entities,
        quotes: quotes,
        composite_score: result.composite_score || { percentile: 50 },
        from_cache: false
      };
      
      console.log('Formatted result:', formattedResult);
      
      // Safely add statistical significance if not present and normalize entity fields
      if (formattedResult.entities && Array.isArray(formattedResult.entities)) {
        formattedResult.entities.forEach(entity => {
          // Normalize the name field
          if (!entity.name && entity.entity) {
            entity.name = entity.entity;
          }

          // Normalize the type field
          if (!entity.type && entity.entity_type) {
            entity.type = entity.entity_type;
          }

          // Add mentions in the expected format if missing
          if (!entity.mentions) {
            // Try to find quotes by this entity's name
            const entityQuotes = (formattedResult.quotes || [])
              .filter(quote => quote.speaker && quote.speaker === (entity.name || entity.entity))
              .map(quote => ({ text: quote.quote, context: quote.title || 'from article' }));

            // Use matching quotes or empty array
            entity.mentions = entityQuotes.length > 0 ? entityQuotes : [];
          }
        });
      }
      
      // Cache the result
      cacheAnalysisResult(formattedResult);
      
      // Display the results
      displayResults(formattedResult);
    })
    .catch(error => {
      // Enhanced error logging
      console.error('API error details:', {
        message: error.message,
        stack: error.stack,
        name: error.name
      });
      
      // Try to ping the API server to check if it's accessible
      fetch(`${API_ENDPOINT}/health`)
        .then(response => {
          console.log('API server ping result:', {
            status: response.status,
            ok: response.ok
          });
        })
        .catch(pingError => {
          console.error('API server ping failed:', pingError.message);
          showError('Server unreachable: Please make sure the API server is running at ' + API_ENDPOINT);
        });
    });
  }
  
  // Cache analysis result for the current tab and URL
  function cacheAnalysisResult(result) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const currentTab = tabs[0];

      if (!currentTab) return;

      // Generate keys for storage
      const tabKey = `tab_${currentTab.id}`;
      const urlKey = generateArticleId(currentTab.url);

      // Create storage object with current timestamp
      const storageObject = {
        tabId: currentTab.id,
        url: currentTab.url,
        result: result,
        timestamp: Date.now()
      };

      // Store by both tab ID and URL
      chrome.storage.local.set({
        [tabKey]: storageObject,
        [urlKey]: storageObject
      });

      // Log that we've cached by URL for debugging
      console.log('Cached analysis result by URL:', currentTab.url, 'with ID:', urlKey);

      analysisResult = result;
    });
  }
  
  // Display analysis results
  function displayResults(result) {
    if (!result) {
      console.error("No result data to display");
      showError("Failed to display results: No data available");
      return;
    }

    try {
      // Ensure result.article exists for use in similarity tab
      if (!result.article) {
        result.article = {
          id: result.id || generateArticleId(result.url),
          url: result.url,
          title: result.title,
          source: result.source
        };
      }

      // Set source and title with safe defaults
      sourceEl.textContent = result.source || "Unknown Source";
      titleEl.textContent = result.title || "Untitled Article";
      
      // Set composite score
      const percentile = result.composite_score && result.composite_score.percentile 
        ? result.composite_score.percentile 
        : 50; // Default to median if no percentile
        
      compositeIndicator.style.left = `${percentile}%`;
      
      // Format percentile text
      let percentileText;
      if (percentile < 10) {
        percentileText = 'highly unusual (bottom 10%)';
      } else if (percentile < 25) {
        percentileText = 'unusual (bottom 25%)';
      } else if (percentile > 90) {
        percentileText = 'very typical (top 10%)';
      } else if (percentile > 75) {
        percentileText = 'typical (top 25%)';
      } else {
        percentileText = 'average';
      }

      // Create a simple cache indicator tag if showing cached results
      const cacheTag = document.getElementById('cache-indicator');
      if (cacheTag) {
        if (result.from_cache) {
          // Retrieved from database
          cacheTag.textContent = 'DB';
          cacheTag.title = 'Analysis retrieved from database';
          cacheTag.style.display = 'inline-block';
          cacheTag.style.backgroundColor = '#4a90e2';
        } else if (result.timestamp || result.analyzed_at) {
          // Retrieved from browser extension cache
          cacheTag.textContent = 'CACHED';
          cacheTag.title = 'Previously analyzed article';
          cacheTag.style.display = 'inline-block';
          cacheTag.style.backgroundColor = '#06d6a0';
        } else {
          cacheTag.style.display = 'none';
        }
      }

      compositePercentile.textContent = percentileText;
      
      // Display entities with safety checks
      if (result.entities && Array.isArray(result.entities)) {
        displayEntityList(result.entities);
      } else {
        console.warn("No entity data to display");
        entitiesListEl.innerHTML = '<div class="empty-message">No entities found in this article</div>';
      }
      
      // Show results state
      showState(resultsState);
    } catch (e) {
      console.error("Error displaying results:", e);
      showError("Failed to display results: " + e.message);
    }
  }
  
  // Display entity list in results view
  function displayEntityList(entities) {
    entitiesListEl.innerHTML = '';

    entities.forEach(entity => {
      const entityItem = document.createElement('div');
      entityItem.className = 'entity-item';

      // Use either entity.name or entity.entity
      const displayName = entity.name || entity.entity || "Unknown Entity";

      // Use either entity.type or entity.entity_type
      const entityType = entity.type || entity.entity_type;

      // Map power score (-2 to 2) to percentage (0 to 100)
      const powerPercentage = ((entity.power_score + 2) / 4) * 100;

      // Map moral score (-2 to 2) to percentage (0 to 100)
      const moralPercentage = ((entity.moral_score + 2) / 4) * 100;

      // Determine significance class
      let sigClass = 'not-significant';
      if (entity.national_significance === null) {
        sigClass = 'no-data';
      } else if (entity.national_significance < 0.05) {
        sigClass = 'significant';
      }

      entityItem.innerHTML = `
        <div class="entity-header">
          <div class="entity-name">${displayName}</div>
          <div class="entity-type">${formatEntityType(entityType)}</div>
        </div>
        <div class="sentiment-bars">
          <div class="sentiment-bar">
            <div class="bar-label">
              <span>Weak</span>
              <span>Power</span>
              <span>Strong</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill power" style="width: ${powerPercentage}%; left: 0;"></div>
            </div>
          </div>
          <div class="sentiment-bar">
            <div class="bar-label">
              <span>Evil</span>
              <span>Morality</span>
              <span>Good</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill moral" style="width: ${moralPercentage}%; left: 0;"></div>
            </div>
          </div>
        </div>
        <div class="statistical-significance ${sigClass}">
          ${entity.national_significance === null
            ? 'Insufficient data for statistical analysis'
            : entity.national_significance < 0.05
              ? `Unusual portrayal (p=${entity.national_significance.toFixed(3)})`
              : 'Typical portrayal'}
        </div>
      `;
      
      entitiesListEl.appendChild(entityItem);
    });
  }
  
  // Show detailed view
  function showDetailedView() {
    resultsState.classList.add('hidden');
    detailedView.classList.remove('hidden');
  }
  
  // Hide detailed view
  function hideDetailedView() {
    detailedView.classList.add('hidden');
    resultsState.classList.remove('hidden');
  }
  
  // Reset to initial state
  function resetToInitialState() {
    showState(initialState);
  }
  
  // Show error message
  function showError(message) {
    const errorMessage = document.querySelector('#error-state p');
    errorMessage.textContent = message;
    showState(errorState);
  }
  
  // Show specified state, hide others
  function showState(stateToShow) {
    const states = [initialState, loadingState, resultsState, noArticleState, errorState, detailedView];
    states.forEach(state => {
      if (state === stateToShow) {
        state.classList.remove('hidden');
      } else {
        state.classList.add('hidden');
      }
    });
  }
  
  // Format entity type for display
  function formatEntityType(type) {
    if (!type) {
      return 'Unknown';
    }

    switch(type) {
      case 'person':
        return 'Person';
      case 'country':
        return 'Country';
      case 'organization':
        return 'Organization';
      case 'political_party':
        return 'Political Party';
      default:
        return type.charAt(0).toUpperCase() + type.slice(1);
    }
  }
});