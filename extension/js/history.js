document.addEventListener('DOMContentLoaded', () => {
  // DOM elements
  const historyItemsContainer = document.getElementById('history-items');
  const emptyState = document.getElementById('empty-state');
  const detailView = document.getElementById('detail-view');
  const searchInput = document.getElementById('search-input');
  const sourceFilter = document.getElementById('source-filter');
  const timeFilter = document.getElementById('time-filter');
  const sortFilter = document.getElementById('sort-filter');
  const exportBtn = document.getElementById('export-btn');
  const clearBtn = document.getElementById('clear-btn');
  const backBtn = document.getElementById('back-btn');
  const openArticleBtn = document.getElementById('open-article-btn');
  
  // Detail view elements
  const detailTitle = document.getElementById('detail-title');
  const detailSource = document.getElementById('detail-source');
  const detailDate = document.getElementById('detail-date');
  const detailIndicator = document.getElementById('detail-indicator');
  const detailPercentile = document.getElementById('detail-percentile');
  const detailEntities = document.getElementById('detail-entities');
  
  // State
  let historyItems = [];
  let filteredItems = [];
  let selectedItemIndex = -1;
  
  // Load history items
  loadHistoryItems();
  
  // Event listeners
  searchInput.addEventListener('input', filterItems);
  sourceFilter.addEventListener('change', filterItems);
  timeFilter.addEventListener('change', filterItems);
  sortFilter.addEventListener('change', filterItems);
  exportBtn.addEventListener('click', exportHistory);
  clearBtn.addEventListener('click', clearHistory);
  backBtn.addEventListener('click', hideDetailView);
  
  // Load history items from storage
  async function loadHistoryItems() {
    try {
      // Send message to background script to get history
      const response = await chrome.runtime.sendMessage({ action: 'getAnalysisHistory' });
      historyItems = response.history || [];
      
      // Populate source filter
      populateSourceFilter();
      
      // Filter and display items
      filterItems();
    } catch (error) {
      console.error('Error loading history items:', error);
      historyItemsContainer.innerHTML = '<div class="error-message">Error loading history. Please try again.</div>';
    }
  }
  
  // Populate source filter dropdown
  function populateSourceFilter() {
    // Get unique sources
    const sources = Array.from(new Set(historyItems.map(item => item.source)));
    
    // Sort sources alphabetically
    sources.sort();
    
    // Clear existing options (except the first one)
    sourceFilter.innerHTML = '<option value="">All Sources</option>';
    
    // Add source options
    sources.forEach(source => {
      const option = document.createElement('option');
      option.value = source;
      option.textContent = source;
      sourceFilter.appendChild(option);
    });
  }
  
  // Filter history items based on search and filters
  function filterItems() {
    const searchTerm = searchInput.value.toLowerCase();
    const sourceValue = sourceFilter.value;
    const timeValue = timeFilter.value;
    const sortValue = sortFilter.value;
    
    // Filter by search term and source
    filteredItems = historyItems.filter(item => {
      // Search term filter
      const matchesSearch = !searchTerm || 
        item.title.toLowerCase().includes(searchTerm) || 
        item.source.toLowerCase().includes(searchTerm);
      
      // Source filter
      const matchesSource = !sourceValue || item.source === sourceValue;
      
      // Time filter
      const matchesTime = filterByTime(item, timeValue);
      
      return matchesSearch && matchesSource && matchesTime;
    });
    
    // Sort items
    sortItems(sortValue);
    
    // Display filtered items
    displayItems();
  }
  
  // Filter items by time period
  function filterByTime(item, timeValue) {
    if (!timeValue || timeValue === 'all') return true;
    
    const itemDate = new Date(item.timestamp);
    const now = new Date();
    
    switch (timeValue) {
      case 'today':
        return itemDate.toDateString() === now.toDateString();
        
      case 'week':
        const weekAgo = new Date();
        weekAgo.setDate(now.getDate() - 7);
        return itemDate >= weekAgo;
        
      case 'month':
        const monthAgo = new Date();
        monthAgo.setMonth(now.getMonth() - 1);
        return itemDate >= monthAgo;
        
      default:
        return true;
    }
  }
  
  // Sort filtered items
  function sortItems(sortValue) {
    switch (sortValue) {
      case 'newest':
        filteredItems.sort((a, b) => b.timestamp - a.timestamp);
        break;
        
      case 'oldest':
        filteredItems.sort((a, b) => a.timestamp - b.timestamp);
        break;
        
      case 'unusual':
        filteredItems.sort((a, b) => a.result.composite_score.percentile - b.result.composite_score.percentile);
        break;
    }
  }
  
  // Display filtered items
  function displayItems() {
    // Show empty state if no items
    if (filteredItems.length === 0) {
      historyItemsContainer.innerHTML = '';
      emptyState.classList.remove('hidden');
      return;
    }
    
    // Hide empty state
    emptyState.classList.add('hidden');
    
    // Create HTML for items
    const html = filteredItems.map((item, index) => {
      // Format date
      const date = new Date(item.timestamp);
      const formattedDate = date.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
      
      // Get significance class
      const percentile = item.result.composite_score.percentile;
      let significanceClass, significanceText;
      
      if (percentile < 10) {
        significanceClass = 'very-unusual';
        significanceText = 'Very Unusual';
      } else if (percentile < 25) {
        significanceClass = 'unusual';
        significanceText = 'Unusual';
      } else {
        significanceClass = 'typical';
        significanceText = 'Typical';
      }
      
      // Get top 3 entities for preview
      const topEntities = item.result.entities
        .slice(0, 3)
        .map(entity => `<span class="entity-chip">${entity.name}</span>`)
        .join('');
      
      return `
        <div class="history-item" data-index="${index}">
          <div class="history-item-header">
            <div>
              <h3 class="history-item-title">${item.title}</h3>
              <div class="history-item-source">${item.source}</div>
            </div>
            <div class="history-item-date">${formattedDate}</div>
          </div>
          
          <div class="sentiment-indicator">
            <span class="significance-badge ${significanceClass}">${significanceText} (${percentile}%)</span>
          </div>
          
          <div class="entity-chips">
            ${topEntities}
          </div>
        </div>
      `;
    }).join('');
    
    // Update container
    historyItemsContainer.innerHTML = html;
    
    // Add click event to items
    document.querySelectorAll('.history-item').forEach(item => {
      item.addEventListener('click', () => {
        const index = parseInt(item.dataset.index, 10);
        showItemDetail(index);
      });
    });
  }
  
  // Show detail view for a history item
  function showItemDetail(index) {
    if (index < 0 || index >= filteredItems.length) return;
    
    selectedItemIndex = index;
    const item = filteredItems[index];
    
    // Set detail view content
    detailTitle.textContent = item.title;
    detailSource.textContent = item.source;
    
    // Format date
    const date = new Date(item.timestamp);
    detailDate.textContent = date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
    
    // Set percentile indicator
    const percentile = item.result.composite_score.percentile;
    detailIndicator.style.left = `${percentile}%`;
    
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
    
    detailPercentile.textContent = `This article's bias pattern is ${percentileText} compared to global news sources (p-value: ${item.result.composite_score.p_value.toFixed(3)})`;
    
    // Generate entity details
    const entitiesHtml = item.result.entities.map(entity => {
      // Map power score (-2 to 2) to percentage (0 to 100)
      const powerPercentage = ((entity.power_score + 2) / 4) * 100;
      
      // Map moral score (-2 to 2) to percentage (0 to 100)
      const moralPercentage = ((entity.moral_score + 2) / 4) * 100;
      
      // Generate context quotes
      const contextHtml = entity.mentions.map(mention => 
        `<p>"${mention.text}" <em>(${mention.context})</em></p>`
      ).join('');
      
      return `
        <div class="detail-entity">
          <div class="entity-header">
            <span class="entity-name">${entity.name}</span>
            <span class="entity-type">${formatEntityType(entity.type)}</span>
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
          
          <div class="entity-context">
            ${contextHtml}
          </div>
        </div>
      `;
    }).join('');
    
    detailEntities.innerHTML = entitiesHtml;
    
    // Set article URL for open button
    openArticleBtn.href = item.url;
    
    // Show detail view
    detailView.classList.remove('hidden');
  }
  
  // Hide detail view
  function hideDetailView() {
    detailView.classList.add('hidden');
    selectedItemIndex = -1;
  }
  
  // Export history to JSON file
  function exportHistory() {
    if (historyItems.length === 0) {
      alert('No history items to export');
      return;
    }
    
    // Create JSON blob
    const dataStr = JSON.stringify(historyItems, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    
    // Create download link
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `news-bias-analysis-history-${Date.now()}.json`;
    
    // Trigger download
    document.body.appendChild(a);
    a.click();
    
    // Cleanup
    window.setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 0);
  }
  
  // Clear all history
  function clearHistory() {
    if (confirm('Are you sure you want to clear all analysis history? This cannot be undone.')) {
      chrome.runtime.sendMessage({ action: 'clearAnalysisHistory' }, () => {
        historyItems = [];
        filteredItems = [];
        displayItems();
      });
    }
  }
  
  // Format entity type for display
  function formatEntityType(type) {
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