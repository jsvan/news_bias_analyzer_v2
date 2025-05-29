// Analysis Controller - Manages the analysis workflow
import { ApiService } from '../services/api-service.js';
import { appState } from '../state/app-state.js';
import { ErrorHandler } from '../utils/error-handler.js';

export class AnalysisController {
  constructor() {
    this.apiService = new ApiService();
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Listen for state changes
    appState.subscribe('currentView', (view) => {
      this.handleViewChange(view);
    });
  }

  async startAnalysis(forceReanalysis = false) {
    try {
      appState.setCurrentView('loading');
      appState.clearError();

      // Get current tab
      const tabs = await this.getCurrentTab();
      const currentTab = tabs[0];
      
      if (!currentTab) {
        throw new Error('No active tab found');
      }

      console.log(`Processing tab: ${currentTab.url}`);
      
      // Check for existing analysis first (unless forcing reanalysis)
      if (!forceReanalysis) {
        const cached = await this.checkForExistingAnalysis(currentTab);
        if (cached) {
          return; // Analysis loaded from cache/database
        }
      }

      // Extract and analyze content
      await this.extractAndAnalyze(currentTab, forceReanalysis);

    } catch (error) {
      console.error('Analysis failed:', error);
      ErrorHandler.handleAnalysisError(error, forceReanalysis);
      appState.setCurrentView('error');
    }
  }

  async checkForExistingAnalysis(tab) {
    try {
      // First check in-memory cache
      const cached = appState.getCachedAnalysis(tab.url, tab.id);
      if (cached) {
        console.log('Found in-memory cached analysis');
        appState.setAnalysisResult(cached);
        appState.setCurrentView('results');
        return true;
      }

      // Check Chrome storage
      const storageCached = await appState.loadCacheFromChromeStorage(tab.url, tab.id);
      if (storageCached) {
        console.log('Found storage cached analysis');
        appState.setAnalysisResult(storageCached);
        appState.setCurrentView('results');
        return true;
      }

      // Check database via API
      const dbResult = await this.apiService.getAnalysisByUrl(tab.url);
      if (dbResult.exists && dbResult.entities && dbResult.entities.length > 0) {
        console.log('Found existing analysis in database');
        
        const formattedResult = this.formatDatabaseResult(dbResult);
        appState.setAnalysisResult(formattedResult);
        appState.setCurrentView('results');
        return true;
      }

      return false;

    } catch (error) {
      console.warn('Error checking for existing analysis:', error);
      return false;
    }
  }

  async extractAndAnalyze(tab, forceReanalysis) {
    // Try content script first, fall back to API extraction
    const content = await this.extractContent(tab);
    
    if (!content) {
      throw new Error('Content extraction failed');
    }

    // Validate article data
    ErrorHandler.validateArticleData(content);

    // Store current article
    appState.setCurrentArticle(content);

    // Analyze with API
    const result = await this.apiService.analyzeArticle(content, forceReanalysis);
    
    // Validate and format result
    ErrorHandler.validateApiResponse(result, ['entities']);
    
    const formattedResult = this.formatAnalysisResult(result, content);
    appState.setAnalysisResult(formattedResult);
    appState.setCurrentView('results');
  }

  async extractContent(tab) {
    try {
      // Try content script first
      const response = await this.sendMessageToContentScript(tab.id, { action: 'getPageContent' });
      
      if (response && response.content) {
        console.log('Content extracted via content script');
        return {
          url: response.content.url,
          source: response.content.source,
          title: response.content.headline,
          text: response.content.content
        };
      }
    } catch (error) {
      console.warn('Content script not available:', error);
    }

    // Fall back to API extraction
    console.log('Extracting content using API...');
    const extractedData = await this.apiService.extractContent(tab.url);
    
    if (!extractedData.text || extractedData.text.trim() === '') {
      throw new Error('No text content found on the page');
    }

    return {
      url: extractedData.url,
      source: extractedData.source || new URL(extractedData.url).hostname,
      title: extractedData.title,
      text: extractedData.text,
      publishDate: extractedData.publish_date
    };
  }

  formatDatabaseResult(dbResult) {
    return {
      id: this.generateArticleId(dbResult.url),
      url: dbResult.url,
      title: dbResult.title,
      source: dbResult.source,
      entities: dbResult.entities,
      quotes: dbResult.quotes || [],
      composite_score: dbResult.composite_score || { percentile: 50 },
      from_database: true
    };
  }

  formatAnalysisResult(result, article) {
    const formattedResult = {
      id: this.generateArticleId(article.url),
      url: article.url,
      title: article.title,
      source: article.source,
      entities: result.entities || [],
      quotes: result.quotes || [],
      composite_score: result.composite_score || { percentile: 50 },
      newly_analyzed: result.newly_analyzed,
      from_database: result.from_database,
      saved_to_database: result.saved_to_database
    };

    // Normalize entity fields
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
          const entityQuotes = (formattedResult.quotes || [])
            .filter(quote => quote.speaker && quote.speaker === (entity.name || entity.entity))
            .map(quote => ({ text: quote.quote, context: quote.title || 'from article' }));

          entity.mentions = entityQuotes.length > 0 ? entityQuotes : [];
        }
      });
    }

    return formattedResult;
  }

  // Helper methods
  getCurrentTab() {
    return new Promise((resolve) => {
      chrome.tabs.query({ active: true, currentWindow: true }, resolve);
    });
  }

  sendMessageToContentScript(tabId, message) {
    return new Promise((resolve, reject) => {
      chrome.tabs.sendMessage(tabId, message, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    });
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

  handleViewChange(view) {
    // This can be used to trigger UI updates based on view changes
    console.log(`View changed to: ${view}`);
  }
}