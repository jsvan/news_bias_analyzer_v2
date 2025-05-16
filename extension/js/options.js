document.addEventListener('DOMContentLoaded', () => {
  // DOM elements
  const settingsForm = document.getElementById('settings-form');
  const saveBtn = document.getElementById('save-btn');
  const resetBtn = document.getElementById('reset-btn');
  const clearHistoryBtn = document.getElementById('clear-history-btn');
  const clearCacheBtn = document.getElementById('clear-cache-btn');
  const statusMessage = document.getElementById('status-message');
  const historyCountEl = document.getElementById('history-count');
  const cacheCountEl = document.getElementById('cache-count');
  
  // Form fields
  const apiEndpointInput = document.getElementById('api-endpoint');
  const analysisModeSelect = document.getElementById('analysis-mode');
  const autoAnalyzeCheckbox = document.getElementById('auto-analyze');
  const saveHistoryCheckbox = document.getElementById('save-history');
  const maxHistoryInput = document.getElementById('max-history');
  const themeSelect = document.getElementById('theme');
  const forceReanalysisCheckbox = document.getElementById('force-reanalysis');
  
  // Default settings
  const defaultSettings = {
    apiEndpoint: 'http://localhost:8000',
    analysisMode: 'demo',
    autoAnalyze: false,
    saveHistory: true,
    maxHistoryItems: 50,
    theme: 'light',
    forceReanalysis: false
  };
  
  // Load settings
  loadSettings();
  
  // Load history and cache stats
  loadHistoryStats();
  loadCacheStats();
  
  // Event Listeners
  settingsForm.addEventListener('submit', saveSettings);
  resetBtn.addEventListener('click', resetSettings);
  clearHistoryBtn.addEventListener('click', clearHistory);
  clearCacheBtn.addEventListener('click', clearCache);
  
  // Load settings from storage
  async function loadSettings() {
    try {
      // Send message to background script to get settings
      const response = await chrome.runtime.sendMessage({ action: 'getSettings' });
      const settings = response.settings;
      
      // If no settings, use defaults
      if (!settings || Object.keys(settings).length === 0) {
        populateForm(defaultSettings);
      } else {
        populateForm(settings);
      }
    } catch (error) {
      console.error('Error loading settings:', error);
      showMessage('Error loading settings', 'error');
      
      // Fallback to defaults
      populateForm(defaultSettings);
    }
  }
  
  // Populate form with settings
  function populateForm(settings) {
    apiEndpointInput.value = settings.apiEndpoint || '';
    analysisModeSelect.value = settings.analysisMode || 'demo';
    autoAnalyzeCheckbox.checked = settings.autoAnalyze || false;
    saveHistoryCheckbox.checked = settings.saveHistory !== undefined ? settings.saveHistory : true;
    maxHistoryInput.value = settings.maxHistoryItems || 50;
    themeSelect.value = settings.theme || 'light';
    forceReanalysisCheckbox.checked = settings.forceReanalysis || false;
  }
  
  // Save settings
  async function saveSettings(event) {
    event.preventDefault();
    
    // Collect form values
    const settings = {
      apiEndpoint: apiEndpointInput.value.trim(),
      analysisMode: analysisModeSelect.value,
      autoAnalyze: autoAnalyzeCheckbox.checked,
      saveHistory: saveHistoryCheckbox.checked,
      maxHistoryItems: parseInt(maxHistoryInput.value, 10),
      theme: themeSelect.value,
      forceReanalysis: forceReanalysisCheckbox.checked
    };
    
    // Validate settings
    const validation = validateSettings(settings);
    if (!validation.valid) {
      showMessage(validation.message, 'error');
      return;
    }
    
    try {
      // Send message to background script to save settings
      await chrome.runtime.sendMessage({ 
        action: 'saveSettings', 
        settings: settings 
      });
      
      showMessage('Settings saved successfully', 'success');
    } catch (error) {
      console.error('Error saving settings:', error);
      showMessage('Error saving settings', 'error');
    }
  }
  
  // Reset settings to defaults
  function resetSettings() {
    if (confirm('Reset all settings to default values?')) {
      populateForm(defaultSettings);
      
      // Save default settings
      chrome.runtime.sendMessage({ 
        action: 'saveSettings', 
        settings: defaultSettings 
      });
      
      showMessage('Settings reset to defaults', 'success');
    }
  }
  
  // Clear analysis history
  async function clearHistory() {
    if (confirm('Are you sure you want to clear all analysis history? This cannot be undone.')) {
      try {
        // Send message to background script to clear history
        await chrome.runtime.sendMessage({ action: 'clearAnalysisHistory' });
        
        showMessage('Analysis history cleared', 'success');
        
        // Update history stats
        loadHistoryStats();
      } catch (error) {
        console.error('Error clearing history:', error);
        showMessage('Error clearing history', 'error');
      }
    }
  }
  
  // Load history stats
  async function loadHistoryStats() {
    try {
      // Send message to background script to get history
      const response = await chrome.runtime.sendMessage({ action: 'getAnalysisHistory' });
      const history = response.history || [];
      
      // Update history count
      historyCountEl.textContent = history.length;
    } catch (error) {
      console.error('Error loading history stats:', error);
      historyCountEl.textContent = '0';
    }
  }
  
  // Load cache stats
  async function loadCacheStats() {
    try {
      // Get cache from local storage
      const cache = await chrome.storage.local.get('articleCache');
      const articleCache = cache.articleCache || {};
      
      // Update cache count
      const cacheCount = Object.keys(articleCache).length;
      cacheCountEl.textContent = cacheCount;
    } catch (error) {
      console.error('Error loading cache stats:', error);
      cacheCountEl.textContent = '0';
    }
  }
  
  // Clear article cache
  async function clearCache() {
    if (confirm('Are you sure you want to clear the URL cache? This will remove all cached analysis results.')) {
      try {
        // Remove article cache
        await chrome.storage.local.remove('articleCache');
        
        // Update cache stats
        cacheCountEl.textContent = '0';
        
        showMessage('URL cache cleared', 'success');
      } catch (error) {
        console.error('Error clearing cache:', error);
        showMessage('Error clearing cache', 'error');
      }
    }
  }
  
  // Validate settings
  function validateSettings(settings) {
    // Validate API endpoint
    if (!settings.apiEndpoint) {
      return { valid: false, message: 'API endpoint is required' };
    }
    
    try {
      new URL(settings.apiEndpoint);
    } catch (error) {
      return { valid: false, message: 'API endpoint must be a valid URL' };
    }
    
    // Validate max history items
    if (isNaN(settings.maxHistoryItems) || settings.maxHistoryItems < 5 || settings.maxHistoryItems > 100) {
      return { valid: false, message: 'Max history items must be a number between 5 and 100' };
    }
    
    return { valid: true };
  }
  
  // Show status message
  function showMessage(message, type = 'success') {
    statusMessage.textContent = message;
    statusMessage.className = 'visible';
    statusMessage.classList.add(type);
    
    setTimeout(() => {
      statusMessage.classList.remove('visible');
    }, 3000);
  }
});