// Centralized Error Handling
import { CONFIG } from '../config.js';
import { appState } from '../state/app-state.js';

export class ErrorHandler {
  static showError(message, context = '', duration = 5000) {
    // Update application state
    appState.setError({ message, context, timestamp: Date.now() });
    
    // Show UI error message
    this.displayErrorInUI(message, 'error');
    
    // Log error for debugging
    console.error(`[${context}] ${message}`);
    
    // Auto-clear error after duration
    if (duration > 0) {
      setTimeout(() => {
        appState.clearError();
      }, duration);
    }
  }

  static showWarning(message, context = '', duration = 3000) {
    this.displayErrorInUI(message, 'warning');
    console.warn(`[${context}] ${message}`);
    
    if (duration > 0) {
      setTimeout(() => {
        this.clearErrorUI();
      }, duration);
    }
  }

  static handleApiError(error, context = 'API') {
    let userMessage = '';
    let logMessage = error.message || 'Unknown API error';
    
    // Handle specific error types
    if (error.message === 'INSUFFICIENT_DATA') {
      userMessage = CONFIG.ERRORS.INSUFFICIENT_DATA;
    } else if (error.message && error.message.includes('500')) {
      userMessage = 'Server error. Please try again later.';
    } else if (error.message && error.message.includes('404')) {
      userMessage = 'API endpoint not found. Please check server status.';
    } else if (error.message && error.message.includes('timeout')) {
      userMessage = 'Request timed out. Please check your connection.';
    } else if (error.message && error.message.includes('Failed to fetch')) {
      userMessage = CONFIG.ERRORS.API_UNREACHABLE;
    } else {
      userMessage = CONFIG.ERRORS.ANALYSIS_FAILED;
    }
    
    this.showError(userMessage, context);
    
    // Log full error details for debugging
    console.error(`[${context}] Full error:`, {
      message: logMessage,
      status: error.status,
      stack: error.stack,
      timestamp: new Date().toISOString()
    });
  }

  static handleContentExtractionError(error) {
    let message = CONFIG.ERRORS.CONTENT_EXTRACTION_FAILED;
    
    if (error.message && error.message.includes('500')) {
      message = 'Content extraction failed: Server error. Make sure the server is properly configured.';
    } else if (error.message && error.message.includes('No text content')) {
      message = 'No readable content found on this page.';
    }
    
    this.showError(message, 'Content Extraction');
  }

  static handleAnalysisError(error, forceReanalysis = false) {
    const context = forceReanalysis ? 'Re-analysis' : 'Analysis';
    
    if (error.message && error.message.includes('Missing required')) {
      this.showError('Missing article data. Please refresh and try again.', context);
    } else {
      this.handleApiError(error, context);
    }
  }

  static displayErrorInUI(message, type = 'error') {
    // Try to find existing error display
    let errorContainer = document.getElementById('error-display');
    
    if (!errorContainer) {
      // Create error display if it doesn't exist
      errorContainer = document.createElement('div');
      errorContainer.id = 'error-display';
      errorContainer.style.cssText = `
        position: fixed;
        top: 10px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 10000;
        padding: 12px 16px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        max-width: 350px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        animation: slideDown 0.3s ease-out;
      `;
      
      // Add CSS animation
      const style = document.createElement('style');
      style.textContent = `
        @keyframes slideDown {
          from { transform: translateX(-50%) translateY(-100%); opacity: 0; }
          to { transform: translateX(-50%) translateY(0); opacity: 1; }
        }
        @keyframes slideUp {
          from { transform: translateX(-50%) translateY(0); opacity: 1; }
          to { transform: translateX(-50%) translateY(-100%); opacity: 0; }
        }
      `;
      document.head.appendChild(style);
      
      document.body.appendChild(errorContainer);
    }
    
    // Set style based on type
    if (type === 'error') {
      errorContainer.style.backgroundColor = '#fee2e2';
      errorContainer.style.color = '#dc2626';
      errorContainer.style.border = '1px solid #fecaca';
    } else if (type === 'warning') {
      errorContainer.style.backgroundColor = '#fef3c7';
      errorContainer.style.color = '#d97706';
      errorContainer.style.border = '1px solid #fed7aa';
    } else if (type === 'success') {
      errorContainer.style.backgroundColor = '#d1fae5';
      errorContainer.style.color = '#065f46';
      errorContainer.style.border = '1px solid #a7f3d0';
    }
    
    // Set message
    errorContainer.textContent = message;
    
    // Make sure it's visible
    errorContainer.style.display = 'block';
  }

  static clearErrorUI() {
    const errorContainer = document.getElementById('error-display');
    if (errorContainer) {
      errorContainer.style.animation = 'slideUp 0.3s ease-out';
      setTimeout(() => {
        if (errorContainer.parentNode) {
          errorContainer.parentNode.removeChild(errorContainer);
        }
      }, 300);
    }
  }

  static showSuccess(message, duration = 3000) {
    this.displayErrorInUI(message, 'success');
    
    if (duration > 0) {
      setTimeout(() => {
        this.clearErrorUI();
      }, duration);
    }
  }

  // Validation helpers
  static validateArticleData(article) {
    const required = ['url', 'source', 'title', 'text'];
    const missing = required.filter(field => !article[field] || article[field].trim() === '');
    
    if (missing.length > 0) {
      throw new Error(`Missing required fields: ${missing.join(', ')}`);
    }
    
    return true;
  }

  static validateApiResponse(response, expectedFields = []) {
    if (!response) {
      throw new Error('Empty API response');
    }
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    const missing = expectedFields.filter(field => !(field in response));
    if (missing.length > 0) {
      throw new Error(`API response missing fields: ${missing.join(', ')}`);
    }
    
    return true;
  }

  // Development helpers
  static logError(message, data = null) {
    if (process.env.NODE_ENV === 'development') {
      console.error(`[ErrorHandler] ${message}`, data);
    }
  }

  static logWarning(message, data = null) {
    if (process.env.NODE_ENV === 'development') {
      console.warn(`[ErrorHandler] ${message}`, data);
    }
  }
}