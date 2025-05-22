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
  analyzeBtn.addEventListener('click', function() {
    startAnalysis(false); // Explicitly pass false for forceReanalysis
  });
  forceAnalyzeBtn.addEventListener('click', function() {
    startAnalysis(true); // Explicitly pass true for forceReanalysis
  });
  retryBtn.addEventListener('click', function() {
    startAnalysis(false); // Explicitly pass false for forceReanalysis
  });
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

      // First check if we have in-memory results for this tab
      const tabKey = `tab_${currentTab.id}`;
      chrome.storage.local.get([tabKey], (result) => {
        if (result[tabKey] && result[tabKey].result) {
          // We have cached results for this tab
          console.log('Found in-memory results for current tab');
          analysisResult = result[tabKey].result;
          displayResults(analysisResult);
        } else {
          // If not in memory, try to retrieve from database via API
          checkForExistingAnalysis(currentTab);
        }
      });
    });
  }

  // Check if this URL has already been analyzed in our database
  function checkForExistingAnalysis(tab) {
    showState(loadingState);
    
    // Show checking message
    const loadingText = document.querySelector('#loading-state p');
    if (loadingText) {
      loadingText.textContent = 'Checking for existing analysis...';
    }
    
    // Call the API to check if this URL has been analyzed before
    fetch(`${API_ENDPOINT}/analysis/by-url?url=${encodeURIComponent(tab.url)}`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`API request failed: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        if (data.exists && data.entities && data.entities.length > 0) {
          console.log('Found existing analysis in database:', data);
          
          // Format the data to match our analysis result structure
          const formattedResult = {
            id: generateArticleId(data.url),
            url: data.url,
            title: data.title,
            source: data.source,
            entities: data.entities,
            quotes: data.quotes || [],
            composite_score: data.composite_score || { percentile: 50 },
            from_database: true
          };
          
          // Save in local storage for faster access
          const tabKey = `tab_${tab.id}`;
          const urlKey = generateArticleId(tab.url);
          
          chrome.storage.local.set({
            [tabKey]: {
              tabId: tab.id,
              url: tab.url,
              result: formattedResult,
              timestamp: Date.now()
            },
            [urlKey]: {
              url: tab.url,
              result: formattedResult,
              timestamp: Date.now()
            }
          });
          
          // Update the global variable and display results
          analysisResult = formattedResult;
          displayResults(analysisResult);
          
          // Log success
          console.log('Successfully loaded and displayed analysis from database');
        } else {
          // No existing analysis, show initial state
          console.log('No existing analysis found for URL:', tab.url);
          showState(initialState);
        }
      })
      .catch(error => {
        console.error('Error checking for existing analysis:', error);
        showState(initialState);
      });
  }
  
  // Start analysis
  function startAnalysis(forceReanalysis = false) {
    console.log(`startAnalysis called with forceReanalysis=${forceReanalysis}`);
    
    // If we already have cached analysis and we're not forcing re-analysis,
    // just display it from memory
    if (analysisResult && analysisResult.from_database && !forceReanalysis) {
      console.log("Using cached analysis from memory");
      displayResults(analysisResult);
      return;
    }
    
    showState(loadingState);
    
    // Update loading message
    const loadingText = document.querySelector('#loading-state p');
    if (loadingText) {
      loadingText.textContent = forceReanalysis ? 
        'Re-analyzing article content...' : 
        'Checking for existing analysis...';
    }

    // Get the current tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const currentTab = tabs[0];
      
      console.log(`Processing tab: ${currentTab.url}`);
      
      // Always check for existing analysis first, unless explicitly forcing reanalysis
      if (!forceReanalysis) {
        console.log("Checking for existing analysis in database");
        // Check if this URL has already been analyzed first
        fetch(`${API_ENDPOINT}/analysis/by-url?url=${encodeURIComponent(currentTab.url)}`)
          .then(response => {
            if (!response.ok) {
              // If the check fails, proceed with extraction
              throw new Error(`API request failed: ${response.status}`);
            }
            return response.json();
          })
          .then(data => {
            if (data.exists && data.entities && data.entities.length > 0) {
              // Found existing analysis - display it directly
              console.log('Found existing analysis in database:', data);
              
              // Format the data to match our analysis result structure
              const formattedResult = {
                id: generateArticleId(data.url),
                url: data.url,
                title: data.title,
                source: data.source,
                entities: data.entities,
                quotes: data.quotes || [],
                composite_score: data.composite_score || { percentile: 50 },
                from_database: true
              };
              
              // Update the global variable and display results
              analysisResult = formattedResult;
              displayResults(analysisResult);
              
              // Cache the result for future use
              cacheAnalysisResult(formattedResult);
            } else {
              console.log("No existing analysis found, proceeding with extraction");
              // No existing analysis, proceed with extraction
              
              if (loadingText) {
                loadingText.textContent = 'Extracting and analyzing article content...';
              }
              
              extractAndAnalyze(currentTab, false);
            }
          })
          .catch(error => {
            console.error('Error checking for existing analysis:', error);
            // If check fails, fall back to extraction
            
            if (loadingText) {
              loadingText.textContent = 'Extracting and analyzing article content...';
            }
            
            extractAndAnalyze(currentTab, false);
          });
      } else {
        // Force reanalysis - skip database check and extract directly
        console.log("Force reanalysis - skipping database check");
        
        if (loadingText) {
          loadingText.textContent = 'Re-analyzing article content...';
        }
        
        extractAndAnalyze(currentTab, true);
      }
    });
  }
  
  // Helper function to extract and analyze content
  function extractAndAnalyze(tab, forceReanalysis) {
    // Use API for content extraction
    tryExtractContent(tab)
      .then(extractedContent => {
        if (extractedContent) {
          // Successfully extracted content from the API
          currentArticle = extractedContent;
          analyzeWithApi(currentArticle, forceReanalysis);
        } else {
          // Show error if API extraction fails
          showError('Content extraction failed. Please make sure the API server is running.');
        }
      })
      .catch(error => {
        console.error("Error with content extraction API:", error);
        showError('Server unreachable: Please make sure the API server is running at ' + API_ENDPOINT);
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
  function analyzeWithApi(article, forceReanalysis = false) {
    // Show loading state
    showState(loadingState);
    
    // Log the article data being sent
    console.log('Sending article to API:', {
      url: article.url,
      source: article.source,
      title: article.headline,
      textLength: article.content ? article.content.length : 0,
      forceReanalysis: forceReanalysis
    });
    
    // Log the API endpoint
    console.log('API endpoint:', `${API_ENDPOINT}/analyze`);
    
    // Create the request payload
    const payload = {
      url: article.url,
      source: article.source,
      title: article.headline,
      text: article.content,
      force_reanalysis: forceReanalysis
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
        newly_analyzed: result.newly_analyzed,
        from_database: result.from_database,
        saved_to_database: result.saved_to_database
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

      // Create a source indicator tag 
      const cacheTag = document.getElementById('cache-indicator');
      if (cacheTag) {
        if (result.from_database) {
          // Retrieved from database
          cacheTag.textContent = 'FROM DB';
          cacheTag.title = 'Analysis retrieved from database';
          cacheTag.style.display = 'inline-block';
          cacheTag.style.backgroundColor = '#4a90e2';
        } else if (result.newly_analyzed) {
          // Fresh analysis
          cacheTag.textContent = 'NEW';
          cacheTag.title = 'Newly analyzed article';
          cacheTag.style.display = 'inline-block';
          cacheTag.style.backgroundColor = '#2ecc71';
        } else if (result.saved_to_database) {
          // Saved to database
          cacheTag.textContent = 'SAVED';
          cacheTag.title = 'Analysis saved to database';
          cacheTag.style.display = 'inline-block';
          cacheTag.style.backgroundColor = '#3498db';
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
      
      // If analysis was from database, add a message
      if (result.from_database) {
        // Add a previously analyzed message at the bottom if it doesn't exist
        let dbNote = document.getElementById('database-note');
        if (!dbNote) {
          dbNote = document.createElement('div');
          dbNote.id = 'database-note';
          dbNote.className = 'database-note';
          dbNote.innerHTML = '<p>This page was previously analyzed and loaded from database.</p>';
          
          // Add force re-analyze button
          const reanalyzeBtn = document.createElement('button');
          reanalyzeBtn.textContent = 'Re-analyze';
          reanalyzeBtn.className = 'small-button';
          reanalyzeBtn.addEventListener('click', () => {
            console.log("Force re-analysis button clicked");
            // Clear any cached results for this URL to ensure a fresh analysis
            analysisResult = null;
            startAnalysis(true); // Pass true to force re-analysis
          });
          dbNote.appendChild(reanalyzeBtn);
          
          // Add to results container
          resultsState.appendChild(dbNote);
        }
      }
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
    let sourceSelector = document.getElementById('source-selector');
    const sampleSizeInfo = document.getElementById('sample-size-info');
    
    // Fix the layout of controls - we'll put each selector on its own row
    const tabControls = document.querySelector('.tab-controls');
    if (tabControls) {
      // Apply new styles to improve layout
      tabControls.style.display = 'flex';
      tabControls.style.flexDirection = 'column';
      tabControls.style.gap = '10px';
      
      // Ensure each control group has proper width
      const controlGroups = tabControls.querySelectorAll('.control-group');
      controlGroups.forEach(group => {
        group.style.width = '100%';
        group.style.display = 'flex';
        group.style.flexDirection = 'column';
        group.style.marginBottom = '8px';
        
        // Make selects take full width
        const select = group.querySelector('select');
        if (select) {
          select.style.width = '100%';
        }
      });
    }
    
    // If sourceSelector doesn't exist, create it
    let comparisonContainer = document.querySelector('.comparison-container');
    if (!comparisonContainer) {
      // Create comparison container and selectors
      comparisonContainer = document.createElement('div');
      comparisonContainer.className = 'comparison-container';
      comparisonContainer.style.width = '100%';
      
      // Add source selector if it doesn't exist
      if (!sourceSelector) {
        const sourceSelectorContainer = document.createElement('div');
        sourceSelectorContainer.className = 'control-group';
        sourceSelectorContainer.style.width = '100%';
        sourceSelectorContainer.innerHTML = `
          <label for="source-selector">Compare with source:</label>
          <select id="source-selector" style="width: 100%;">
            <option value="">All Sources</option>
          </select>
        `;
        comparisonContainer.appendChild(sourceSelectorContainer);
        
        // Add it to the distribution controls
        const controlsContainer = countrySelector ? countrySelector.closest('.tab-controls') : null;
        if (controlsContainer) {
          controlsContainer.appendChild(comparisonContainer);
          sourceSelector = document.getElementById('source-selector');
        }
      }
    }
    
    // Clear and repopulate entity selector
    if (entitySelector) {
      entitySelector.innerHTML = '';
      
      if (!analysisResult || !analysisResult.entities || analysisResult.entities.length === 0) {
        // Show empty state
        if (window.sentimentHistogram) {
          window.sentimentHistogram.drawEmptyState('No entities available');
        }
        entitySelector.innerHTML = '<option value="">No entities available</option>';
        if (sampleSizeInfo) {
          sampleSizeInfo.textContent = 'No data available';
        }
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
    }
    
    // Ensure all selectors exist before adding event listeners
    if (entitySelector) {
      entitySelector.addEventListener('change', updateDistributionChart);
    }
    
    if (dimensionSelector) {
      dimensionSelector.addEventListener('change', updateDistributionChart);
    }
    
    if (countrySelector) {
      countrySelector.addEventListener('change', updateDistributionChart);
    }
    
    if (sourceSelector) {
      sourceSelector.addEventListener('change', updateDistributionChart);
    }
    
    // Load initial data only if we have entities
    if (analysisResult && analysisResult.entities && analysisResult.entities.length > 0) {
      updateDistributionChart();
    }
    
    // Update distribution chart based on selections
    function updateDistributionChart() {
      // Handle cases where elements might not exist
      if (!entitySelector || !dimensionSelector || !window.sentimentHistogram) {
        console.error("Required elements for distribution chart not found");
        return;
      }
      
      // Re-fetch sourceSelector in case it was created after initial load
      sourceSelector = document.getElementById('source-selector');
    
      const selectedEntity = entitySelector.value;
      const selectedDimension = dimensionSelector ? dimensionSelector.value : 'power';
      const selectedCountry = countrySelector ? countrySelector.value : '';
      const selectedSource = sourceSelector ? sourceSelector.value : '';
      
      if (!selectedEntity) {
        window.sentimentHistogram.drawEmptyState('Please select an entity');
        return;
      }
      
      // Ensure we have analysis result with entities
      if (!analysisResult || !analysisResult.entities || !Array.isArray(analysisResult.entities)) {
        window.sentimentHistogram.drawEmptyState('No entity data available');
        return;
      }
      
      const entity = analysisResult.entities.find(e => 
        (e.name === selectedEntity) || (e.entity === selectedEntity)
      );
      
      if (!entity) {
        window.sentimentHistogram.drawEmptyState('Entity data not found');
        return;
      }
      
      // Show loading state
      sampleSizeInfo.textContent = 'Loading distribution data...';
      
      // Build API URL with parameters
      let apiUrl = `${API_ENDPOINT}/stats/sentiment/distribution?entity_name=${encodeURIComponent(selectedEntity)}&dimension=${selectedDimension}`;
      
      // Only add one comparison filter - source takes precedence over country
      if (selectedSource) {
        apiUrl += `&source_id=${selectedSource}`;
      } else if (selectedCountry) {
        apiUrl += `&country=${encodeURIComponent(selectedCountry)}`;
      }
      
      // Fetch distribution data from API
      fetch(apiUrl)
        .then(response => {
          if (!response.ok) {
            // Handle API errors gracefully
            return response.json().then(errorData => {
              throw new Error(errorData.detail || `API request failed: ${response.status}`);
            }).catch(() => {
              throw new Error(`API request failed: ${response.status}`);
            });
          }
          return response.json();
        })
        .then(data => {
          console.log('Distribution API response:', data);
          
          // Check if we have valid data
          if (!data.has_data || !data.values || data.values.length < 5) {
            window.sentimentHistogram.drawEmptyState('No data available for this entity');
            if (sampleSizeInfo) {
              sampleSizeInfo.textContent = `Sample: ${data.sample_size || 0} entity mentions (insufficient for analysis)`;
            }
            return;
          }
          
          // Set the data in the histogram
          // The API now returns comparison_data directly
          const comparisonData = data.comparison_data || null;
          window.sentimentHistogram.setData(
            data.values, 
            data.current_value, 
            comparisonData
          );
          
          // Update HTML title based on comparison data
          const titleElement = document.getElementById('distribution-title');
          if (titleElement) {
            if (comparisonData) {
              const comparisonKey = Object.keys(comparisonData)[0];
              titleElement.textContent = comparisonKey ? 
                `Sentiment Distribution with ${comparisonKey} Comparison` :
                'Sentiment Distribution';
            } else {
              titleElement.textContent = 'Sentiment Distribution';
            }
          }
          
          // Update sample size info
          sampleSizeInfo.textContent = `Sample: ${data.sample_size} entity mentions across ${data.source_count} news sources`;
          
          // Update available sources dropdown if we have source data
          if (data.available_sources && data.available_sources.length > 0 && sourceSelector) {
            // Keep the current selection
            const currentSelection = sourceSelector.value;
            
            // Clear existing options except the first one
            while (sourceSelector.options.length > 1) {
              sourceSelector.remove(1);
            }
            
            // Add new source options
            data.available_sources.forEach(source => {
              const option = document.createElement('option');
              option.value = source.id;
              option.textContent = `${source.name} (${source.count})`;
              sourceSelector.appendChild(option);
            });
            
            // Restore previous selection if it exists in the new options
            if (currentSelection) {
              for (let i = 0; i < sourceSelector.options.length; i++) {
                if (sourceSelector.options[i].value === currentSelection) {
                  sourceSelector.selectedIndex = i;
                  break;
                }
              }
            }
          }
        })
        .catch(error => {
          console.error('Error fetching distribution data:', error);
          
          // Show user-friendly error messages
          if (error.message.includes('Insufficient data')) {
            window.sentimentHistogram.drawEmptyState('Insufficient data for this entity');
            if (sampleSizeInfo) {
              sampleSizeInfo.textContent = 'This entity has too few mentions for statistical analysis';
            }
          } else if (error.message.includes('not found')) {
            window.sentimentHistogram.drawEmptyState('Entity not found in database');
            if (sampleSizeInfo) {
              sampleSizeInfo.textContent = 'This entity is not yet in our database';
            }
          } else {
            window.sentimentHistogram.drawEmptyState('Error loading data');
            if (sampleSizeInfo) {
              sampleSizeInfo.textContent = 'Error: Could not fetch data from server';
            }
          }
        });
    }
  }
  
  // Load similarity data
  function loadSimilarityData() {
    // Show loading state in similarity-results
    const container = document.getElementById('similarity-results');
    const canvasContainer = document.getElementById('similarity-canvas').parentNode;
    
    container.innerHTML = `
      <div class="no-data-message">
        <h3>Feature Not Available</h3>
        <p>The Similar Articles feature requires additional data indexing that has not yet been implemented.</p>
        <p>Please check back later when this feature is fully developed.</p>
      </div>
    `;
    
    // Also show message in the canvas
    if (window.similarityCluster) {
      const canvas = document.getElementById('similarity-canvas');
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#333';
      ctx.textAlign = 'center';
      ctx.font = '14px Arial';
      ctx.fillText('Similar Articles Feature Not Available', canvas.width/2, canvas.height/2 - 10);
      ctx.font = '12px Arial';
      ctx.fillText('This feature requires additional data infrastructure', canvas.width/2, canvas.height/2 + 15);
    }
    
    // Disable the form controls
    const thresholdSelect = document.getElementById('similarity-threshold');
    const maxResultsSelect = document.getElementById('max-results');
    
    if (thresholdSelect) thresholdSelect.disabled = true;
    if (maxResultsSelect) maxResultsSelect.disabled = true;
  }
  
  // Load entity tracking data
  function loadEntityTrackingData() {
    // Get form controls
    const entitySelector = document.getElementById('tracking-entity-selector');
    const timeRangeSelect = document.getElementById('tracking-time-range');
    const insightBox = document.getElementById('tracking-insight');
    const dataInfoContainer = document.createElement('div');
    dataInfoContainer.id = 'tracking-data-info';
    dataInfoContainer.className = 'data-info';
    
    // Add the data info container after the tracking insight box if it doesn't exist
    if (!document.getElementById('tracking-data-info')) {
      insightBox.parentNode.insertBefore(dataInfoContainer, insightBox.nextSibling);
    }
    
    // Clear and populate entity selector
    entitySelector.innerHTML = '';
    
    if (!analysisResult.entities || analysisResult.entities.length === 0) {
      entitySelector.innerHTML = '<option value="">No entities available</option>';
      window.entityTracking.clear();
      insightBox.textContent = 'No entity data available for tracking';
      dataInfoContainer.textContent = '';
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
      const windowSize = 7; // 7-day sliding window
      
      if (!selectedEntity) {
        window.entityTracking.clear();
        insightBox.textContent = 'Select an entity to view sentiment tracking data';
        dataInfoContainer.textContent = '';
        return;
      }
      
      const entity = analysisResult.entities.find(e => 
        (e.name === selectedEntity) || (e.entity === selectedEntity)
      );
      
      if (!entity) {
        window.entityTracking.clear();
        insightBox.textContent = 'Entity data not found';
        dataInfoContainer.textContent = '';
        return;
      }
      
      // Show loading state
      insightBox.textContent = 'Loading entity tracking data...';
      dataInfoContainer.textContent = '';
      
      // Fetch tracking data from API
      fetch(`${API_ENDPOINT}/stats/entity/tracking?entity_name=${encodeURIComponent(selectedEntity)}&days=${timeRange}&window_size=${windowSize}`)
        .then(response => {
          if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          // Check if we have no data at all
          if (!data.has_data || !data.data || data.data.length === 0) {
            window.entityTracking.clear();
            insightBox.textContent = 'No data available for this entity';
            dataInfoContainer.textContent = 'No data points found for this entity in the selected time period';
            return;
          }
          
          // If we have limited data, show a warning but still display it
          const limitedData = data.limited_data || data.data.length < 3;
          
          // Update visualization with real data
          window.entityTracking.setData(
            data.data, 
            data.entity_name, 
            data.entity_type || entity.type || entity.entity_type
          );
          
          // Show data info with warning for limited data
          if (limitedData) {
            dataInfoContainer.innerHTML = `
              <div class="data-warning">Limited data available: analysis may not be statistically significant</div>
              <div>Data from ${data.sample_size} mentions across ${data.source_count} sources over the past ${data.time_period || timeRange + ' days'}</div>
            `;
            dataInfoContainer.querySelector('.data-warning').style.color = '#e67e22';
            dataInfoContainer.querySelector('.data-warning').style.fontWeight = 'bold';
            dataInfoContainer.querySelector('.data-warning').style.marginBottom = '5px';
          } else {
            dataInfoContainer.textContent = `Data from ${data.sample_size} mentions across ${data.source_count} sources over the past ${data.time_period || timeRange + ' days'}`;
          }
          
          // Generate insight text based on the first and last data points
          const points = data.data;
          if (points.length >= 2) {
            const firstPoint = points[0];
            const lastPoint = points[points.length - 1];
            
            const powerChange = lastPoint.power_score - firstPoint.power_score;
            const moralChange = lastPoint.moral_score - firstPoint.moral_score;
            
            // Generate a base insight
            let insightText = '';
            if (Math.abs(powerChange) > Math.abs(moralChange)) {
              insightText = powerChange > 0.3 
                ? `${selectedEntity} is being portrayed as increasingly powerful over time`
                : powerChange < -0.3
                  ? `${selectedEntity} is being portrayed as increasingly vulnerable over time`
                  : `${selectedEntity}'s power portrayal is relatively stable`;
            } else {
              insightText = moralChange > 0.3
                ? `${selectedEntity} is being portrayed more positively over time`
                : moralChange < -0.3
                  ? `${selectedEntity} is being portrayed more negatively over time`
                  : `${selectedEntity}'s moral portrayal is relatively stable`;
            }
            
            // Add a qualifier if the data is limited
            if (limitedData) {
              insightText += ' (based on limited data)';
            }
            
            insightBox.textContent = insightText;
          } else {
            insightBox.textContent = 'Not enough data points to generate meaningful insights';
          }
        })
        .catch(error => {
          console.error('Error fetching entity tracking data:', error);
          window.entityTracking.clear();
          insightBox.textContent = 'Error loading entity tracking data';
          dataInfoContainer.textContent = 'Could not retrieve data from server';
        });
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
    
    // Disable form controls 
    if (viewTypeSelect) viewTypeSelect.disabled = true;
    if (thresholdSelect) thresholdSelect.disabled = true;
    
    // Display not available message
    const canvas = document.getElementById('topic-cluster-canvas');
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#333';
      ctx.textAlign = 'center';
      ctx.font = '14px Arial';
      ctx.fillText('Topic Clusters Feature Not Available', canvas.width/2, canvas.height/2 - 10);
      ctx.font = '12px Arial';
      ctx.fillText('This feature requires additional data indexing and categorization', canvas.width/2, canvas.height/2 + 15);
    }
    
    // Add a message to the details container
    detailsContainer.classList.remove('hidden');
    detailsContainer.innerHTML = `
      <div class="no-data-message">
        <h3>Feature Not Available</h3>
        <p>The Topic Clusters feature requires additional topic modeling that has not yet been implemented.</p>
        <p>Please check back later when this feature is fully developed.</p>
      </div>
    `;
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
});