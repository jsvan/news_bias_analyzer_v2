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
      
      // Load data for the selected tab
      if (analysisResult) {
        loadTabData(button.dataset.tab);
      }
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
    
    // Initialize visualizations for the detailed view
    initializeVisualizations();

    // Load data for the selected tab
    const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
    loadTabData(activeTab);
  }
  
  // Hide detailed view
  function hideDetailedView() {
    detailedView.classList.add('hidden');
    resultsState.classList.remove('hidden');
  }
  
  // Initialize visualizations
  function initializeVisualizations() {
    // Initialize distribution histogram
    window.sentimentHistogram = new SentimentHistogram('distribution-chart', {
      animate: true,
      showPercentile: true
    });

    // Initialize entity tracking visualization
    window.entityTracking = new EntityTrackingViz('entity-tracking-chart', {
      animate: true,
      showLegend: true
    });

    // Initialize similarity cluster visualization
    window.similarityCluster = new SimilarityClusterViz('similarity-canvas', {
      animate: true
    });

    // Initialize topic cluster visualization
    window.topicCluster = new TopicClusterViz('topic-cluster-canvas', {
      animate: true,
      tooltips: true,
      onNodeSelected: (node) => {
        showClusterDetails(node);
      }
    });
  }

  // Show cluster details when a node is selected
  function showClusterDetails(node) {
    if (!node) return;
    
    const detailsContainer = document.getElementById('cluster-details');
    const titleEl = document.getElementById('selected-item-title');
    const detailsEl = document.getElementById('selected-item-details');
    
    titleEl.textContent = `Selected ${node.type || 'Topic'}: ${node.label}`;
    
    let detailsHTML = '';
    if (node.count) {
      detailsHTML += `<p>Contains ${node.count} entities</p>`;
    }
    
    if (node.entities && node.entities.length) {
      detailsHTML += '<ul class="related-items">';
      node.entities.forEach(entity => {
        detailsHTML += `<li>${entity}</li>`;
      });
      detailsHTML += '</ul>';
    }
    
    detailsEl.innerHTML = detailsHTML || '<p>No additional details available</p>';
    detailsContainer.classList.remove('hidden');
  }

  // Load data for a specific tab
  function loadTabData(tabId) {
    if (!analysisResult || !analysisResult.id) return;
    
    switch(tabId) {
      case 'entity-tab':
        populateEntityDetails();
        break;
      case 'distribution-tab':
        populateDistributionTab();
        break;
      case 'similarity-tab':
        loadSimilarityData();
        break;
      case 'entity-tracking-tab':
        loadEntityTrackingData();
        break;
      case 'topic-cluster-tab':
        loadTopicClusterData();
        break;
      case 'methodology-tab':
        populateMethodologyTab();
        break;
    }
  }
  
  // Populate entity details tab
  function populateEntityDetails() {
    const container = document.querySelector('.entity-details-container');
    container.innerHTML = '';
    
    if (!analysisResult.entities || analysisResult.entities.length === 0) {
      container.innerHTML = '<div class="empty-message">No entity details available for this article</div>';
      return;
    }
    
    analysisResult.entities.forEach(entity => {
      const powerPercentage = ((entity.power_score + 2) / 4) * 100;
      const moralPercentage = ((entity.moral_score + 2) / 4) * 100;
      
      const entityDetails = document.createElement('div');
      entityDetails.className = 'entity-detail-card';
      
      let sigClass = 'not-significant';
      if (entity.national_significance === null) {
        sigClass = 'no-data';
      } else if (entity.national_significance < 0.05) {
        sigClass = 'significant';
      }
      
      const displayName = entity.name || entity.entity || "Unknown Entity";
      const entityType = entity.type || entity.entity_type;
      
      // Format mentions if available
      let mentionsHTML = '';
      if (entity.mentions && entity.mentions.length > 0) {
        mentionsHTML = '<div class="entity-mentions"><h4>Mentions in Article</h4><ul class="mention-list">';
        entity.mentions.forEach(mention => {
          // Highlight the entity name within the text
          const displayName = entity.name || entity.entity || "Unknown Entity";
          let highlightedText = mention.text;
          
          // Only attempt highlight if it's not already a short mention
          if (mention.text.length > displayName.length) {
            // Case-insensitive replace to highlight the entity name
            const regex = new RegExp('\\b(' + displayName.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&') + ')\\b', 'gi');
            highlightedText = mention.text.replace(regex, '<span class="entity-highlight">$1</span>');
          }
          
          mentionsHTML += `
            <li class="mention-item">
              <div class="mention-text"><q>${highlightedText}</q></div>
              <div class="mention-context">${mention.context}</div>
            </li>`;
        });
        mentionsHTML += '</ul></div>';
      }
      
      entityDetails.innerHTML = `
        <div class="entity-header">
          <h3>${displayName}</h3>
          <span class="entity-type-tag">${formatEntityType(entityType)}</span>
        </div>
        
        <div class="sentiment-details">
          <div class="sentiment-bar">
            <div class="bar-label">
              <span>Weak</span>
              <span>Power</span>
              <span>Strong</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill power" style="width: ${powerPercentage}%; left: 0;"></div>
            </div>
            <div class="score-value">${entity.power_score.toFixed(1)}</div>
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
            <div class="score-value">${entity.moral_score.toFixed(1)}</div>
          </div>
        </div>
        
        <div class="statistical-significance ${sigClass}">
          ${entity.national_significance === null
            ? 'Insufficient data for statistical analysis'
            : entity.national_significance < 0.05
              ? `Unusual portrayal (p=${entity.national_significance.toFixed(3)})`
              : 'Typical portrayal'}
        </div>
        
        ${mentionsHTML}
      `;
      
      container.appendChild(entityDetails);
    });
  }
  
  // Populate distribution tab
  function populateDistributionTab() {
    // Get dropdown elements
    const entitySelector = document.getElementById('entity-selector');
    const dimensionSelector = document.getElementById('dimension-selector');
    const countrySelector = document.getElementById('country-selector');
    const sampleSizeInfo = document.getElementById('sample-size-info');
    
    // Clear and repopulate entity selector
    entitySelector.innerHTML = '';
    
    if (!analysisResult.entities || analysisResult.entities.length === 0) {
      // Show empty state
      window.sentimentHistogram.drawEmptyState('No entities available');
      entitySelector.innerHTML = '<option value="">No entities available</option>';
      sampleSizeInfo.textContent = 'No data available';
      return;
    }
    
    // Populate entity dropdown
    analysisResult.entities.forEach(entity => {
      const displayName = entity.name || entity.entity;
      if (!displayName) return;
      
      const option = document.createElement('option');
      option.value = displayName;
      option.textContent = displayName;
      entitySelector.appendChild(option);
    });
    
    // Event listeners for controls
    entitySelector.addEventListener('change', updateDistributionChart);
    dimensionSelector.addEventListener('change', updateDistributionChart);
    countrySelector.addEventListener('change', updateDistributionChart);
    
    // Load initial data
    updateDistributionChart();
    
    // Update distribution chart based on selections
    function updateDistributionChart() {
      const selectedEntity = entitySelector.value;
      const selectedDimension = dimensionSelector.value;
      const selectedCountry = countrySelector.value;
      
      if (!selectedEntity) {
        window.sentimentHistogram.drawEmptyState('Please select an entity');
        return;
      }
      
      const entity = analysisResult.entities.find(e => 
        (e.name === selectedEntity) || (e.entity === selectedEntity)
      );
      
      if (!entity) {
        window.sentimentHistogram.drawEmptyState('Entity data not found');
        return;
      }
      
      // Get the score based on selected dimension
      const score = selectedDimension === 'power' ? entity.power_score : entity.moral_score;
      
      // For demo, generate some random distribution data
      // In real implementation, this would be fetched from the API
      const demoData = generateDemoDistribution(score);
      
      // Update the histogram
      window.sentimentHistogram.setData(demoData.globalData, score, 
        selectedCountry ? { [selectedCountry]: demoData.countryData } : null);
      
      // Update sample size info
      sampleSizeInfo.textContent = `Sample: ${demoData.sampleSize} entity mentions across ${demoData.articleCount} articles`;
      
      if (selectedCountry) {
        window.sentimentHistogram.setCountry(selectedCountry);
      }
    }
    
    // Generate demo distribution for testing
    function generateDemoDistribution(currentValue) {
      // Generate bell-curve-ish distribution around mean
      const mean = 0;
      const stdDev = 1;
      const count = 1000;
      
      const globalData = [];
      for (let i = 0; i < count; i++) {
        // Box-Muller transform for normal distribution
        const u1 = Math.random();
        const u2 = Math.random();
        const z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
        
        // Transform to desired mean and standard deviation
        let value = mean + z0 * stdDev;
        
        // Clamp to [-2, 2] range
        value = Math.max(-2, Math.min(2, value));
        
        globalData.push(value);
      }
      
      // Add more values near the current value to make it less unusual
      for (let i = 0; i < 50; i++) {
        const variance = (Math.random() - 0.5) * 0.5;
        let value = currentValue + variance;
        value = Math.max(-2, Math.min(2, value));
        globalData.push(value);
      }
      
      // Generate country data (subset of global with slight bias)
      const countryData = [];
      const countryBias = 0.3;
      
      for (let i = 0; i < count / 4; i++) {
        const u1 = Math.random();
        const u2 = Math.random();
        const z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
        
        // Add slight bias
        let value = mean + countryBias + z0 * stdDev;
        value = Math.max(-2, Math.min(2, value));
        
        countryData.push(value);
      }
      
      return {
        globalData,
        countryData,
        sampleSize: count,
        articleCount: Math.floor(count / 3)
      };
    }
  }
  
  // Load similarity cluster data
  function loadSimilarityData() {
    // Show loading state in similarity-results
    const container = document.getElementById('similarity-results');
    container.innerHTML = `
      <div class="loading">
        <div class="loader"></div>
        <p>Finding similar articles...</p>
      </div>
    `;
    
    // Get form controls
    const thresholdSelect = document.getElementById('similarity-threshold');
    const maxResultsSelect = document.getElementById('max-results');
    
    // Add event listeners
    thresholdSelect.addEventListener('change', updateSimilarityResults);
    maxResultsSelect.addEventListener('change', updateSimilarityResults);
    
    // For demo, we'd normally call the API here
    // const threshold = parseFloat(thresholdSelect.value);
    // const maxResults = parseInt(maxResultsSelect.value);
    
    // Simulate API response with demo data
    setTimeout(() => {
      const demoData = generateDemoSimilarityData();
      displaySimilarityResults(demoData);
      updateSimilarityVisualization(demoData);
    }, 1000);
    
    function updateSimilarityResults() {
      // This would normally call the API with new parameters
      const demoData = generateDemoSimilarityData();
      displaySimilarityResults(demoData);
      updateSimilarityVisualization(demoData);
    }
    
    function displaySimilarityResults(data) {
      if (!data || data.length === 0) {
        container.innerHTML = '<div class="empty-message">No similar articles found</div>';
        return;
      }
      
      container.innerHTML = '';
      
      data.forEach(article => {
        const similarityPercent = Math.round(article.similarity * 100);
        const articleCard = document.createElement('div');
        articleCard.className = 'similar-article-card';
        
        articleCard.innerHTML = `
          <div class="article-header">
            <div class="similarity-badge">${similarityPercent}%</div>
            <div class="article-source">${article.source}</div>
            <div class="article-date">${formatDate(article.date)}</div>
          </div>
          <h4 class="article-title">${article.title}</h4>
          <p class="article-excerpt">${article.excerpt}</p>
          <a href="${article.url}" class="article-link" target="_blank">Read Article</a>
        `;
        
        container.appendChild(articleCard);
      });
    }
    
    function updateSimilarityVisualization(data) {
      // Prepare data for visualization
      const nodes = data.map(article => ({
        id: article.id,
        title: article.title,
        source: article.source,
        url: article.url,
        similarity: article.similarity
      }));
      
      // Add current article to the data
      nodes.unshift({
        id: analysisResult.id,
        title: analysisResult.title,
        source: analysisResult.source,
        url: analysisResult.url,
        similarity: 1.0
      });
      
      // Update visualization
      window.similarityCluster.setData(nodes, analysisResult.id);
    }
    
    function formatDate(dateStr) {
      const date = new Date(dateStr);
      return date.toLocaleDateString();
    }
    
    function generateDemoSimilarityData() {
      const articles = [];
      const sources = ['CNN', 'Fox News', 'The New York Times', 'The Washington Post', 'BBC', 'Al Jazeera', 'Reuters'];
      
      // Generate 5-15 similar articles
      const count = Math.floor(Math.random() * 10) + 5;
      
      for (let i = 0; i < count; i++) {
        const similarity = Math.random() * 0.3 + 0.65; // 65-95% similarity
        const source = sources[Math.floor(Math.random() * sources.length)];
        const daysAgo = Math.floor(Math.random() * 14); // 0-14 days ago
        
        const date = new Date();
        date.setDate(date.getDate() - daysAgo);
        
        articles.push({
          id: `similar_${i}`,
          title: `Similar article ${i + 1} about this topic`,
          source: source,
          date: date.toISOString(),
          similarity: similarity,
          excerpt: 'This is a summary of the similar article that discusses the same topics and entities with a similar perspective...',
          url: '#', // This would be a real URL in production
          cluster: Math.floor(Math.random() * 3) // Random cluster for visualization
        });
      }
      
      // Sort by similarity, descending
      return articles.sort((a, b) => b.similarity - a.similarity);
    }
  }
  
  // Load entity tracking data
  function loadEntityTrackingData() {
    // Get form controls
    const entitySelector = document.getElementById('tracking-entity-selector');
    const timeRangeSelect = document.getElementById('tracking-time-range');
    const insightBox = document.getElementById('tracking-insight');
    
    // Clear and populate entity selector
    entitySelector.innerHTML = '';
    
    if (!analysisResult.entities || analysisResult.entities.length === 0) {
      entitySelector.innerHTML = '<option value="">No entities available</option>';
      window.entityTracking.clear();
      insightBox.textContent = 'No entity data available for tracking';
      return;
    }
    
    // Populate entity dropdown
    analysisResult.entities.forEach(entity => {
      const displayName = entity.name || entity.entity;
      if (!displayName) return;
      
      const option = document.createElement('option');
      option.value = displayName;
      option.textContent = displayName;
      entitySelector.appendChild(option);
    });
    
    // Add event listeners
    entitySelector.addEventListener('change', updateEntityTracking);
    timeRangeSelect.addEventListener('change', updateEntityTracking);
    
    // Load initial data
    updateEntityTracking();
    
    function updateEntityTracking() {
      const selectedEntity = entitySelector.value;
      const timeRange = parseInt(timeRangeSelect.value);
      
      if (!selectedEntity) {
        window.entityTracking.clear();
        insightBox.textContent = 'Select an entity to view sentiment tracking data';
        return;
      }
      
      const entity = analysisResult.entities.find(e => 
        (e.name === selectedEntity) || (e.entity === selectedEntity)
      );
      
      if (!entity) {
        window.entityTracking.clear();
        insightBox.textContent = 'Entity data not found';
        return;
      }
      
      // Generate demo data (in real app, we'd fetch from API)
      const demoData = generateDemoTrackingData(entity, timeRange);
      
      // Update visualization
      window.entityTracking.setData(
        demoData.data, 
        selectedEntity, 
        entity.type || entity.entity_type || 'Entity'
      );
      
      // Update insight box
      updateInsightText(demoData);
    }
    
    function updateInsightText(trackingData) {
      if (!trackingData || !trackingData.data || trackingData.data.length < 2) {
        insightBox.textContent = 'Insufficient data for trend analysis';
        return;
      }
      
      // Calculate trends
      const firstPoint = trackingData.data[0];
      const lastPoint = trackingData.data[trackingData.data.length - 1];
      
      const powerChange = lastPoint.power_score - firstPoint.power_score;
      const moralChange = lastPoint.moral_score - firstPoint.moral_score;
      
      // Generate insight text
      let insightText = `Over the past ${trackingData.timeRange} days: `;
      
      if (Math.abs(powerChange) > 0.5 || Math.abs(moralChange) > 0.5) {
        if (Math.abs(powerChange) > Math.abs(moralChange)) {
          insightText += powerChange > 0 
            ? `This entity is being portrayed as increasingly powerful (${powerChange.toFixed(1)} change).` 
            : `This entity is being portrayed as increasingly vulnerable (${Math.abs(powerChange).toFixed(1)} change).`;
        } else {
          insightText += moralChange > 0 
            ? `This entity is being portrayed more positively (${moralChange.toFixed(1)} moral score increase).` 
            : `This entity is being portrayed more negatively (${Math.abs(moralChange).toFixed(1)} moral score decrease).`;
        }
      } else {
        insightText += 'The portrayal of this entity has remained relatively stable.';
      }
      
      insightBox.textContent = insightText;
    }
    
    function generateDemoTrackingData(entity, timeRange) {
      const data = [];
      const now = new Date();
      
      // Start values near the entity's current scores
      let powerScore = entity.power_score || 0;
      let moralScore = entity.moral_score || 0;
      
      // Add some trend direction
      const powerTrend = (Math.random() - 0.5) * 0.1;  // Small random trend
      const moralTrend = (Math.random() - 0.5) * 0.1;  // Small random trend
      
      // Generate data points for each day in the range
      for (let i = timeRange; i >= 0; i--) {
        const date = new Date();
        date.setDate(now.getDate() - i);
        
        // Apply trends and some random noise
        powerScore += powerTrend + (Math.random() - 0.5) * 0.3;
        moralScore += moralTrend + (Math.random() - 0.5) * 0.3;
        
        // Clamp to valid range
        powerScore = Math.max(-2, Math.min(2, powerScore));
        moralScore = Math.max(-2, Math.min(2, moralScore));
        
        data.push({
          date: date.toISOString(),
          power_score: powerScore,
          moral_score: moralScore
        });
      }
      
      return {
        entity_name: entity.name || entity.entity,
        entity_type: entity.type || entity.entity_type,
        timeRange: timeRange,
        data: data
      };
    }
  }
  
  // Load topic cluster data
  function loadTopicClusterData() {
    // Get form controls
    const viewTypeSelect = document.getElementById('cluster-view-type');
    const thresholdSelect = document.getElementById('cluster-threshold');
    const detailsContainer = document.getElementById('cluster-details');
    
    // Hide details container initially
    detailsContainer.classList.add('hidden');
    
    // Add event listeners
    viewTypeSelect.addEventListener('change', updateTopicCluster);
    thresholdSelect.addEventListener('change', updateTopicCluster);
    
    // Load initial data
    updateTopicCluster();
    
    function updateTopicCluster() {
      const viewType = viewTypeSelect.value;
      const threshold = thresholdSelect.value;
      
      // Generate demo cluster data
      const demoData = generateDemoClusterData(viewType, threshold);
      
      // Update visualization
      window.topicCluster.setData(demoData);
    }
    
    function generateDemoClusterData(viewType, threshold) {
      // This would normally come from the API
      // For demo, we'll generate random topic clusters
      
      const thresholdValues = {
        'weak': 0.3,
        'medium': 0.5,
        'strong': 0.7
      };
      
      const minStrength = thresholdValues[threshold] || 0.5;
      
      // For topics view
      if (viewType === 'topics') {
        // Use the TopicClusterViz built-in demo data generator
        return TopicClusterViz.generateDemoData(5, 8);
      }
      
      // For entities view
      const entities = [];
      const links = [];
      
      // Use entities from the current article
      if (analysisResult.entities && analysisResult.entities.length > 0) {
        // Add entities from the article
        analysisResult.entities.forEach((entity, index) => {
          entities.push({
            id: `entity_${index}`,
            label: entity.name || entity.entity || `Entity ${index}`,
            type: 'entity',
            group: entity.type === 'country' ? 0 : 
                  entity.type === 'organization' ? 1 : 
                  entity.type === 'person' ? 2 : 3,
            cluster: entity.type === 'country' ? 0 : 
                     entity.type === 'organization' ? 1 : 
                     entity.type === 'person' ? 2 : 3,
            size: 1,
            count: 1
          });
        });
        
        // Add links between entities (demo only)
        for (let i = 0; i < entities.length; i++) {
          for (let j = i + 1; j < entities.length; j++) {
            // Add link with some probability based on threshold
            if (Math.random() < minStrength * 0.8) {
              links.push({
                source: entities[i].id,
                target: entities[j].id,
                weight: Math.random() * (1 - minStrength) + minStrength
              });
            }
          }
        }
      } else {
        // Generate demo entities and links
        for (let i = 0; i < 10; i++) {
          entities.push({
            id: `entity_${i}`,
            label: `Entity ${i}`,
            type: 'entity',
            group: i % 4,
            cluster: i % 4,
            size: Math.random() * 0.5 + 0.8,
            count: Math.floor(Math.random() * 5) + 1
          });
        }
        
        // Add random links
        for (let i = 0; i < entities.length; i++) {
          for (let j = i + 1; j < entities.length; j++) {
            if (Math.random() < minStrength * 0.8) {
              links.push({
                source: entities[i].id,
                target: entities[j].id,
                weight: Math.random() * (1 - minStrength) + minStrength
              });
            }
          }
        }
      }
      
      return { nodes: entities, links: links };
    }
  }
  
  // Populate methodology tab
  function populateMethodologyTab() {
    const container = document.getElementById('current-article-data');
    
    if (!analysisResult) {
      container.innerHTML = '<p>No analysis data available</p>';
      return;
    }
    
    // Create a summary of the current article's analysis
    let html = '<h4>Current Article Analysis Summary</h4>';
    
    // Add composite score
    const percentile = analysisResult.composite_score ? analysisResult.composite_score.percentile : 50;
    html += `<p><strong>Composite Score:</strong> ${percentile}th percentile</p>`;
    
    // Add entity count
    const entityCount = analysisResult.entities ? analysisResult.entities.length : 0;
    html += `<p><strong>Entities Analyzed:</strong> ${entityCount}</p>`;
    
    // Add significant entities
    const significantEntities = analysisResult.entities ? 
      analysisResult.entities.filter(e => e.national_significance && e.national_significance < 0.05) : [];
    
    if (significantEntities.length > 0) {
      html += '<p><strong>Statistically Unusual Portrayals:</strong></p>';
      html += '<ul>';
      significantEntities.forEach(entity => {
        const name = entity.name || entity.entity;
        html += `<li>${name} (p=${entity.national_significance.toFixed(3)})</li>`;
      });
      html += '</ul>';
    } else {
      html += '<p><strong>Statistically Unusual Portrayals:</strong> None detected</p>';
    }
    
    container.innerHTML = html;
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
  
  // Initialize sentiment histogram visualization
  function initializeSentimentHistogram() {
    console.log("Initializing sentiment histogram visualization");
    const entitySelector = document.getElementById('entity-selector');
    const dimensionSelector = document.getElementById('dimension-selector');
    const countrySelector = document.getElementById('country-selector');
    const sampleSizeInfo = document.getElementById('sample-size-info');
    
    // Clear existing options
    entitySelector.innerHTML = '';
    
    // Add entities to the selector
    analysisResult.entities.forEach(entity => {
      const option = document.createElement('option');
      option.value = entity.name || entity.entity;
      option.textContent = entity.name || entity.entity;
      entitySelector.appendChild(option);
    });
    
    // Create histogram instance
    const histogramChart = new SentimentHistogram('distribution-chart');
    
    // Function to update the histogram with current selections
    function updateHistogram() {
      const selectedEntity = entitySelector.value;
      const dimension = dimensionSelector.value;
      const country = countrySelector.value;
      
      // Get entity data
      const entity = analysisResult.entities.find(e => (e.name || e.entity) === selectedEntity);
      if (!entity) return;
      
      // Try to get distribution data from API
      const params = new URLSearchParams({
        entity_name: selectedEntity,
        dimension: dimension
      });
      
      if (country) {
        params.append('country', country);
      }
      
      const apiUrl = `${API_ENDPOINT}/stats/sentiment/distribution?${params.toString()}`;
      
      // Set loading state
      sampleSizeInfo.textContent = 'Loading distribution data...';
      
      fetch(apiUrl)
        .then(response => {
          if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          // Set the data in the histogram
          histogramChart.setData(data.values, data.current_value, data.country_data);
          
          // Update sample size info
          sampleSizeInfo.textContent = `Sample size: ${data.sample_size} mentions across ${data.source_count} sources`;
        })
        .catch(error => {
          console.error('Error fetching distribution data:', error);
          
          // Fall back to generated data if API fails
          const fallbackData = generateMockDistributionData(entity, dimension);
          const currentValue = dimension === 'power' ? entity.power_score : entity.moral_score;
          
          histogramChart.setData(fallbackData.values, currentValue, fallbackData.countryData);
          sampleSizeInfo.textContent = `Sample size: ${fallbackData.sampleSize} mentions across ${fallbackData.sourceCount} sources (fallback data)`;
        });
    }
    
    // Generate mock distribution data as fallback
    function generateMockDistributionData(entity, dimension) {
      const mean = dimension === 'power' ? entity.power_score : entity.moral_score;
      const values = [];
      
      // Generate a normal-ish distribution around the entity's score
      for (let i = 0; i < 100; i++) {
        const randomValue = mean + (Math.random() * 2 - 1);
        values.push(Math.max(-2, Math.min(2, randomValue)));
      }
      
      return {
        values: values,
        countryData: {},
        sampleSize: 100 + Math.floor(Math.random() * 900),
        sourceCount: 10 + Math.floor(Math.random() * 40)
      };
    }
    
    // Set up event listeners
    entitySelector.addEventListener('change', updateHistogram);
    dimensionSelector.addEventListener('change', updateHistogram);
    countrySelector.addEventListener('change', updateHistogram);
    
    // Initial render
    if (entitySelector.options.length > 0) {
      updateHistogram();
    }
  }
  
  // Initialize entity tracking visualization
  function initializeEntityTracking() {
    console.log("Initializing entity tracking visualization");
    const entitySelector = document.getElementById('tracking-entity-selector');
    const timeRangeSelector = document.getElementById('tracking-time-range');
    const insightBox = document.getElementById('tracking-insight');
    
    // Clear existing options
    entitySelector.innerHTML = '';
    
    // Add entities to the selector
    analysisResult.entities.forEach(entity => {
      const option = document.createElement('option');
      option.value = entity.name || entity.entity;
      option.textContent = entity.name || entity.entity;
      entitySelector.appendChild(option);
    });
    
    // Create tracking visualization
    const trackingViz = new EntityTrackingViz('entity-tracking-chart');
    
    // Function to update tracking data
    function updateTracking() {
      const selectedEntity = entitySelector.value;
      const days = parseInt(timeRangeSelector.value);
      
      // Get entity data
      const entity = analysisResult.entities.find(e => (e.name || e.entity) === selectedEntity);
      if (!entity) return;
      
      // Set loading state
      insightBox.textContent = 'Loading entity tracking data...';
      
      // Try to get tracking data from API
      const params = new URLSearchParams({
        entity_name: selectedEntity,
        days: days
      });
      
      const apiUrl = `${API_ENDPOINT}/stats/entity/tracking?${params.toString()}`;
      
      fetch(apiUrl)
        .then(response => {
          if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          // Set data in the visualization
          trackingViz.setData(data.data, data.entity_name, data.entity_type || entity.type || entity.entity_type || 'Unknown');
          
          // Analyze trends for insight text
          const trendAnalysis = analyzeTrends(data.data);
          
          // Update insight text
          insightBox.textContent = `${data.entity_name} shows ${trendAnalysis.powerTrend} trend in power sentiment and ${trendAnalysis.moralTrend} trend in moral sentiment over the past ${days} days across news sources.`;
        })
        .catch(error => {
          console.error('Error fetching entity tracking data:', error);
          
          // Fall back to generated data if API fails
          const fallbackData = EntityTrackingViz.generateDemoData(entity.name || entity.entity, 12);
          
          // Set fallback data
          trackingViz.setData(fallbackData.data, fallbackData.entity_name, entity.type || entity.entity_type || 'Unknown');
          
          // Update insight text with fallback message
          insightBox.textContent = `${entity.name || entity.entity} shows ${Math.random() > 0.5 ? 'an upward' : 'a downward'} trend in ${Math.random() > 0.5 ? 'power' : 'moral'} sentiment over the past ${days} days across news sources. (fallback data)`;
        });
    }
    
    // Helper function to analyze trends in the data
    function analyzeTrends(data) {
      if (!data || data.length < 2) {
        return { powerTrend: 'no clear', moralTrend: 'no clear' };
      }
      
      // Calculate simple linear regression for power scores
      let powerSum = 0;
      data.forEach(point => {
        powerSum += point.power_score;
      });
      const powerAvg = powerSum / data.length;
      
      let powerTrendDirection = 0;
      for (let i = 1; i < data.length; i++) {
        powerTrendDirection += (data[i].power_score - data[i-1].power_score);
      }
      
      // Calculate simple linear regression for moral scores
      let moralSum = 0;
      data.forEach(point => {
        moralSum += point.moral_score;
      });
      const moralAvg = moralSum / data.length;
      
      let moralTrendDirection = 0;
      for (let i = 1; i < data.length; i++) {
        moralTrendDirection += (data[i].moral_score - data[i-1].moral_score);
      }
      
      // Determine trend descriptions
      const powerTrend = powerTrendDirection > 0.1 ? 'an upward' : 
                         powerTrendDirection < -0.1 ? 'a downward' : 'a stable';
                         
      const moralTrend = moralTrendDirection > 0.1 ? 'an upward' : 
                        moralTrendDirection < -0.1 ? 'a downward' : 'a stable';
      
      return { powerTrend, moralTrend };
    }
    
    // Set up event listeners
    entitySelector.addEventListener('change', updateTracking);
    timeRangeSelector.addEventListener('change', updateTracking);
    
    // Initial render
    if (entitySelector.options.length > 0) {
      updateTracking();
    }
  }
  
  // Initialize similarity cluster visualization
  function initializeSimilarityCluster() {
    console.log("Initializing similarity cluster visualization");
    const similarityThreshold = document.getElementById('similarity-threshold');
    const maxResults = document.getElementById('max-results');
    const similarityResults = document.getElementById('similarity-results');
    
    // Create similarity visualization
    const similarityViz = new SimilarityClusterViz('similarity-canvas');
    
    // Function to update similarity data
    function updateSimilarity() {
      const threshold = parseFloat(similarityThreshold.value);
      const limit = parseInt(maxResults.value);
      
      // Set loading state
      similarityResults.innerHTML = '<div class="loading"><div class="loader"></div><p>Finding similar articles...</p></div>';
      
      // Try to get similar articles from API
      const params = new URLSearchParams({
        article_url: analysisResult.url,
        threshold: threshold,
        max_results: limit
      });
      
      const apiUrl = `${API_ENDPOINT}/similarity/articles/similar?${params.toString()}`;
      
      fetch(apiUrl)
        .then(response => {
          if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
          }
          return response.json();
        })
        .then(similarArticles => {
          // Clear previous results
          similarityResults.innerHTML = '';
          
          if (!similarArticles || similarArticles.length === 0) {
            // Show no results message
            similarityResults.innerHTML = '<div class="no-results">No similar articles found.</div>';
            return;
          }
          
          // Add results to the list
          similarArticles.forEach(article => {
            const articleItem = document.createElement('div');
            articleItem.className = 'similar-article-item';
            
            // Format the date if it's in ISO format
            let formattedDate = article.date || article.publish_date;
            try {
              if (formattedDate && formattedDate.includes('T')) {
                formattedDate = new Date(formattedDate).toLocaleDateString();
              }
            } catch (e) {
              console.warn('Error formatting date:', e);
              formattedDate = 'Unknown date';
            }
            
            articleItem.innerHTML = `
              <div class="similarity-score">${Math.round(article.similarity * 100)}%</div>
              <div class="article-info">
                <h4 class="article-title">${article.title}</h4>
                <div class="article-source">${article.source}</div>
                <div class="article-date">${formattedDate}</div>
              </div>
            `;
            
            // Add click handler to open the article
            articleItem.addEventListener('click', () => {
              if (article.url) {
                window.open(article.url, '_blank');
              }
            });
            
            similarityResults.appendChild(articleItem);
          });
          
          // Now get cluster visualization data
          fetchClusterVisualization(similarArticles);
        })
        .catch(error => {
          console.error('Error fetching similar articles:', error);
          
          // Fall back to generated data if API fails
          const fallbackArticles = generateMockSimilarArticles(analysisResult, limit, threshold);
          
          // Clear loading state
          similarityResults.innerHTML = '';
          
          if (fallbackArticles.length === 0) {
            similarityResults.innerHTML = '<div class="no-results">No similar articles found.</div>';
            return;
          }
          
          // Display fallback data
          fallbackArticles.forEach(article => {
            const articleItem = document.createElement('div');
            articleItem.className = 'similar-article-item';
            
            articleItem.innerHTML = `
              <div class="similarity-score">${Math.round(article.similarity * 100)}%</div>
              <div class="article-info">
                <h4 class="article-title">${article.title}</h4>
                <div class="article-source">${article.source}</div>
                <div class="article-date">${article.date} (fallback)</div>
              </div>
            `;
            
            articleItem.addEventListener('click', () => {
              if (article.url) {
                window.open(article.url, '_blank');
              }
            });
            
            similarityResults.appendChild(articleItem);
          });
          
          // Update the visualization with fallback data
          const vizData = [
            {
              id: analysisResult.id || 'current',
              title: analysisResult.title,
              source: analysisResult.source,
              similarity: 1.0
            },
            ...fallbackArticles
          ];
          
          similarityViz.setData(vizData, analysisResult.id || 'current');
        });
    }
    
    // Function to fetch cluster visualization data
    function fetchClusterVisualization(similarArticles) {
      // Try to get cluster data from API
      const params = new URLSearchParams({
        article_url: analysisResult.url,
        cluster_count: 3
      });
      
      const apiUrl = `${API_ENDPOINT}/similarity/articles/cluster?${params.toString()}`;
      
      fetch(apiUrl)
        .then(response => {
          if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
          }
          return response.json();
        })
        .then(clusterData => {
          // Update the visualization with cluster data
          similarityViz.setData(clusterData.nodes, 'source');
        })
        .catch(error => {
          console.error('Error fetching cluster data:', error);
          
          // Fall back to simple visualization with just the similar articles
          const vizData = [
            {
              id: analysisResult.id || 'current',
              title: analysisResult.title,
              source: analysisResult.source,
              similarity: 1.0
            },
            ...similarArticles.map(article => ({
              id: article.id || `similar_${Math.random().toString(36).substring(7)}`,
              title: article.title,
              source: article.source,
              url: article.url,
              similarity: article.similarity,
              cluster: article.cluster || 0
            }))
          ];
          
          similarityViz.setData(vizData, analysisResult.id || 'current');
        });
    }
    
    // Generate mock similar articles as fallback
    function generateMockSimilarArticles(article, limit, threshold) {
      const result = [];
      const sourceDomains = [
        'nytimes.com',
        'washingtonpost.com',
        'cnn.com',
        'foxnews.com',
        'bbc.com',
        'reuters.com',
        'apnews.com',
        'nbcnews.com',
        'politico.com'
      ];
      
      const currentDate = new Date();
      
      for (let i = 0; i < limit; i++) {
        // Random similarity score above threshold
        const similarity = threshold + (Math.random() * (1 - threshold));
        
        // Create random date within past 30 days
        const randomDaysAgo = Math.floor(Math.random() * 30);
        const date = new Date(currentDate);
        date.setDate(date.getDate() - randomDaysAgo);
        
        // Create a mock article
        result.push({
          id: `similar_${i}`,
          title: `Similar article about ${article.title.split(' ').slice(0, 3).join(' ')}...`,
          source: sourceDomains[Math.floor(Math.random() * sourceDomains.length)],
          url: `https://${sourceDomains[Math.floor(Math.random() * sourceDomains.length)]}/article-${i}`,
          date: date.toLocaleDateString(),
          similarity: similarity,
          // For cluster visualization
          cluster: Math.floor(Math.random() * 3)
        });
      }
      
      // Sort by similarity (highest first)
      return result.sort((a, b) => b.similarity - a.similarity);
    }
    
    // Set up event listeners
    similarityThreshold.addEventListener('change', updateSimilarity);
    maxResults.addEventListener('change', updateSimilarity);
    
    // Initial render
    updateSimilarity();
  }
  
  // Initialize topic cluster visualization
  function initializeTopicCluster() {
    console.log("Initializing topic cluster visualization");
    const viewType = document.getElementById('cluster-view-type');
    const threshold = document.getElementById('cluster-threshold');
    const clusterDetails = document.getElementById('cluster-details');
    const selectedItemTitle = document.getElementById('selected-item-title');
    const selectedItemDetails = document.getElementById('selected-item-details');
    
    // Create topic cluster visualization
    const topicClusterViz = new TopicClusterViz('topic-cluster-canvas', {
      onNodeSelected: (node) => {
        // Update details panel when a node is selected
        clusterDetails.classList.remove('hidden');
        selectedItemTitle.textContent = node.label;
        
        // Show different details based on node type
        if (node.type === 'topic') {
          selectedItemDetails.innerHTML = `
            <p>Topic cluster with ${node.count || 0} related entities</p>
            <ul>
              ${(node.related || []).map(rel => `<li>${rel}</li>`).join('')}
            </ul>
          `;
        } else {
          selectedItemDetails.innerHTML = `
            <p>${node.type || node.entity_type || 'Entity'}</p>
            <div class="entity-sentiment">
              <div>Power: ${node.power || 'N/A'}</div>
              <div>Moral: ${node.moral || 'N/A'}</div>
            </div>
          `;
        }
      }
    });
    
    // Function to update the cluster visualization
    function updateCluster() {
      const viewTypeValue = viewType.value;
      const thresholdValue = threshold.value;
      
      // Hide details panel while loading
      clusterDetails.classList.add('hidden');
      
      // Try to get topic cluster data from API
      const params = new URLSearchParams({
        article_url: analysisResult.url,
        view_type: viewTypeValue,
        threshold: thresholdValue
      });
      
      const apiUrl = `${API_ENDPOINT}/stats/topics/cluster?${params.toString()}`;
      
      fetch(apiUrl)
        .then(response => {
          if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
          }
          return response.json();
        })
        .then(clusterData => {
          // Update the visualization with cluster data
          topicClusterViz.setData(clusterData);
        })
        .catch(error => {
          console.error('Error fetching topic cluster data:', error);
          
          // Fall back to generated data if API fails
          const fallbackData = generateTopicClusters(analysisResult.entities, viewTypeValue, thresholdValue);
          
          // Update the visualization with fallback data
          topicClusterViz.setData(fallbackData);
        });
    }
    
    // Generate mock topic clusters based on entities (fallback)
    function generateTopicClusters(entities, viewType, threshold) {
      // Map threshold value to strength
      const strengthMap = {
        'weak': 0.3,
        'medium': 0.5,
        'strong': 0.7
      };
      
      // For demonstration, we'll use the demo data generator
      const topicCount = Math.min(4, Math.max(2, Math.ceil(entities.length / 3)));
      const entitiesPerTopic = Math.min(8, Math.max(entities.length, 5));
      
      return TopicClusterViz.generateDemoData(topicCount, entitiesPerTopic);
    }
    
    // Set up event listeners
    viewType.addEventListener('change', updateCluster);
    threshold.addEventListener('change', updateCluster);
    
    // Initial render
    updateCluster();
  }
});