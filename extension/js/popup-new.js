// New Main Entry Point - Integrates all refactored modules
import { CONFIG } from './config.js';
import { appState } from './state/app-state.js';
import { ApiService } from './services/api-service.js';
import { ErrorHandler } from './utils/error-handler.js';
import { AnalysisController } from './components/analysis-controller.js';
import { UIRenderer } from './components/ui-renderer.js';
import { TabManager } from './components/tab-manager.js';

class NewsAnalyzerApp {
  constructor() {
    this.apiService = new ApiService();
    this.analysisController = new AnalysisController();
    this.uiRenderer = new UIRenderer();
    this.tabManager = new TabManager();
    
    this.initialized = false;
  }

  async initialize() {
    if (this.initialized) return;
    
    try {
      console.log('Initializing News Analyzer App...');
      
      // Set up global error handling
      this.setupGlobalErrorHandling();
      
      // Initialize UI event listeners
      this.setupEventListeners();
      
      // Check API health
      await this.checkApiHealth();
      
      // Initialize extension state
      await this.initializeExtension();
      
      this.initialized = true;
      console.log('News Analyzer App initialized successfully');
      
    } catch (error) {
      console.error('Failed to initialize app:', error);
      ErrorHandler.showError('Failed to initialize application');
    }
  }

  setupGlobalErrorHandling() {
    // Global error handler for unhandled promises
    window.addEventListener('unhandledrejection', (event) => {
      console.error('Unhandled promise rejection:', event.reason);
      ErrorHandler.showError('An unexpected error occurred');
      event.preventDefault();
    });

    // Global error handler for uncaught errors
    window.addEventListener('error', (event) => {
      console.error('Uncaught error:', event.error);
      ErrorHandler.showError('An unexpected error occurred');
    });
  }

  setupEventListeners() {
    // Main action buttons
    const analyzeBtn = document.getElementById('analyze-btn');
    const forceAnalyzeBtn = document.getElementById('force-analyze-btn');
    const retryBtn = document.getElementById('retry-btn');
    const viewDetailsBtn = document.getElementById('view-details-btn');
    const backBtn = document.getElementById('back-btn');

    if (analyzeBtn) {
      analyzeBtn.addEventListener('click', () => {
        this.analysisController.startAnalysis(false);
      });
    }

    if (forceAnalyzeBtn) {
      forceAnalyzeBtn.addEventListener('click', () => {
        this.analysisController.startAnalysis(true);
      });
    }

    if (retryBtn) {
      retryBtn.addEventListener('click', () => {
        this.analysisController.startAnalysis(false);
      });
    }

    if (viewDetailsBtn) {
      viewDetailsBtn.addEventListener('click', () => {
        this.showDetailedView();
      });
    }

    if (backBtn) {
      backBtn.addEventListener('click', () => {
        this.hideDetailedView();
      });
    }
  }

  async checkApiHealth() {
    try {
      const health = await this.apiService.checkHealth();
      if (!health.ok) {
        this.showApiWarning();
      }
    } catch (error) {
      console.warn('API health check failed:', error);
      this.showApiWarning();
    }
  }

  showApiWarning() {
    const warningEl = document.getElementById('api-status-warning');
    if (warningEl) {
      warningEl.style.display = 'block';
    }
  }

  async initializeExtension() {
    try {
      // Get current tab
      const tabs = await this.getCurrentTab();
      const currentTab = tabs[0];

      if (!currentTab) {
        appState.setCurrentView('initial');
        return;
      }

      // Check for cached results first
      const cached = appState.getCachedAnalysis(currentTab.url, currentTab.id);
      if (cached) {
        console.log('Found in-memory cached analysis');
        appState.setAnalysisResult(cached);
        appState.setCurrentView('results');
        return;
      }

      // Check Chrome storage
      const storageCached = await appState.loadCacheFromChromeStorage(currentTab.url, currentTab.id);
      if (storageCached) {
        console.log('Found storage cached analysis');
        appState.setAnalysisResult(storageCached);
        appState.setCurrentView('results');
        return;
      }

      // Check database via analysis controller
      const hasExisting = await this.analysisController.checkForExistingAnalysis(currentTab);
      if (!hasExisting) {
        appState.setCurrentView('initial');
      }

    } catch (error) {
      console.error('Error initializing extension:', error);
      appState.setCurrentView('initial');
    }
  }

  showDetailedView() {
    appState.setCurrentView('detailed');
    
    // Initialize visualizations for the detailed view
    this.tabManager.initializeVisualizations();

    // Load data for the active tab
    const activeTab = appState.getActiveTab();
    const analysisResult = appState.getAnalysisResult();
    
    if (activeTab && analysisResult) {
      this.tabManager.loadTabData(activeTab, analysisResult);
    }
  }

  hideDetailedView() {
    appState.setCurrentView('results');
  }

  // Utility methods
  getCurrentTab() {
    return new Promise((resolve) => {
      chrome.tabs.query({ active: true, currentWindow: true }, resolve);
    });
  }

  // Public API for external access
  getState() {
    return appState.getStateSnapshot();
  }

  async reanalyze() {
    return this.analysisController.startAnalysis(true);
  }

  switchTab(tabId) {
    this.tabManager.switchTab(tabId);
  }

  // Development helpers
  debug() {
    console.log('=== News Analyzer Debug Info ===');
    console.log('App State:', this.getState());
    console.log('Current Article:', appState.getCurrentArticle());
    console.log('Analysis Result:', appState.getAnalysisResult());
    console.log('Active Tab:', appState.getActiveTab());
    console.log('Current View:', appState.getCurrentView());
    console.log('Last Error:', appState.getLastError());
  }

  reset() {
    appState.reset();
    appState.setCurrentView('initial');
  }
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
  try {
    // Create global app instance
    window.newsAnalyzerApp = new NewsAnalyzerApp();
    await window.newsAnalyzerApp.initialize();
    
    // Make debug function available globally
    window.debugNewsAnalyzer = () => window.newsAnalyzerApp.debug();
    
  } catch (error) {
    console.error('Failed to start News Analyzer App:', error);
    ErrorHandler.showError('Failed to start application');
  }
});

// Export for module usage
export { NewsAnalyzerApp };