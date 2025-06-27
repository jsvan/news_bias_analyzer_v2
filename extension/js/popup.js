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
  const backBtn = document.getElementById('back-btn');
  
  const sourceEl = document.querySelector('#article-source span');
  const titleEl = document.getElementById('article-title');
  const entitiesListEl = document.getElementById('entities-list');
  const compositeIndicator = document.getElementById('composite-indicator');
  const compositePercentile = document.getElementById('composite-percentile');
  
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  
  // Info link elements
  const methodologyLink = document.getElementById('methodology-link');
  const distributionInfoLink = document.getElementById('distribution-info-link');
  
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

  // Helper function to extract readable source name from URL
  function extractSourceFromUrl(url) {
    try {
      const domain = new URL(url).hostname.toLowerCase();
      
      // Remove www prefix
      const cleanDomain = domain.replace(/^www\./, '');
      
      // Map domains to readable names
      const sourceMap = {
        'foxnews.com': 'Fox News',
        'cnn.com': 'CNN',
        'nytimes.com': 'New York Times',
        'washingtonpost.com': 'Washington Post',
        'bbc.com': 'BBC',
        'bbc.co.uk': 'BBC',
        'theguardian.com': 'The Guardian',
        'reuters.com': 'Reuters',
        'aljazeera.com': 'Al Jazeera',
        'nbcnews.com': 'NBC News',
        'abcnews.go.com': 'ABC News',
        'cbsnews.com': 'CBS News',
        'usatoday.com': 'USA Today',
        'wsj.com': 'Wall Street Journal',
        'apnews.com': 'Associated Press',
        'npr.org': 'NPR',
        'politico.com': 'Politico',
        'huffpost.com': 'HuffPost',
        'breitbart.com': 'Breitbart',
        'dailymail.co.uk': 'Daily Mail',
        'nypost.com': 'New York Post'
      };
      
      // Check for exact matches first
      if (sourceMap[cleanDomain]) {
        return sourceMap[cleanDomain];
      }
      
      // Check for partial matches
      for (const [domain, name] of Object.entries(sourceMap)) {
        if (cleanDomain.includes(domain.split('.')[0])) {
          return name;
        }
      }
      
      // Default to capitalizing domain without TLD
      const parts = cleanDomain.split('.');
      if (parts.length >= 2) {
        return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
      }
      
      return cleanDomain;
    } catch (error) {
      console.error('Error extracting source from URL:', error);
      return 'Unknown Source';
    }
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
  
  // Info button event listeners
  if (methodologyLink) {
    methodologyLink.addEventListener('click', (e) => {
      e.preventDefault();
      showInfoPopup('Composite Bias Score Methodology', 
        'The composite bias score represents how typical or unusual this article\'s sentiment pattern is compared to articles from this week.\n\n' +
        'It\'s calculated by:\n' +
        '1. Converting each entity\'s power and moral scores to percentiles\n' +
        '2. Measuring statistical deviation from expected values\n' +
        '3. Combining scores using weighted averaging\n' +
        '4. Normalizing to a 0-100 percentile\n\n' +
        'Lower percentiles indicate more unusual sentiment patterns.'
      );
    });
  }
  
  if (distributionInfoLink) {
    distributionInfoLink.addEventListener('click', (e) => {
      e.preventDefault();
      showInfoPopup('Sentiment Distribution Explanation',
        'This histogram shows how the selected entity\'s sentiment score compares to the distribution of scores across news articles.\n\n' +
        'The orange marker shows where this article\'s sentiment falls in the distribution. The percentile is calculated relative to:\n' +
        '• Global data (when no country is selected)\n' +
        '• Country-specific data (when a country is selected)\n\n' +
        'This helps identify whether the sentiment is typical or unusual compared to the selected comparison group.'
      );
    });
  }
  
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
    // First try to use content script for better extraction
    chrome.tabs.sendMessage(tab.id, { action: 'getPageContent' }, (response) => {
      if (chrome.runtime.lastError) {
        console.warn('Content script not available:', chrome.runtime.lastError);
        // Fall back to API extraction
        tryExtractContent(tab)
          .then(extractedContent => {
            if (extractedContent) {
              currentArticle = extractedContent;
              analyzeWithApi(currentArticle, forceReanalysis);
            } else {
              showError('Content extraction failed. Please make sure the API server is running.');
            }
          })
          .catch(error => {
            console.error("Error with content extraction API:", error);
            showError('Server unreachable: Please make sure the API server is running at ' + API_ENDPOINT);
          });
      } else if (response && response.content) {
        // Successfully got content from content script
        console.log('Content extracted via content script');
        currentArticle = {
          url: response.content.url,
          source: response.content.source,
          title: response.content.headline,
          text: response.content.content
        };
        analyzeWithApi(currentArticle, forceReanalysis);
      } else {
        // Content script returned but no content
        console.warn('Content script returned no content');
        showError('Could not extract article content from this page.');
      }
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
        source: data.source || extractSourceFromUrl(data.url),
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
    
    // Ensure all required fields are present
    const url = article.url || '';
    const source = article.source || '';
    const title = article.headline || article.title || '';
    const text = article.content || article.text || '';
    
    console.log('Analyzing with source:', source, 'from article:', article);
    
    // Validate required fields
    if (!url || !source || !title || !text) {
      console.error('Missing required fields:', { url: !!url, source: !!source, title: !!title, text: !!text });
      showError('Missing required article data. Please try refreshing the page.');
      return;
    }
    
    // Log the article data being sent
    console.log('Sending article to API:', {
      url: url,
      source: source,
      title: title,
      textLength: text.length,
      forceReanalysis: forceReanalysis
    });
    
    // Log the API endpoint
    console.log('API endpoint:', `${API_ENDPOINT}/analyze`);
    
    // Create the request payload
    const payload = {
      url: url,
      source: source,
      title: title,
      text: text,
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
      const displaySource = result.source || "Unknown Source";
      console.log('Display results source:', displaySource, 'from result:', result.source);
      sourceEl.textContent = displaySource;
      titleEl.textContent = result.title || "Untitled Article";
      
      // Set composite score
      const percentile = result.composite_score && result.composite_score.percentile 
        ? result.composite_score.percentile 
        : 50; // Default to median if no percentile
        
      compositeIndicator.style.left = `${percentile}%`;
      
      // Format percentile text based on extremeness
      let percentileText;
      if (percentile > 90) {
        percentileText = 'extremely unusual (top 10%)';
      } else if (percentile > 75) {
        percentileText = 'very unusual (top 25%)';
      } else if (percentile > 60) {
        percentileText = 'somewhat unusual';
      } else if (percentile < 25) {
        percentileText = 'typical';
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
      
      // Always add a re-analyze button at the bottom 
      // Remove any existing database note first
      const existingDbNote = document.getElementById('database-note');
      if (existingDbNote) {
        existingDbNote.remove();
      }
      
      // Create new database note with re-analyze button
      const dbNote = document.createElement('div');
      dbNote.id = 'database-note';
      dbNote.className = 'database-note';
      
      // Set message based on whether it's from database or newly analyzed
      if (result.from_database) {
        dbNote.innerHTML = '<p>This page was previously analyzed and loaded from database.</p>';
      } else {
        dbNote.innerHTML = '<p>Analysis complete.</p>';
      }
      
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
    // Initialize distribution histogram container (now shows multiple histograms)
    window.sentimentHistogram = new SentimentHistogram('distribution-charts-container', {
      animate: true,
      showPercentile: true,
      dimension: 'moral' // Default to moral dimension
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
    const dimensionSelector = document.getElementById('dimension-selector');
    
    // Hide the global sample size info since individual histograms have their own
    const globalSampleInfo = document.getElementById('sample-size-info');
    if (globalSampleInfo) {
      globalSampleInfo.style.display = 'none';
    }
    
    if (!analysisResult || !analysisResult.entities || analysisResult.entities.length === 0) {
      // Show empty state
      if (window.sentimentHistogram) {
        window.sentimentHistogram.container.innerHTML = '<div class="empty-message">No entities available</div>';
      }
      return;
    }

    // Set up event listener for dimension selector
    if (dimensionSelector) {
      // Remove any existing listeners
      const newDimensionSelector = dimensionSelector.cloneNode(true);
      dimensionSelector.parentNode.replaceChild(newDimensionSelector, dimensionSelector);
      
      newDimensionSelector.addEventListener('change', () => {
        if (window.sentimentHistogram) {
          window.sentimentHistogram.setDimension(newDimensionSelector.value);
        }
      });
    }

    // Set entities data and render all histograms
    if (window.sentimentHistogram) {
      window.sentimentHistogram.setEntitiesData(analysisResult.entities);
    }
  }
  
  // Load similarity data
  async function loadSimilarityData() {
    // Show loading state in similarity-results
    const container = document.getElementById('similarity-results');
    const canvasContainer = document.getElementById('similarity-canvas').parentNode;
    
    container.innerHTML = `
      <div class="loading">
        <div class="loader"></div>
        <p>Loading similarity data...</p>
      </div>
    `;
    
    try {
      // First, get the source info for the current article
      if (!analysisResult || !analysisResult.source) {
        throw new Error('No source information available');
      }
      
      // Get source ID from source name
      const sourceInfo = await window.sourceSimilarity.getSourceByName(analysisResult.source);
      if (!sourceInfo) {
        throw new Error(`Source "${analysisResult.source}" not found in database`);
      }
      
      // Load similar sources
      const similarSources = await window.sourceSimilarity.loadSourceSimilarityData(sourceInfo.id);
      
      // Display similar sources
      container.innerHTML = window.sourceSimilarity.createSimilarSourcesHTML(
        similarSources, 
        analysisResult.source
      );
      
      // Also load volatile entities
      const volatileEntities = await window.sourceSimilarity.loadVolatileEntities(10);
      
      // Add volatile entities section
      container.innerHTML += window.sourceSimilarity.createVolatileEntitiesHTML(volatileEntities);
      
      // Load and visualize source clusters
      const clusterData = await window.sourceSimilarity.loadSourceClusters(sourceInfo.country);
      window.sourceSimilarity.visualizeSourceClusters(clusterData, 'similarity-canvas');
      
      // Enable the form controls
      const thresholdSelect = document.getElementById('similarity-threshold');
      const maxResultsSelect = document.getElementById('max-results');
      
      if (thresholdSelect) thresholdSelect.disabled = false;
      if (maxResultsSelect) maxResultsSelect.disabled = false;
      
      // Add event listeners for controls
      if (thresholdSelect && !thresholdSelect.hasListener) {
        thresholdSelect.addEventListener('change', () => loadSimilarityData());
        thresholdSelect.hasListener = true;
      }
      
    } catch (error) {
      console.error('Error loading similarity data:', error);
      
      // Show specific error messages based on error type
      let errorTitle = 'Similarity Feature Error';
      let errorMessage = error.message;
      let helpText = '';
      
      if (error.message.includes('501') || error.message.includes('not yet implemented')) {
        errorTitle = 'Feature Not Implemented';
        errorMessage = 'Article similarity clustering is not yet implemented.';
        helpText = 'This feature requires semantic similarity algorithms and dimensionality reduction (t-SNE/UMAP).';
      } else if (error.message.includes('404') || error.message.includes('not found')) {
        errorTitle = 'Source Not Found';
        errorMessage = `Source "${analysisResult.source}" not found in similarity database.`;
        helpText = 'The similarity computation may not have processed this source yet.';
      } else {
        helpText = 'Check that the similarity computation services are running and have processed recent data.';
      }
      
      container.innerHTML = `
        <div class="no-data-message">
          <h3>${errorTitle}</h3>
          <p><strong>Error:</strong> ${errorMessage}</p>
          <p><em>${helpText}</em></p>
        </div>
      `;
      
      // Clear canvas with specific error
      const canvas = document.getElementById('similarity-canvas');
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#e74c3c';
      ctx.textAlign = 'center';
      ctx.font = 'bold 12px Arial';
      ctx.fillText('Similarity Feature Error', canvas.width/2, canvas.height/2 - 10);
      ctx.fillStyle = '#666';
      ctx.font = '10px Arial';
      ctx.fillText('Check console for details', canvas.width/2, canvas.height/2 + 10);
    }
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
    
    async function updateEntityTracking() {
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
      
      // Get source ID if available
      let sourceIdParam = '';
      if (analysisResult && analysisResult.source) {
        try {
          const sourceInfo = await window.sourceSimilarity.getSourceByName(analysisResult.source);
          if (sourceInfo && sourceInfo.id) {
            sourceIdParam = `&source_id=${sourceInfo.id}`;
          }
        } catch (error) {
          console.warn('Could not get source ID:', error);
          // Continue without source ID - will show global data
        }
      }
      
      // Fetch tracking data from API
      fetch(`${API_ENDPOINT}/stats/entity/tracking?entity_name=${encodeURIComponent(selectedEntity)}&days=${timeRange}&window_size=${windowSize}${sourceIdParam}`)
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
          
          // Get source name with fallback - use the URL from analysisResult
          const currentUrl = analysisResult.url || currentArticle?.url;
          const sourceName = analysisResult.source || (currentUrl ? extractSourceFromUrl(currentUrl) : 'Source');
          console.log('Entity tracking source name:', sourceName, 'from URL:', currentUrl, 'analysisResult.source:', analysisResult.source);
          
          // Update visualization with real data
          window.entityTracking.setData(
            data.data, 
            data.entity_name, 
            data.entity_type || entity.type || entity.entity_type,
            sourceName
          );
          
          // Show data info with warning for limited data
          const sourceSpecific = sourceIdParam ? ` (${analysisResult.source} + global averages)` : '';
          if (limitedData) {
            dataInfoContainer.innerHTML = `
              <div class="data-warning">Limited data available: analysis may not be statistically significant</div>
              <div>Data from ${data.sample_size} mentions across ${data.source_count} source${data.source_count === 1 ? '' : 's'} over the past ${data.time_period || timeRange + ' days'}${sourceSpecific}</div>
            `;
            dataInfoContainer.querySelector('.data-warning').style.color = '#e67e22';
            dataInfoContainer.querySelector('.data-warning').style.fontWeight = 'bold';
            dataInfoContainer.querySelector('.data-warning').style.marginBottom = '5px';
          } else {
            dataInfoContainer.textContent = `Data from ${data.sample_size} mentions across ${data.source_count} source${data.source_count === 1 ? '' : 's'} over the past ${data.time_period || timeRange + ' days'}${sourceSpecific}`;
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
  
  // Show info popup
  function showInfoPopup(title, message) {
    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'info-popup-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background-color: rgba(0, 0, 0, 0.5);
      z-index: 1000;
      display: flex;
      align-items: center;
      justify-content: center;
    `;
    
    // Create popup
    const popup = document.createElement('div');
    popup.className = 'info-popup';
    popup.style.cssText = `
      background: white;
      padding: 20px;
      border-radius: 8px;
      max-width: 400px;
      max-height: 300px;
      overflow-y: auto;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
      position: relative;
    `;
    
    // Create close button
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '×';
    closeBtn.style.cssText = `
      position: absolute;
      top: 10px;
      right: 15px;
      border: none;
      background: none;
      font-size: 20px;
      cursor: pointer;
      color: #666;
    `;
    
    // Create content
    const titleEl = document.createElement('h3');
    titleEl.textContent = title;
    titleEl.style.cssText = `
      margin-top: 0;
      margin-bottom: 15px;
      color: #333;
    `;
    
    const messageEl = document.createElement('div');
    messageEl.style.cssText = `
      color: #555;
      line-height: 1.5;
      white-space: pre-line;
    `;
    messageEl.textContent = message;
    
    // Assemble popup
    popup.appendChild(closeBtn);
    popup.appendChild(titleEl);
    popup.appendChild(messageEl);
    overlay.appendChild(popup);
    
    // Add to document
    document.body.appendChild(overlay);
    
    // Close handlers
    const closePopup = () => {
      document.body.removeChild(overlay);
    };
    
    closeBtn.addEventListener('click', closePopup);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closePopup();
      }
    });
    
    // Close on escape key
    const escapeHandler = (e) => {
      if (e.key === 'Escape') {
        closePopup();
        document.removeEventListener('keydown', escapeHandler);
      }
    };
    document.addEventListener('keydown', escapeHandler);
  }
});