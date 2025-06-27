// Tab Manager - Handles tab navigation and content loading
import { appState } from '../state/app-state.js';
import { ApiService } from '../services/api-service.js';
import { ErrorHandler } from '../utils/error-handler.js';

export class TabManager {
  constructor() {
    this.apiService = new ApiService();
    this.activeTab = 'entity-tab';
    this.tabButtons = document.querySelectorAll('.tab-btn');
    this.tabContents = document.querySelectorAll('.tab-content');
    
    this.setupEventListeners();
    this.initializeVisualizations();
  }

  setupEventListeners() {
    // Tab navigation
    this.tabButtons.forEach(button => {
      button.addEventListener('click', () => {
        this.switchTab(button.dataset.tab);
      });
    });

    // Listen for analysis result changes
    appState.subscribe('analysisResult', (result) => {
      if (result) {
        this.onAnalysisResultChanged(result);
      }
    });

    // Listen for active tab changes from state
    appState.subscribe('activeTab', (tabId) => {
      this.updateTabUI(tabId);
    });
  }

  switchTab(tabId) {
    if (this.activeTab === tabId) return; // Already active
    
    this.activeTab = tabId;
    appState.setActiveTab(tabId);
    
    // Update UI
    this.updateTabUI(tabId);
    
    // Load tab data
    const analysisResult = appState.getAnalysisResult();
    if (analysisResult) {
      this.loadTabData(tabId, analysisResult);
    }
  }

  updateTabUI(tabId) {
    // Remove active class from all tabs
    this.tabButtons.forEach(btn => btn.classList.remove('active'));
    this.tabContents.forEach(content => content.classList.remove('active'));

    // Add active class to current tab
    const activeButton = document.querySelector(`[data-tab="${tabId}"]`);
    const activeContent = document.getElementById(tabId);
    
    if (activeButton) activeButton.classList.add('active');
    if (activeContent) activeContent.classList.add('active');
  }

  onAnalysisResultChanged(result) {
    // Load data for currently active tab
    if (this.activeTab && result) {
      this.loadTabData(this.activeTab, result);
    }
  }

  async loadTabData(tabId, analysisResult) {
    if (!analysisResult || !analysisResult.id) return;
    
    try {
      switch(tabId) {
        case 'entity-tab':
          this.populateEntityDetails(analysisResult);
          break;
        case 'distribution-tab':
          this.populateDistributionTab(analysisResult);
          break;
        case 'similarity-tab':
          await this.loadSimilarityData(analysisResult);
          break;
        case 'entity-tracking-tab':
          this.loadEntityTrackingData(analysisResult);
          break;
        case 'topic-cluster-tab':
          this.loadTopicClusterData(analysisResult);
          break;
        case 'methodology-tab':
          this.populateMethodologyTab(analysisResult);
          break;
      }
    } catch (error) {
      console.error(`Error loading data for tab ${tabId}:`, error);
      ErrorHandler.showError(`Failed to load ${tabId} data`);
    }
  }

  // Entity tab
  populateEntityDetails(analysisResult) {
    const container = document.querySelector('.entity-details-container');
    if (!container) return;
    
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
          const highlightedText = this.highlightEntityInText(mention.text, displayName);
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
          <span class="entity-type-tag">${this.formatEntityType(entityType)}</span>
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

  // Distribution tab
  populateDistributionTab(analysisResult) {
    const dimensionSelector = document.getElementById('dimension-selector');
    
    // Hide the global sample size info since individual histograms have their own
    const globalSampleInfo = document.getElementById('sample-size-info');
    if (globalSampleInfo) {
      globalSampleInfo.style.display = 'none';
    }
    
    if (!analysisResult || !analysisResult.entities || analysisResult.entities.length === 0) {
      if (window.sentimentHistogram) {
        window.sentimentHistogram.container.innerHTML = '<div class="empty-message">No entities available</div>';
      }
      return;
    }

    // Set up event listener for dimension selector
    if (dimensionSelector) {
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

  // Similarity tab
  async loadSimilarityData(analysisResult) {
    const container = document.getElementById('similarity-results');
    
    if (!container) return;
    
    container.innerHTML = `
      <div class="loading">
        <div class="loader"></div>
        <p>Loading similar articles...</p>
      </div>
    `;
    
    try {
      if (!analysisResult || !analysisResult.id) {
        container.innerHTML = `
          <div class="no-data-message">
            <h3>No Article Data</h3>
            <p>Unable to find similar articles without article analysis data.</p>
          </div>
        `;
        return;
      }

      // Fetch similar articles from API
      const similarData = await this.apiService.getSimilarArticles(analysisResult.id, {
        limit: 8,
        daysWindow: 3,
        minEntityOverlap: 0.3
      });

      if (!similarData.similar_articles || similarData.similar_articles.length === 0) {
        container.innerHTML = `
          <div class="no-data-message">
            <h3>No Similar Articles Found</h3>
            <p>No articles found covering similar topics in the same time period.</p>
            <p class="tip">Try visiting news sites that covered the same story to build the database.</p>
          </div>
        `;
        return;
      }

      // Display similar articles
      this.renderSimilarArticles(container, similarData, analysisResult);

    } catch (error) {
      console.error('Error loading similar articles:', error);
      container.innerHTML = `
        <div class="error-message">
          <h3>Error Loading Similar Articles</h3>
          <p>Failed to load similar articles: ${error.message}</p>
          <p class="tip">This feature requires articles to be analyzed and stored in the database.</p>
        </div>
      `;
    }
  }

  renderSimilarArticles(container, similarData, currentAnalysis) {
    const { similar_articles } = similarData;
    
    let html = `
      <div class="similar-articles-header">
        <h3>Similar Articles (${similar_articles.length} found)</h3>
        <p class="description">Articles covering similar topics, ordered by sentiment divergence</p>
      </div>
      <div class="similar-articles-list">
    `;

    similar_articles.forEach((article, index) => {
      const sentimentClass = this.getSentimentDivergenceClass(article.sentiment_similarity);
      const publishDate = new Date(article.publish_date).toLocaleDateString();
      
      // Find overlapping entities for display
      const currentEntities = new Set(currentAnalysis.entities.map(e => e.name.toLowerCase()));
      const overlappingEntities = article.entities.filter(e => 
        currentEntities.has(e.name.toLowerCase())
      ).slice(0, 3); // Show max 3 overlapping entities

      html += `
        <div class="similar-article-card ${sentimentClass}" data-article-id="${article.article_id}">
          <div class="article-header">
            <div class="article-meta">
              <span class="source-name">${article.source_name}</span>
              <span class="publish-date">${publishDate}</span>
            </div>
            <div class="similarity-scores">
              <span class="entity-overlap" title="Entity Overlap">
                ${(article.entity_overlap * 100).toFixed(0)}% overlap
              </span>
              <span class="sentiment-divergence ${sentimentClass}" title="Sentiment Divergence">
                ${article.sentiment_similarity.toFixed(1)} divergence
              </span>
            </div>
          </div>
          
          <h4 class="article-title">${article.title}</h4>
          
          <div class="overlapping-entities">
            <span class="entities-label">Shared entities:</span>
            ${overlappingEntities.map(entity => `
              <span class="entity-tag" title="Power: ${entity.power_score.toFixed(1)}, Moral: ${entity.moral_score.toFixed(1)}">
                ${entity.name}
              </span>
            `).join('')}
            ${article.entities.length > 3 ? `<span class="more-entities">+${article.entities.length - 3} more</span>` : ''}
          </div>
          
          <div class="article-actions">
            <button class="view-article-btn" data-url="${article.url}">View Article</button>
            <button class="compare-sentiment-btn" data-article-id="${article.article_id}">Compare Sentiment</button>
          </div>
        </div>
      `;
    });

    html += `
      </div>
      <div class="similarity-legend">
        <h4>How to Read This</h4>
        <div class="legend-items">
          <div class="legend-item">
            <span class="legend-color low-divergence"></span>
            <span>Low Divergence: Similar sentiment patterns</span>
          </div>
          <div class="legend-item">
            <span class="legend-color medium-divergence"></span>
            <span>Medium Divergence: Somewhat different perspectives</span>
          </div>
          <div class="legend-item">
            <span class="legend-color high-divergence"></span>
            <span>High Divergence: Very different sentiment patterns</span>
          </div>
        </div>
        <p class="note">Articles are sorted by sentiment divergence (highest first) to show different perspectives on the same story.</p>
      </div>
    `;

    container.innerHTML = html;
    
    // Add event listeners
    this.setupSimilarArticlesEventListeners(container);
  }

  getSentimentDivergenceClass(sentimentSimilarity) {
    if (sentimentSimilarity < 1.0) return 'low-divergence';
    if (sentimentSimilarity < 2.0) return 'medium-divergence';
    return 'high-divergence';
  }

  setupSimilarArticlesEventListeners(container) {
    // View article buttons
    container.querySelectorAll('.view-article-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const url = e.target.getAttribute('data-url');
        if (url) {
          chrome.tabs.create({ url: url });
        }
      });
    });

    // Compare sentiment buttons
    container.querySelectorAll('.compare-sentiment-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const articleId = e.target.getAttribute('data-article-id');
        // TODO: Implement sentiment comparison modal/view
        console.log('Compare sentiment for article:', articleId);
        // For now, just show a placeholder
        alert('Sentiment comparison feature coming soon!');
      });
    });
  }

  // Entity tracking tab
  loadEntityTrackingData(analysisResult) {
    const entitySelector = document.getElementById('tracking-entity-selector');
    const timeRangeSelect = document.getElementById('tracking-time-range');
    const insightBox = document.getElementById('tracking-insight');
    
    if (!entitySelector || !timeRangeSelect || !insightBox) return;
    
    // Clear and populate entity selector
    entitySelector.innerHTML = '';
    
    if (!analysisResult.entities || analysisResult.entities.length === 0) {
      entitySelector.innerHTML = '<option value="">No entities available</option>';
      if (window.entityTracking) {
        window.entityTracking.clear();
      }
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
    
    // Set up event listeners
    entitySelector.addEventListener('change', () => this.updateEntityTracking(analysisResult));
    timeRangeSelect.addEventListener('change', () => this.updateEntityTracking(analysisResult));
    
    // Load initial data
    this.updateEntityTracking(analysisResult);
  }

  async updateEntityTracking(analysisResult) {
    const entitySelector = document.getElementById('tracking-entity-selector');
    const timeRangeSelect = document.getElementById('tracking-time-range');
    const insightBox = document.getElementById('tracking-insight');
    
    const selectedEntity = entitySelector.value;
    const timeRange = parseInt(timeRangeSelect.value);
    const windowSize = 7; // 7-day sliding window
    
    if (!selectedEntity) {
      if (window.entityTracking) {
        window.entityTracking.clear();
      }
      insightBox.textContent = 'Select an entity to view sentiment tracking data';
      return;
    }
    
    const entity = analysisResult.entities.find(e => 
      (e.name === selectedEntity) || (e.entity === selectedEntity)
    );
    
    if (!entity) {
      if (window.entityTracking) {
        window.entityTracking.clear();
      }
      insightBox.textContent = 'Entity data not found';
      return;
    }
    
    insightBox.textContent = 'Loading entity tracking data...';
    
    try {
      const data = await this.apiService.getEntityTracking(selectedEntity, timeRange, windowSize);
      
      if (!data.has_data || !data.data || data.data.length === 0) {
        if (window.entityTracking) {
          window.entityTracking.clear();
        }
        insightBox.textContent = 'No data available for this entity';
        return;
      }
      
      // Get source name with fallback - use the URL from analysisResult
      const currentUrl = analysisResult.url;
      const sourceName = analysisResult.source || (currentUrl ? this.extractSourceFromUrl(currentUrl) : 'Source');
      console.log('Entity tracking source name:', sourceName, 'from URL:', currentUrl, 'analysisResult.source:', analysisResult.source);
      
      // Update visualization
      if (window.entityTracking) {
        window.entityTracking.setData(
          data.data, 
          data.entity_name, 
          data.entity_type || entity.type || entity.entity_type,
          sourceName
        );
      }
      
      // Generate insight
      this.generateEntityTrackingInsight(data, selectedEntity, insightBox);
      
    } catch (error) {
      console.error('Error fetching entity tracking data:', error);
      if (window.entityTracking) {
        window.entityTracking.clear();
      }
      insightBox.textContent = 'Error loading entity tracking data';
    }
  }

  generateEntityTrackingInsight(data, entityName, insightBox) {
    const points = data.data;
    if (points.length >= 2) {
      const firstPoint = points[0];
      const lastPoint = points[points.length - 1];
      
      const powerChange = lastPoint.power_score - firstPoint.power_score;
      const moralChange = lastPoint.moral_score - firstPoint.moral_score;
      
      let insightText = '';
      if (Math.abs(powerChange) > Math.abs(moralChange)) {
        insightText = powerChange > 0.3 
          ? `${entityName} is being portrayed as increasingly powerful over time`
          : powerChange < -0.3
            ? `${entityName} is being portrayed as increasingly vulnerable over time`
            : `${entityName}'s power portrayal is relatively stable`;
      } else {
        insightText = moralChange > 0.3
          ? `${entityName} is being portrayed more positively over time`
          : moralChange < -0.3
            ? `${entityName} is being portrayed more negatively over time`
            : `${entityName}'s moral portrayal is relatively stable`;
      }
      
      if (data.limited_data) {
        insightText += ' (based on limited data)';
      }
      
      insightBox.textContent = insightText;
    } else {
      insightBox.textContent = 'Not enough data points to generate meaningful insights';
    }
  }

  // Topic cluster tab
  loadTopicClusterData(analysisResult) {
    const canvas = document.getElementById('topic-cluster-canvas');
    const detailsContainer = document.getElementById('cluster-details');
    
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#333';
      ctx.textAlign = 'center';
      ctx.font = '14px Arial';
      ctx.fillText('Topic Clusters Feature Not Available', canvas.width/2, canvas.height/2 - 10);
      ctx.font = '12px Arial';
      ctx.fillText('This feature requires additional topic modeling', canvas.width/2, canvas.height/2 + 15);
    }
    
    if (detailsContainer) {
      detailsContainer.classList.remove('hidden');
      detailsContainer.innerHTML = `
        <div class="no-data-message">
          <h3>Feature Not Available</h3>
          <p>The Topic Clusters feature requires additional topic modeling that has not yet been implemented.</p>
          <p>Please check back later when this feature is fully developed.</p>
        </div>
      `;
    }
  }

  // Methodology tab
  populateMethodologyTab(analysisResult) {
    const container = document.getElementById('current-article-data');
    
    if (!container || !analysisResult) {
      return;
    }
    
    let html = '<h4>Current Article Analysis Summary</h4>';
    
    const percentile = analysisResult.composite_score ? analysisResult.composite_score.percentile : 50;
    html += `<p><strong>Composite Score:</strong> ${percentile}th percentile</p>`;
    
    const entityCount = analysisResult.entities ? analysisResult.entities.length : 0;
    html += `<p><strong>Entities Analyzed:</strong> ${entityCount}</p>`;
    
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

  // Visualization initialization
  initializeVisualizations() {
    // Initialize sentiment histogram
    if (document.getElementById('distribution-charts-container')) {
      window.sentimentHistogram = new SentimentHistogram('distribution-charts-container', {
        animate: true,
        showPercentile: true,
        dimension: 'moral'
      });
    }

    // Initialize entity tracking
    if (document.getElementById('entity-tracking-chart')) {
      window.entityTracking = new EntityTrackingViz('entity-tracking-chart', {
        animate: true,
        showLegend: true
      });
    }

    // Initialize similarity cluster
    if (document.getElementById('similarity-canvas')) {
      window.similarityCluster = new SimilarityClusterViz('similarity-canvas', {
        animate: true
      });
    }

    // Initialize topic cluster
    if (document.getElementById('topic-cluster-canvas')) {
      window.topicCluster = new TopicClusterViz('topic-cluster-canvas', {
        animate: true,
        tooltips: true
      });
    }
  }

  // Utility methods
  highlightEntityInText(text, entityName) {
    if (text.length <= entityName.length) {
      return text;
    }
    
    const regex = new RegExp('\\b(' + entityName.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&') + ')\\b', 'gi');
    return text.replace(regex, '<span class="entity-highlight">$1</span>');
  }

  formatEntityType(type) {
    if (!type) return 'Unknown';

    switch(type) {
      case 'person': return 'Person';
      case 'country': return 'Country';
      case 'organization': return 'Organization';
      case 'political_party': return 'Political Party';
      default: return type.charAt(0).toUpperCase() + type.slice(1);
    }
  }

  // Helper function to extract readable source name from URL
  extractSourceFromUrl(url) {
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
}