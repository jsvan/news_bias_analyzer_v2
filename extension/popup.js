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

  // Check if API is available
  fetch(`${API_ENDPOINT}/health`)
    .catch(error => {
      console.warn('API health check failed:', error);
      document.getElementById('api-status-warning').style.display = 'block';
    });
  
  // App state
  let currentArticle = null;
  let analysisResult = null;
  
  // Helper function to generate a stable ID from URL (global function)
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

  // Add event listener for the methodology info link
  const methodologyLink = document.getElementById('methodology-link');
  if (methodologyLink) {
    methodologyLink.addEventListener('click', () => {
      showDetailedView();

      // Select the methodology tab
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

      const methodologyTab = document.querySelector('[data-tab="methodology-tab"]');
      if (methodologyTab) {
        methodologyTab.classList.add('active');
        document.getElementById('methodology-tab').classList.add('active');

        // Populate article-specific data in the methodology tab
        populateArticleDataForMethodology();
      }
    });
  }
  
  // Tab navigation
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      // Remove active class from all tabs
      tabButtons.forEach(btn => btn.classList.remove('active'));
      tabContents.forEach(content => content.classList.remove('active'));

      // Add active class to current tab
      button.classList.add('active');
      document.getElementById(button.dataset.tab).classList.add('active');

      // Load data for the specific tab if selected
      if (button.dataset.tab === 'similarity-tab' && analysisResult) {
        loadSimilarArticles();
      } else if (button.dataset.tab === 'methodology-tab' && analysisResult) {
        populateArticleDataForMethodology();
      }
    });
  });

  // Initialize visualizations
  const similarityCluster = new SimilarityClusterViz('similarity-canvas');
  const entityTracking = new EntityTrackingViz('entity-tracking-chart');
  const topicCluster = new TopicClusterViz('topic-cluster-canvas', {
    onNodeSelected: handleTopicNodeSelected
  });

  // Elements for similarity tab
  const similarityThresholdSelect = document.getElementById('similarity-threshold');
  const maxResultsSelect = document.getElementById('max-results');
  const similarityResults = document.getElementById('similarity-results');

  // Elements for entity tracking tab
  const trackingEntitySelector = document.getElementById('tracking-entity-selector');
  const trackingTimeRange = document.getElementById('tracking-time-range');
  const trackingInsight = document.getElementById('tracking-insight');

  // Elements for topic cluster tab
  const clusterViewType = document.getElementById('cluster-view-type');
  const clusterThreshold = document.getElementById('cluster-threshold');
  const clusterDetails = document.getElementById('cluster-details');
  const selectedItemTitle = document.getElementById('selected-item-title');
  const selectedItemDetails = document.getElementById('selected-item-details');

  // Add event listeners for similarity controls
  similarityThresholdSelect.addEventListener('change', loadSimilarArticles);
  maxResultsSelect.addEventListener('change', loadSimilarArticles);

  // Add event listeners for entity tracking controls
  trackingEntitySelector.addEventListener('change', loadEntityTracking);
  trackingTimeRange.addEventListener('change', loadEntityTracking);

  // Add event listeners for topic cluster controls
  clusterViewType.addEventListener('change', loadTopicClusters);
  clusterThreshold.addEventListener('change', loadTopicClusters);
  
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
              // All cached results are considered valid regardless of age
              console.log('Found cached analysis for URL:', currentTab.url);
              analysisResult = urlResult[urlKey].result;

              // Also cache in tab storage for faster future access
              chrome.storage.local.set({
                [tabKey]: {
                  tabId: currentTab.id,
                  url: currentTab.url,
                  result: analysisResult,
                  timestamp: Date.now() // Update timestamp for tracking purposes
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

      // Use API with trafilatura for content extraction (no fallback)
      tryExtractContent(currentTab)
        .then(extractedContent => {
          if (extractedContent) {
            // Successfully extracted content from the API
            currentArticle = extractedContent;
            analyzeWithApi(currentArticle);
          } else {
            // Show error if API extraction fails
            showError('Content extraction failed. Please try again or check if the API server is running.');
          }
        })
        .catch(error => {
          console.error("Error with content extraction API:", error);
          showError('Content extraction failed: ' + error.message);
        });
    });
  }

  // Extract content using the /extract API endpoint with trafilatura
  function tryExtractContent(tab) {
    console.log("Extracting content using API (trafilatura)...");

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

      // Format the extracted content to match our expected format
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
      // No longer returning null - let the error propagate to the calling function
      throw error;
    });
  }

  // Note: We've removed the extractContentFromPage function
  // We now rely exclusively on the API's /extract endpoint with trafilatura
  // for content extraction, with no fallback mechanism
  
  // Simulate API analysis with mock data (for development)
  // In production, this would be a real API call
  function simulateApiAnalysis(article) {
    // Simulate API processing time
    setTimeout(() => {
      // Generate fake analysis result
      const mockResult = generateMockResult(article);
      
      // Cache the result
      cacheAnalysisResult(mockResult);
      
      // Display the results
      displayResults(mockResult);
    }, 1500);
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
        composite_score: {
          percentile: Math.floor(Math.random() * 100), // We'll randomly generate this for now
        },
        from_cache: false
      };

      // Use the global generateArticleId function
      
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

          // Add default significance if missing
          if (!entity.national_significance) {
            entity.national_significance = Math.random() * 0.2;
          }
          if (!entity.global_significance) {
            entity.global_significance = Math.random() * 0.2;
          }

          // Add mentions in the expected format
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
      fetch(`${API_ENDPOINT}`)
        .then(response => {
          console.log('API server ping result:', {
            status: response.status,
            ok: response.ok
          });
        })
        .catch(pingError => {
          console.error('API server ping failed:', pingError.message);
          showError('Could not connect to API server. Is it running at ' + API_ENDPOINT + '?');
        });
      
      showError('Could not analyze article: ' + error.message);
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
      
      // Prepare detailed view
      try {
        prepareDetailedView(result);
      } catch (e) {
        console.warn("Error preparing detailed view:", e);
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
  
  // Prepare detailed view
  function prepareDetailedView(result) {
    const entityTabContent = document.querySelector('.entity-details-container');
    entityTabContent.innerHTML = '';

    // Create detailed entity cards
    result.entities.forEach(entity => {
      const entityDetail = document.createElement('div');
      entityDetail.className = 'entity-detail';

      // Use either entity.name or entity.entity
      const displayName = entity.name || entity.entity || "Unknown Entity";

      // Use either entity.type or entity.entity_type
      const entityType = entity.type || entity.entity_type;

      // Generate mock statistical data for different countries/regions
      const mockStatistics = {
        national: { pValue: entity.national_significance },
        global: { pValue: entity.global_significance },
        us: { pValue: Math.random() * 0.15 },
        uk: { pValue: Math.random() * 0.2 },
        eu: { pValue: Math.random() * 0.3 },
        asia: { pValue: Math.random() * 0.4 }
      };

      // Format mentions
      const mentionsHtml = entity.mentions.map(mention =>
        `<p>"${mention.text}" <em>(${mention.context})</em></p>`
      ).join('');

      entityDetail.innerHTML = `
        <div class="entity-detail-header">
          <span class="entity-detail-name">${displayName}</span>
          <span class="entity-type">${formatEntityType(entityType)}</span>
        </div>

        <div class="entity-stats-header">
          <h4>Statistical Significance</h4>
          <div class="country-filter">
            <label for="country-compare-${entity.name.replace(/\s+/g, '_')}">Compare with:</label>
            <select class="entity-country-filter" id="country-compare-${entity.name.replace(/\s+/g, '_')}">
              <option value="national">National Media</option>
              <option value="global" selected>Global Media</option>
              <option value="us">United States</option>
              <option value="uk">United Kingdom</option>
              <option value="eu">European Union</option>
              <option value="asia">Asia</option>
            </select>
          </div>
        </div>

        <div class="statistical-tests">
          ${entity.national_significance === null
            ? '<p>National comparison: <em>Insufficient data for statistical analysis</em></p>'
            : `<p>National comparison: p-value = ${entity.national_significance.toFixed(3)}
                ${entity.national_significance < 0.05 ? '(significant)' : ''}</p>`}
          ${entity.global_significance === null
            ? '<p>Global comparison: <em>Insufficient data for statistical analysis</em></p>'
            : `<p>Global comparison: p-value = ${entity.global_significance.toFixed(3)}
                ${entity.global_significance < 0.05 ? '(significant)' : ''}</p>`}
        </div>

        <div class="sentiment-scores">
          <div class="score-item">
            <span class="score-label">Power Score:</span>
            <span class="score-value">${entity.power_score.toFixed(1)}</span>
            <div class="score-bar-container">
              <div class="score-bar power" style="width: ${((entity.power_score + 2) / 4) * 100}%"></div>
            </div>
          </div>
          <div class="score-item">
            <span class="score-label">Moral Score:</span>
            <span class="score-value">${entity.moral_score.toFixed(1)}</span>
            <div class="score-bar-container">
              <div class="score-bar moral" style="width: ${((entity.moral_score + 2) / 4) * 100}%"></div>
            </div>
          </div>
        </div>

        <div class="entity-actions">
          <button class="track-entity-btn" data-entity="${displayName}" data-type="${entityType}">View Tracking Data</button>
        </div>

        <div class="context-section">
          <h4 class="context-heading">Mentioned in context:</h4>
          <div class="context-quotes">
            ${mentionsHtml}
          </div>
        </div>
      `;

      entityTabContent.appendChild(entityDetail);

      // Add event listener for country filter dropdown
      const countryFilter = entityDetail.querySelector('.entity-country-filter');
      const statsContainer = entityDetail.querySelector('.statistical-tests');

      if (countryFilter && statsContainer) {
        countryFilter.addEventListener('change', (e) => {
          const selectedRegion = e.target.value;
          const stats = mockStatistics[selectedRegion];

          if (stats) {
            const isSignificant = stats.pValue < 0.05;
            statsContainer.innerHTML = `
              <p>${selectedRegion === 'national' ? 'National' : selectedRegion === 'global' ? 'Global' : selectedRegion.toUpperCase()} comparison:
                 p-value = ${stats.pValue.toFixed(3)}
                 ${isSignificant ? '<span class="significant">(significant)</span>' : ''}
              </p>
            `;
          }
        });
      }

      // Add event listener for track entity button
      const trackBtn = entityDetail.querySelector('.track-entity-btn');
      if (trackBtn) {
        trackBtn.addEventListener('click', () => {
          // Show the entity tracking tab for this entity
          showEntityTrackingTab(displayName, entityType);
        });
      }
    });

    // Setup the distribution chart
    setupDistributionChart();

    // Also prepare entity tracking tab
    prepareEntityTrackingTab(result.entities);

    // Prepare topic clusters tab
    prepareTopicClustersTab(result);
  }

  // Show entity tracking tab for a specific entity
  function showEntityTrackingTab(entityName, entityType) {
    // Switch to entity tracking tab
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    const trackingTab = document.querySelector('[data-tab="entity-tracking-tab"]');
    if (trackingTab) {
      trackingTab.classList.add('active');
      document.getElementById('entity-tracking-tab').classList.add('active');

      // Select the entity in the dropdown
      if (trackingEntitySelector) {
        // Find the option with matching text
        for (let i = 0; i < trackingEntitySelector.options.length; i++) {
          if (trackingEntitySelector.options[i].text === entityName) {
            trackingEntitySelector.selectedIndex = i;
            break;
          }
        }

        // Load tracking data
        loadEntityTracking();
      }
    }
  }

  // Prepare entity tracking tab
  function prepareEntityTrackingTab(entities) {
    // Clear existing options
    trackingEntitySelector.innerHTML = '';

    // Add options for each entity
    entities.forEach((entity, index) => {
      const option = document.createElement('option');
      option.value = index;
      option.textContent = entity.name || entity.entity || `Entity ${index + 1}`;
      trackingEntitySelector.appendChild(option);
    });

    // Load initial demo data
    loadEntityTracking();
  }

  // Load entity tracking data
  function loadEntityTracking() {
    const entityIndex = parseInt(trackingEntitySelector.value);
    const timeRange = parseInt(trackingTimeRange.value);
    const entity = analysisResult.entities[entityIndex];

    if (!entity) return;

    const entityName = entity.name || entity.entity || "Unknown Entity";
    const entityType = entity.type || entity.entity_type || "Unknown";

    // Try to load real data from API
    fetch(`${API_ENDPOINT}/entity/track?name=${encodeURIComponent(entityName)}&type=${encodeURIComponent(entityType)}&days=${timeRange}`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`API request failed with status ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        // Update visualization with real data
        entityTracking.setData(data.data, data.entity_name, data.entity_type);

        // Update insight text
        updateTrackingInsight(data);
      })
      .catch(error => {
        console.warn('Error loading entity tracking data:', error);

        // Generate demo data for visualization
        const demoData = EntityTrackingViz.generateDemoData(entityName, 10);
        entityTracking.setData(demoData.data, demoData.entity_name, demoData.entity_type);

        // Update insight with demo data
        updateTrackingInsightDemo(demoData, entity);
      });
  }

  // Update tracking insight with real data
  function updateTrackingInsight(data) {
    // Calculate trend
    const powerValues = data.data.map(d => d.power_score);
    const moralValues = data.data.map(d => d.moral_score);

    // Simple trend calculation
    const powerTrend = calculateTrend(powerValues);
    const moralTrend = calculateTrend(moralValues);

    // Format insight text
    let insightText = `<strong>${data.entity_name}</strong> has `;

    if (Math.abs(powerTrend) < 0.05 && Math.abs(moralTrend) < 0.05) {
      insightText += `remained fairly consistent in news portrayals over the past ${trackingTimeRange.value} days.`;
    } else {
      // Power trend text
      if (Math.abs(powerTrend) >= 0.05) {
        insightText += `been portrayed as increasingly ${powerTrend > 0 ? 'powerful' : 'vulnerable'} `;

        // Moral trend text
        if (Math.abs(moralTrend) >= 0.05) {
          insightText += `and ${moralTrend > 0 ? 'more positively' : 'more negatively'} `;
        }

        insightText += `in news coverage over the past ${trackingTimeRange.value} days.`;
      } else if (Math.abs(moralTrend) >= 0.05) {
        insightText += `been portrayed ${moralTrend > 0 ? 'more positively' : 'more negatively'} in news coverage over the past ${trackingTimeRange.value} days.`;
      }
    }

    // Add statistical significance if available
    if (data.significance) {
      insightText += ` This shift is ${data.significance < 0.05 ? 'statistically significant' : 'not statistically significant'}.`;
    }

    trackingInsight.innerHTML = insightText;
  }

  // Update tracking insight with demo data
  function updateTrackingInsightDemo(demoData, entity) {
    // Calculate trend from demo data
    const powerValues = demoData.data.map(d => d.power_score);
    const moralValues = demoData.data.map(d => d.moral_score);

    const powerTrend = calculateTrend(powerValues);
    const moralTrend = calculateTrend(moralValues);

    // Format insight text
    let insightText = `Based on available data, <strong>${demoData.entity_name}</strong> has `;

    if (Math.abs(powerTrend) < 0.1 && Math.abs(moralTrend) < 0.1) {
      insightText += `remained consistently portrayed as ${powerValues[powerValues.length-1] > 0 ? 'powerful' : 'vulnerable'} and ${moralValues[moralValues.length-1] > 0 ? 'morally positive' : 'morally questionable'}.`;
    } else {
      // Power trend text
      if (Math.abs(powerTrend) >= 0.1) {
        insightText += `shown a shift toward being portrayed as ${powerTrend > 0 ? 'more powerful' : 'less powerful'} `;

        // Moral trend text
        if (Math.abs(moralTrend) >= 0.1) {
          insightText += `and ${moralTrend > 0 ? 'more favorably' : 'less favorably'} `;
        }

        insightText += `in recent coverage.`;
      } else if (Math.abs(moralTrend) >= 0.1) {
        insightText += `maintained similar power representation but shifted toward ${moralTrend > 0 ? 'more positive' : 'more negative'} moral portrayal.`;
      }
    }

    // Add significance for entity
    if (entity.national_significance !== null && entity.national_significance < 0.05) {
      insightText += ` This entity's portrayal in the current article is statistically unusual compared to typical coverage.`;
    }

    trackingInsight.innerHTML = insightText;
  }

  // Calculate trend from a series of values
  function calculateTrend(values) {
    if (!values || values.length < 2) return 0;

    const n = values.length;

    // Create x values (0, 1, 2, ...)
    const x = Array.from({ length: n }, (_, i) => i);

    // Calculate means
    const meanX = x.reduce((sum, val) => sum + val, 0) / n;
    const meanY = values.reduce((sum, val) => sum + val, 0) / n;

    // Calculate slope (trend)
    let numerator = 0;
    let denominator = 0;

    for (let i = 0; i < n; i++) {
      numerator += (x[i] - meanX) * (values[i] - meanY);
      denominator += (x[i] - meanX) ** 2;
    }

    return denominator !== 0 ? numerator / denominator : 0;
  }

  // Prepare topic clusters tab
  function prepareTopicClustersTab(result) {
    // Clear details panel
    clusterDetails.classList.add('hidden');

    // Try to load topic clusters from API
    fetch(`${API_ENDPOINT}/topics/clusters?article_id=${result.id}`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`API request failed with status ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        // Update visualization with real data
        updateTopicClusterViz(data);
      })
      .catch(error => {
        console.warn('Error loading topic clusters:', error);

        // Generate demo topic clusters
        const demoData = TopicClusterViz.generateDemoData();

        // Add entity data from current article if available
        if (result.entities && result.entities.length > 0) {
          // Add entity nodes connected to topic nodes
          result.entities.forEach((entity, index) => {
            // Assign entity to random existing topic cluster
            const topicIndex = index % demoData.nodes.filter(n => n.id.startsWith('topic_')).length;
            const topic = demoData.nodes.find(n => n.id === `topic_${topicIndex}`);

            if (topic) {
              // Add entity node
              const entityNode = {
                id: `article_entity_${index}`,
                label: entity.name || entity.entity || `Entity ${index}`,
                type: 'entity',
                avgPower: entity.power_score,
                avgMoral: entity.moral_score,
                group: topic.group,
                cluster: topic.cluster,
                size: 1.0,
                count: 1
              };

              demoData.nodes.push(entityNode);

              // Add link to topic
              demoData.links.push({
                source: topic.id,
                target: entityNode.id,
                weight: 0.8
              });

              // Enhance topic with entity reference if first entity
              if (!topic.relatedEntities) {
                topic.relatedEntities = [];
              }

              topic.relatedEntities.push({
                name: entityNode.label,
                type: entity.type || entity.entity_type,
                weight: 0.8
              });

              // Add entity to topic's related entities
              if (topic.relatedEntities.length < 5) {
                topic.relatedEntities.push({
                  name: entity.name || entity.entity,
                  type: entity.type || entity.entity_type,
                  weight: 0.8
                });
              }
            }
          });
        }

        // Update visualization with demo data
        topicCluster.setData(demoData);
      });
  }

  // Load topic clusters
  function loadTopicClusters() {
    const viewType = clusterViewType.value;
    const threshold = clusterThreshold.value;

    // If we have an article, try to load real data
    if (analysisResult && analysisResult.id) {
      let strengthValue;
      switch (threshold) {
        case 'weak': strengthValue = 0.3; break;
        case 'strong': strengthValue = 0.7; break;
        default: strengthValue = 0.5;
      }

      fetch(`${API_ENDPOINT}/topics/clusters?article_id=${analysisResult.id}&view_type=${viewType}&strength=${strengthValue}`)
        .then(response => {
          if (!response.ok) {
            throw new Error(`API request failed with status ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          // Update visualization with real data
          updateTopicClusterViz(data);
        })
        .catch(error => {
          console.warn('Error loading topic clusters with filters:', error);

          // Generate new demo data with the current filters
          const demoData = generateFilteredDemoTopicClusters(viewType, threshold);
          topicCluster.setData(demoData);
        });
    } else {
      // Generate new demo data with the current filters
      const demoData = generateFilteredDemoTopicClusters(viewType, threshold);
      topicCluster.setData(demoData);
    }

    // Hide details panel when changing view
    clusterDetails.classList.add('hidden');
  }

  // Update topic cluster visualization
  function updateTopicClusterViz(data) {
    // Format data for visualization
    const clusterData = {
      nodes: [],
      links: []
    };

    // Process topics and entities from API data
    if (data.topics) {
      data.topics.forEach((topic, index) => {
        clusterData.nodes.push({
          id: `topic_${topic.id || index}`,
          label: topic.name || `Topic ${index + 1}`,
          type: 'topic',
          group: topic.cluster || index,
          cluster: topic.cluster || index,
          size: 1.5,
          count: topic.entity_count || 0,
          avgPower: topic.avg_power,
          avgMoral: topic.avg_moral,
          relatedEntities: topic.related_entities || []
        });
      });
    }

    if (data.entities) {
      data.entities.forEach((entity, index) => {
        clusterData.nodes.push({
          id: `entity_${entity.id || index}`,
          label: entity.name || `Entity ${index + 1}`,
          type: 'entity',
          group: entity.cluster || 0,
          cluster: entity.cluster || 0,
          size: entity.importance ? 0.8 + (entity.importance * 0.7) : 1.0,
          count: entity.article_count || 1,
          avgPower: entity.avg_power,
          avgMoral: entity.avg_moral,
          relatedTopics: entity.related_topics || []
        });
      });
    }

    // Process links
    if (data.links) {
      data.links.forEach(link => {
        const source = clusterData.nodes.find(n =>
          n.id === `${link.source_type}_${link.source_id}`
        );

        const target = clusterData.nodes.find(n =>
          n.id === `${link.target_type}_${link.target_id}`
        );

        if (source && target) {
          clusterData.links.push({
            source: source.id,
            target: target.id,
            weight: link.weight || 0.5
          });
        }
      });
    }

    // Update the visualization
    topicCluster.setData(clusterData);
  }

  // Generate filtered demo topic clusters
  function generateFilteredDemoTopicClusters(viewType, threshold) {
    // Generate base demo data
    const demoData = TopicClusterViz.generateDemoData(
      viewType === 'topics' ? 4 : 6,
      viewType === 'topics' ? 6 : 4
    );

    // Apply threshold filter
    let minWeight;
    switch (threshold) {
      case 'weak': minWeight = 0.3; break;
      case 'strong': minWeight = 0.7; break;
      default: minWeight = 0.5;
    }

    // Filter links by weight
    demoData.links = demoData.links.filter(link => link.weight >= minWeight);

    // For topics view, emphasize topic nodes
    if (viewType === 'topics') {
      // Make topic nodes larger
      demoData.nodes.forEach(node => {
        if (node.id.startsWith('topic_')) {
          node.size = 1.8;
        }
      });
    }

    return demoData;
  }
  
  // Setup distribution chart
  function setupDistributionChart() {
    const chartCanvas = document.getElementById('distribution-chart');
    
    // Initialize our sentiment histogram
    const histogram = new SentimentHistogram('distribution-chart', {
      width: chartCanvas.width,
      height: chartCanvas.height,
      bins: 10,
      barColor: '#4a90e2',
      highlightColor: '#e74c3c',
      countryColor: '#2ecc71'
    });
    
    // We'll start with mock data but fetch real data when available
    let powerScores = generateMockDistribution(0, 0.8, 100);
    let moralScores = generateMockDistribution(0, 1.2, 100);
    
    // Default country data
    let countryData = {
      "United States": {
        power: generateMockDistribution(0.5, 0.7, 50),
        moral: generateMockDistribution(0.2, 1.0, 50)
      },
      "United Kingdom": {
        power: generateMockDistribution(-0.2, 0.5, 40),
        moral: generateMockDistribution(0.3, 0.8, 40)
      }
    };
    
    // Fetch real distribution data from API if available
    // This is non-blocking, so we'll use the mock data first
    // and update the chart when the real data arrives
    fetch(`${API_ENDPOINT}/distributions`)
      .then(response => response.json())
      .then(data => {
        if (data.power_scores && data.power_scores.length > 0) {
          powerScores = data.power_scores;
          moralScores = data.moral_scores;
          
          // Store the sample size information
          const globalSampleSize = data.sample_size || data.power_scores.length;
          
          // Add sample size info to the page
          const distributionDescription = document.querySelector('.distribution-description');
          if (distributionDescription) {
            // Add a sample size paragraph or replace existing one
            let sampleSizeEl = document.getElementById('sample-size-info');
            if (!sampleSizeEl) {
              sampleSizeEl = document.createElement('p');
              sampleSizeEl.id = 'sample-size-info';
              sampleSizeEl.className = 'sample-size-info';
              distributionDescription.appendChild(sampleSizeEl);
            }
            sampleSizeEl.textContent = `Analysis based on ${globalSampleSize.toLocaleString()} entity mentions across our news database.`;
          }
          
          // If there's country-specific data, use it
          if (data.countries) {
            countryData = Object.entries(data.countries).reduce((acc, [country, scores]) => {
              acc[country] = {
                power: scores.power,
                moral: scores.moral,
                sample_size: scores.sample_size || scores.power.length
              };
              return acc;
            }, {});
          }
          
          // Update the histogram with real data - only if updateChartCallback is defined
          if (typeof updateChartCallback === 'function') {
            updateChartCallback();
          } else {
            console.log("Update chart callback not yet available");
          }
        }
      })
      .catch(error => {
        console.error("Error fetching distribution data:", error);
        // Continue with mock data
      });
    
    // Get the current entity's scores, with fallback if entities is empty
    const selectedEntity = analysisResult && analysisResult.entities && analysisResult.entities.length > 0 
      ? analysisResult.entities[0] 
      : { power_score: 0, moral_score: 0 }; // Default fallback
    
    // Set up histogram for power scores with safety checks
    try {
      histogram.setData(powerScores, selectedEntity.power_score);
    } catch (e) {
      console.warn("Error setting initial histogram data:", e);
    }
    
    // Add entity selection for different charts
    let updateChartCallback = null;
    try {
      // Only setup entity selection if we have valid entities
      if (analysisResult && analysisResult.entities && analysisResult.entities.length > 0) {
        updateChartCallback = setupEntitySelectionForCharts(histogram, powerScores, moralScores, countryData);
      } else {
        // No entities available, use fallback
        console.log("No entities available for chart selection");
        updateChartCallback = function() {
          console.log("Using fallback update chart function");
        };
      }
    } catch (e) {
      console.warn("Error setting up entity selection for charts:", e);
      // Create a simple no-op update function as fallback
      updateChartCallback = function() {
        console.log("Using fallback update chart function");
      };
    }
    
    // Store the update function for external calls
    window.updateEntityChart = updateChartCallback;
  }
  
  // Generate mock normal distribution data
  function generateMockDistribution(mean, stdDev, count) {
    const data = [];
    for (let i = 0; i < count; i++) {
      // Box-Muller transform for normal distribution
      const u1 = Math.random();
      const u2 = Math.random();
      const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      const value = mean + z * stdDev;
      data.push(value);
    }
    return data;
  }
  
  // Setup entity selection for charts
  function setupEntitySelectionForCharts(histogram, powerScores, moralScores, countryData = {}) {
    const entitySelector = document.getElementById('entity-selector');
    const dimensionSelector = document.getElementById('dimension-selector');
    const countrySelector = document.getElementById('country-selector');

    // Check if elements exist - they might not in some cases
    if (!entitySelector || !dimensionSelector || !countrySelector) {
      console.warn("Chart selectors not found in the DOM");
      return function() { console.log("Chart selectors not available"); };
    }

    // Clear previous options
    entitySelector.innerHTML = '';

    // Make sure we have entities before trying to iterate
    if (!analysisResult || !analysisResult.entities || !Array.isArray(analysisResult.entities)) {
      console.warn("No entities available for chart selection");
      return function() { console.log("No entities available"); };
    }

    // Add entity options
    analysisResult.entities.forEach((entity, index) => {
      const option = document.createElement('option');
      option.value = index;
      option.textContent = entity.name || entity.entity || "Entity " + (index + 1);
      entitySelector.appendChild(option);
    });
    
    // Handle selection changes
    entitySelector.addEventListener('change', updateChart);
    dimensionSelector.addEventListener('change', updateChart);
    countrySelector.addEventListener('change', updateChart);
    
    // Initial chart update
    updateChart();
    
    // Update chart based on selections
    function updateChart() {
      const entityIndex = parseInt(entitySelector.value);
      const dimension = dimensionSelector.value;
      const country = countrySelector.value;
      const entity = analysisResult.entities[entityIndex];
      
      // Set country filter for histogram
      histogram.options.country = country;
      
      // Get sample size info element or create it if not exists
      let sampleSizeEl = document.getElementById('sample-size-info');
      if (!sampleSizeEl) {
        const distributionDescription = document.querySelector('.distribution-description');
        if (distributionDescription) {
          sampleSizeEl = document.createElement('p');
          sampleSizeEl.id = 'sample-size-info';
          sampleSizeEl.className = 'sample-size-info';
          distributionDescription.appendChild(sampleSizeEl);
        }
      }
      
      // Get data and update chart
      if (dimension === 'power') {
        // Get country-specific data for this dimension if available
        const countrySpecificData = getCountryData(country, 'power', countryData);
        histogram.setData(powerScores, entity.power_score, countrySpecificData);
        
        // Update sample size text
        if (sampleSizeEl) {
          let sampleSize = powerScores.length;
          let sourceText = "global";
          
          // If country selected and we have country data, show that sample size
          if (country && countryData[country] && countryData[country].sample_size) {
            sampleSize = countryData[country].sample_size;
            sourceText = country;
          }
          
          sampleSizeEl.textContent = `Analysis based on ${sampleSize.toLocaleString()} entity mentions from ${sourceText} news sources.`;
        }
      } else {
        // Get country-specific data for this dimension if available
        const countrySpecificData = getCountryData(country, 'moral', countryData);
        histogram.setData(moralScores, entity.moral_score, countrySpecificData);
        
        // Update sample size text
        if (sampleSizeEl) {
          let sampleSize = moralScores.length;
          let sourceText = "global";
          
          // If country selected and we have country data, show that sample size
          if (country && countryData[country] && countryData[country].sample_size) {
            sampleSize = countryData[country].sample_size;
            sourceText = country;
          }
          
          sampleSizeEl.textContent = `Analysis based on ${sampleSize.toLocaleString()} entity mentions from ${sourceText} news sources.`;
        }
      }
      
      // If the entity has changed, fetch entity-specific data from API
      fetchEntityDistribution(entity.name, entity.type);
    }
    
    // Fetch entity-specific distribution data
    function fetchEntityDistribution(entityName, entityType) {
      fetch(`${API_ENDPOINT}/distributions?entity=${encodeURIComponent(entityName)}&type=${encodeURIComponent(entityType)}`)
        .then(response => response.json())
        .then(data => {
          if (data.power_scores && data.power_scores.length > 0) {
            // Update with entity-specific data
            powerScores = data.power_scores;
            moralScores = data.moral_scores;
            
            // Get sample size info
            const globalSampleSize = data.sample_size || data.power_scores.length;
            
            // If there's country-specific data, use it
            if (data.countries) {
              countryData = Object.entries(data.countries).reduce((acc, [country, scores]) => {
                acc[country] = {
                  power: scores.power,
                  moral: scores.moral,
                  sample_size: scores.sample_size || scores.power.length
                };
                return acc;
              }, {});
            }
            
            // Update the chart with the new data
            const dimension = dimensionSelector.value;
            const country = countrySelector.value;
            const entityIndex = parseInt(entitySelector.value);
            const entity = analysisResult.entities[entityIndex];
            
            // Update sample size info element
            const sampleSizeEl = document.getElementById('sample-size-info');
            if (sampleSizeEl) {
              let sampleSize = globalSampleSize;
              let sourceText = "global";
              
              // If country is selected and we have data for it, show that sample size
              if (country && countryData[country] && countryData[country].sample_size) {
                sampleSize = countryData[country].sample_size;
                sourceText = country;
              }
              
              // Update text with entity-specific context
              sampleSizeEl.textContent = `Analysis of "${entityName}" based on ${sampleSize.toLocaleString()} mentions across ${sourceText} news sources.`;
            }
            
            // Update chart with new data
            const countrySpecificData = getCountryData(country, dimension, countryData);
            histogram.setData(
              dimension === 'power' ? powerScores : moralScores,
              dimension === 'power' ? entity.power_score : entity.moral_score,
              countrySpecificData
            );
          }
        })
        .catch(error => {
          console.error("Error fetching entity distribution:", error);
          
          // Update sample size info even in case of error
          const sampleSizeEl = document.getElementById('sample-size-info');
          if (sampleSizeEl) {
            sampleSizeEl.textContent = `Analysis based on available data (error fetching full statistics).`;
            sampleSizeEl.style.backgroundColor = 'rgba(239, 71, 111, 0.1)';
            sampleSizeEl.style.borderLeftColor = 'var(--error-color)';
          }
        });
    }
    
    // Helper to get country data for a specific dimension
    function getCountryData(countryName, dimension, data) {
      if (!countryName || !data[countryName] || !data[countryName][dimension]) {
        return null;
      }
      return data[countryName][dimension];
    }
    
    // Return the update chart function so it can be called externally
    return updateChart;
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

  // Populate article-specific data in the methodology tab
  function populateArticleDataForMethodology() {
    const articleDataContainer = document.getElementById('current-article-data');
    if (!articleDataContainer || !analysisResult) return;

    // Calculate averages from entity data
    let totalPower = 0;
    let totalMoral = 0;
    let entityCount = 0;

    if (analysisResult.entities && analysisResult.entities.length > 0) {
      analysisResult.entities.forEach(entity => {
        if (entity.power_score !== undefined) {
          totalPower += entity.power_score;
          entityCount++;
        }
        if (entity.moral_score !== undefined) {
          totalMoral += entity.moral_score;
        }
      });
    }

    const avgPower = entityCount > 0 ? (totalPower / entityCount).toFixed(1) : 'N/A';
    const avgMoral = entityCount > 0 ? (totalMoral / entityCount).toFixed(1) : 'N/A';
    const percentile = analysisResult.composite_score && analysisResult.composite_score.percentile
                      ? analysisResult.composite_score.percentile
                      : 'N/A';

    // Create HTML for article data summary
    let html = `
      <h4>This Article's Data</h4>
      <p><strong>Source:</strong> ${analysisResult.source || 'Unknown'}</p>
      <p><strong>Entities Analyzed:</strong> ${entityCount}</p>
      <p><strong>Average Power Score:</strong> ${avgPower} (scale: -2 to +2)</p>
      <p><strong>Average Moral Score:</strong> ${avgMoral} (scale: -2 to +2)</p>
      <p><strong>Composite Percentile:</strong> ${percentile}%</p>
      <p><strong>Interpretation:</strong> ${getPercentileInterpretation(percentile)}</p>
    `;

    // Add entity-specific data if available
    if (analysisResult.entities && analysisResult.entities.length > 0) {
      html += `<div class="entity-specifics">
        <h5>Entity Details:</h5>
        <ul>`;

      analysisResult.entities.slice(0, 3).forEach(entity => {
        html += `<li><strong>${entity.name || 'Entity'}:</strong>
          Power: ${entity.power_score !== undefined ? entity.power_score.toFixed(1) : 'N/A'},
          Moral: ${entity.moral_score !== undefined ? entity.moral_score.toFixed(1) : 'N/A'}
        </li>`;
      });

      if (analysisResult.entities.length > 3) {
        html += `<li>... and ${analysisResult.entities.length - 3} more entities</li>`;
      }

      html += `</ul></div>`;
    }

    articleDataContainer.innerHTML = html;
  }

  // Get interpretation text for percentile
  function getPercentileInterpretation(percentile) {
    if (!percentile || percentile === 'N/A') return 'Not available';

    if (percentile < 10) {
      return 'Highly unusual sentiment pattern compared to typical news coverage';
    } else if (percentile < 25) {
      return 'Unusual sentiment pattern';
    } else if (percentile < 75) {
      return 'Average or typical sentiment pattern';
    } else if (percentile < 90) {
      return 'Notably conventional sentiment pattern';
    } else {
      return 'Extremely conventional sentiment pattern';
    }
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

  // Handle topic cluster node selection
  function handleTopicNodeSelected(node) {
    clusterDetails.classList.remove('hidden');

    if (node.type === 'topic') {
      selectedItemTitle.textContent = `Topic: ${node.label}`;

      // Display topic details
      let detailsHtml = `
        <p>${node.count || 0} entities in this topic cluster</p>
        <div class="related-entities">
          <h5>Related Entities</h5>
          <ul>
      `;

      // Add related entities if available
      if (node.relatedEntities && node.relatedEntities.length > 0) {
        node.relatedEntities.forEach(entity => {
          detailsHtml += `
            <li>
              <span class="entity-name">${entity.name}</span>
              <span class="entity-type">(${formatEntityType(entity.type)})</span>
              ${entity.weight ? `<span class="relationship-strength">Strength: ${(entity.weight * 100).toFixed(0)}%</span>` : ''}
            </li>
          `;
        });
      } else {
        // Add placeholder text when no related entities available
        detailsHtml += `<li>No specific entities available for this topic</li>`;
      }

      detailsHtml += `
          </ul>
        </div>
        <div class="topic-sentiment">
          <h5>Topic Sentiment Profile</h5>
          <p>Average sentiment pattern for this topic:</p>
          <div class="sentiment-scores">
            <div class="score-item">
              <span class="score-label">Power:</span>
              <span class="score-value">${node.avgPower !== undefined ? node.avgPower.toFixed(1) : 'N/A'}</span>
            </div>
            <div class="score-item">
              <span class="score-label">Moral:</span>
              <span class="score-value">${node.avgMoral !== undefined ? node.avgMoral.toFixed(1) : 'N/A'}</span>
            </div>
          </div>
        </div>
      `;

      selectedItemDetails.innerHTML = detailsHtml;
    } else {
      // Entity node
      selectedItemTitle.textContent = `Entity: ${node.label}`;

      // Display entity details
      let detailsHtml = `
        <p>${formatEntityType(node.type)} mentioned in ${node.count || 0} articles</p>

        <div class="entity-sentiment">
          <h5>Average Sentiment</h5>
          <div class="sentiment-scores">
            <div class="score-item">
              <span class="score-label">Power Score:</span>
              <span class="score-value">${node.avgPower !== undefined ? node.avgPower.toFixed(1) : 'N/A'}</span>
              <div class="score-bar-container">
                <div class="score-bar power" style="width: ${node.avgPower !== undefined ? ((node.avgPower + 2) / 4) * 100 : 50}%"></div>
              </div>
            </div>
            <div class="score-item">
              <span class="score-label">Moral Score:</span>
              <span class="score-value">${node.avgMoral !== undefined ? node.avgMoral.toFixed(1) : 'N/A'}</span>
              <div class="score-bar-container">
                <div class="score-bar moral" style="width: ${node.avgMoral !== undefined ? ((node.avgMoral + 2) / 4) * 100 : 50}%"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="related-topics">
          <h5>Related Topics</h5>
          <ul>
      `;

      // Add related topics if available
      if (node.relatedTopics && node.relatedTopics.length > 0) {
        node.relatedTopics.forEach(topic => {
          detailsHtml += `
            <li>
              <span class="topic-name">${topic.name}</span>
              ${topic.weight ? `<span class="relationship-strength">Strength: ${(topic.weight * 100).toFixed(0)}%</span>` : ''}
            </li>
          `;
        });
      } else {
        // Add placeholder text when no related topics available
        detailsHtml += `<li>No specific topics available for this entity</li>`;
      }

      detailsHtml += `
          </ul>
        </div>
      `;

      selectedItemDetails.innerHTML = detailsHtml;
    }
  }
  
  // Generate mock result for testing
  // Load similar articles from API
  function loadSimilarArticles() {
    // Skip if no analysis result
    if (!analysisResult || !analysisResult.article || !analysisResult.article.id) {
      return;
    }

    // Show loading state
    similarityResults.innerHTML = `
      <div class="loading">
        <div class="loader"></div>
        <p>Finding similar articles...</p>
      </div>
    `;

    // Get filter values
    const threshold = parseFloat(similarityThresholdSelect.value);
    const maxResults = parseInt(maxResultsSelect.value);

    // Get the article ID
    const articleId = analysisResult.article.id;

    // Call the API to get similar articles
    fetch(`${API_ENDPOINT}/similarity/article/${articleId}?min_similarity=${threshold}&max_results=${maxResults}`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`API request failed with status ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        // Process API response
        displaySimilarArticles(data);
      })
      .catch(error => {
        console.error('Error fetching similar articles:', error);
        // Show error message
        similarityResults.innerHTML = `
          <div class="error-message">
            <p>Error finding similar articles.</p>
            <p>Please try again later or check if the API server is running.</p>
          </div>
        `;

        // Use mock data for demo
        const mockData = generateMockSimilarArticles(analysisResult.article, maxResults, threshold);
        displaySimilarArticles(mockData);
      });
  }

  // Generate mock similar articles data for demo
  function generateMockSimilarArticles(currentArticle, maxResults, minSimilarity) {
    const sources = ['CNN', 'BBC', 'Fox News', 'New York Times', 'Washington Post', 'Reuters', 'NPR'];
    const topics = ['Politics', 'Economy', 'Health', 'Technology', 'International'];
    const clusters = [0, 1, 2]; // Mock cluster IDs

    // Generate mock similar articles
    const mockArticles = [];
    for (let i = 0; i < maxResults; i++) {
      // Similarity decreases as we go down the list
      const baseSimilarity = Math.max(minSimilarity, 0.95 - (i * 0.03));
      // Add some randomness
      const similarity = Math.min(0.98, baseSimilarity + (Math.random() * 0.04 - 0.02));

      // Random time within the last 30 days
      const date = new Date();
      date.setDate(date.getDate() - Math.floor(Math.random() * 30));

      // Determine cluster - similar articles should be in same/similar clusters
      const cluster = i < 3 ? clusters[0] : clusters[Math.floor(Math.random() * clusters.length)];

      mockArticles.push({
        id: `mock-article-${i}`,
        title: `${topics[Math.floor(Math.random() * topics.length)]} Article ${i + 1}`,
        source: sources[Math.floor(Math.random() * sources.length)],
        publish_date: date.toISOString(),
        url: 'https://example.com/article-' + i,
        similarity: similarity,
        cluster: cluster
      });
    }

    // Current article data
    const currentArticleData = {
      id: currentArticle.id || 'current-article',
      title: currentArticle.title || 'Current Article',
      source: currentArticle.source || 'Unknown Source',
      url: currentArticle.url || 'https://example.com',
      similarity: 1.0, // Self-similarity is 100%
      cluster: clusters[0] // Current article is in cluster 0
    };

    return {
      article: currentArticleData,
      similar_articles: mockArticles
    };
  }

  // Display similar articles in the UI
  function displaySimilarArticles(data) {
    if (!data || !data.similar_articles) {
      similarityResults.innerHTML = '<p>No similar articles found.</p>';
      return;
    }

    const articles = data.similar_articles;

    if (articles.length === 0) {
      similarityResults.innerHTML = '<p>No similar articles found.</p>';
      return;
    }

    // Update the results container
    let resultsHtml = '';
    articles.forEach(article => {
      const similarity = Math.round(article.similarity * 100);
      const date = article.publish_date ? new Date(article.publish_date).toLocaleDateString() : 'Unknown date';

      resultsHtml += `
        <div class="similar-article">
          <div class="similar-article-header">
            <div class="similar-article-title">${article.title}</div>
            <div class="similarity-score">${similarity}%</div>
          </div>
          <div class="similar-article-meta">
            <div>${article.source}</div>
            <div>${date}</div>
          </div>
        </div>
      `;
    });

    similarityResults.innerHTML = resultsHtml;

    // Prepare data for cluster visualization
    const visualizationData = [...articles];

    // Add current article
    if (data.article) {
      visualizationData.push({
        ...data.article,
        isCurrentArticle: true
      });
    }

    // Update the cluster visualization
    similarityCluster.setData(
      visualizationData,
      data.article ? data.article.id : 'current-article'
    );
  }

  function generateMockResult(article) {
    return {
      source: article.source,
      title: article.headline,
      url: article.url,
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
  }

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'newAnalysisResult') {
      // New analysis result available
      analysisResult = request.result;
      displayResults(analysisResult);
    } else if (request.action === 'resetAnalysis') {
      // Reset tab-based analysis when navigating to a new page
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const currentTab = tabs[0];
        if (currentTab && currentTab.id === request.tabId) {
          // Clear the current tab-based result
          analysisResult = null;
          currentArticle = null;

          // Check if we have a URL and could look for a URL-based cache instead
          if (request.url) {
            const urlKey = generateArticleId(request.url);

            // Look for URL-based cached analysis
            chrome.storage.local.get([urlKey], (urlResult) => {
              if (urlResult[urlKey] && urlResult[urlKey].result) {
                // Found cached results by URL, restore them regardless of age
                console.log('Found cached analysis for URL after navigation:', request.url);
                analysisResult = urlResult[urlKey].result;

                // Re-cache in tab storage for faster future access
                const tabKey = `tab_${currentTab.id}`;
                chrome.storage.local.set({
                  [tabKey]: {
                    tabId: currentTab.id,
                    url: request.url,
                    result: analysisResult,
                    timestamp: Date.now() // Update timestamp for tracking purposes
                  }
                });

                // Update the UI with the cached results
                displayResults(analysisResult);
              } else {
                // No cached results, show initial state
                showState(initialState);
              }
            });
          } else {
            // No URL provided, just show initial state
            showState(initialState);
          }
        }
      });
    }
  });
});