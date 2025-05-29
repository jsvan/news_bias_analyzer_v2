// UI Renderer - Handles DOM manipulation and UI updates
import { appState } from '../state/app-state.js';
import { ErrorHandler } from '../utils/error-handler.js';

export class UIRenderer {
  constructor() {
    this.elements = this.initializeElements();
    this.setupEventListeners();
  }

  initializeElements() {
    return {
      // State containers
      initialState: document.getElementById('initial-state'),
      loadingState: document.getElementById('loading-state'),
      resultsState: document.getElementById('results-state'),
      noArticleState: document.getElementById('no-article-state'),
      errorState: document.getElementById('error-state'),
      detailedView: document.getElementById('detailed-view'),

      // Buttons
      analyzeBtn: document.getElementById('analyze-btn'),
      forceAnalyzeBtn: document.getElementById('force-analyze-btn'),
      retryBtn: document.getElementById('retry-btn'),
      viewDetailsBtn: document.getElementById('view-details-btn'),
      backBtn: document.getElementById('back-btn'),

      // Result elements
      sourceEl: document.querySelector('#article-source span'),
      titleEl: document.getElementById('article-title'),
      entitiesListEl: document.getElementById('entities-list'),
      compositeIndicator: document.getElementById('composite-indicator'),
      compositePercentile: document.getElementById('composite-percentile'),

      // Tab elements
      tabButtons: document.querySelectorAll('.tab-btn'),
      tabContents: document.querySelectorAll('.tab-content'),

      // Info links
      methodologyLink: document.getElementById('methodology-link'),
      distributionInfoLink: document.getElementById('distribution-info-link')
    };
  }

  setupEventListeners() {
    // Subscribe to state changes
    appState.subscribe('currentView', (view) => {
      this.showState(view);
    });

    appState.subscribe('analysisResult', (result) => {
      if (result) {
        this.displayResults(result);
      }
    });

    appState.subscribe('error', (error) => {
      if (error) {
        this.showErrorMessage(error.message);
      }
    });

    // Info button popups
    if (this.elements.methodologyLink) {
      this.elements.methodologyLink.addEventListener('click', (e) => {
        e.preventDefault();
        this.showInfoPopup('Composite Bias Score Methodology', 
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

    if (this.elements.distributionInfoLink) {
      this.elements.distributionInfoLink.addEventListener('click', (e) => {
        e.preventDefault();
        this.showInfoPopup('Sentiment Distribution Explanation',
          'This histogram shows how the selected entity\'s sentiment score compares to the global distribution of scores for similar entities across thousands of news articles.\n\n' +
          'The highlighted bar shows where this article\'s sentiment falls in the distribution, helping identify unusual portrayals.'
        );
      });
    }
  }

  showState(stateName) {
    const states = [
      this.elements.initialState,
      this.elements.loadingState,
      this.elements.resultsState,
      this.elements.noArticleState,
      this.elements.errorState,
      this.elements.detailedView
    ];

    const stateMap = {
      'initial': this.elements.initialState,
      'loading': this.elements.loadingState,
      'results': this.elements.resultsState,
      'detailed': this.elements.detailedView,
      'no-article': this.elements.noArticleState,
      'error': this.elements.errorState
    };

    const stateToShow = stateMap[stateName];

    states.forEach(state => {
      if (state) {
        if (state === stateToShow) {
          state.classList.remove('hidden');
        } else {
          state.classList.add('hidden');
        }
      }
    });
  }

  displayResults(result) {
    if (!result) {
      console.error("No result data to display");
      ErrorHandler.showError("Failed to display results: No data available");
      return;
    }

    try {
      // Ensure result.article exists for use in similarity tab
      if (!result.article) {
        result.article = {
          id: result.id || this.generateArticleId(result.url),
          url: result.url,
          title: result.title,
          source: result.source
        };
      }

      // Set source and title with safe defaults
      if (this.elements.sourceEl) {
        this.elements.sourceEl.textContent = result.source || "Unknown Source";
      }
      
      if (this.elements.titleEl) {
        this.elements.titleEl.textContent = result.title || "Untitled Article";
      }
      
      // Set composite score
      this.displayCompositeScore(result.composite_score);
      
      // Display entities
      if (result.entities && Array.isArray(result.entities)) {
        this.displayEntityList(result.entities);
      } else {
        console.warn("No entity data to display");
        if (this.elements.entitiesListEl) {
          this.elements.entitiesListEl.innerHTML = '<div class="empty-message">No entities found in this article</div>';
        }
      }
      
      // Add database/cache indicators
      this.displayCacheIndicator(result);
      
    } catch (e) {
      console.error("Error displaying results:", e);
      ErrorHandler.showError("Failed to display results: " + e.message);
    }
  }

  displayCompositeScore(compositeScore) {
    const percentile = compositeScore && compositeScore.percentile ? compositeScore.percentile : 50;
        
    if (this.elements.compositeIndicator) {
      this.elements.compositeIndicator.style.left = `${percentile}%`;
    }
    
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

    if (this.elements.compositePercentile) {
      this.elements.compositePercentile.textContent = percentileText;
    }
  }

  displayCacheIndicator(result) {
    const cacheTag = document.getElementById('cache-indicator');
    if (cacheTag) {
      if (result.from_database) {
        cacheTag.textContent = 'FROM DB';
        cacheTag.title = 'Analysis retrieved from database';
        cacheTag.style.display = 'inline-block';
        cacheTag.style.backgroundColor = '#4a90e2';
      } else if (result.newly_analyzed) {
        cacheTag.textContent = 'NEW';
        cacheTag.title = 'Newly analyzed article';
        cacheTag.style.display = 'inline-block';
        cacheTag.style.backgroundColor = '#2ecc71';
      } else if (result.saved_to_database) {
        cacheTag.textContent = 'SAVED';
        cacheTag.title = 'Analysis saved to database';
        cacheTag.style.display = 'inline-block';
        cacheTag.style.backgroundColor = '#3498db';
      } else {
        cacheTag.style.display = 'none';
      }
    }
  }

  displayEntityList(entities) {
    if (!this.elements.entitiesListEl) return;
    
    this.elements.entitiesListEl.innerHTML = '';

    entities.forEach(entity => {
      const entityItem = document.createElement('div');
      entityItem.className = 'entity-item';

      const displayName = entity.name || entity.entity || "Unknown Entity";
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
          <div class="entity-type">${this.formatEntityType(entityType)}</div>
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
      
      this.elements.entitiesListEl.appendChild(entityItem);
    });
  }

  showErrorMessage(message) {
    const errorMessage = document.querySelector('#error-state p');
    if (errorMessage) {
      errorMessage.textContent = message;
    }
  }

  // Info popup functionality
  showInfoPopup(title, message) {
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

  // Utility methods
  formatEntityType(type) {
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

  generateArticleId(url) {
    if (!url) return 'unknown_article';

    let hash = 0;
    for (let i = 0; i < url.length; i++) {
      const char = url.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return 'article_' + Math.abs(hash).toString(16);
  }
}