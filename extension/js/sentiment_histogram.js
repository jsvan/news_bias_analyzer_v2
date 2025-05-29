// Sentiment Histogram Implementation
// This implements multiple histograms showing sentiment distribution for all entities

class SentimentHistogram {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    
    this.options = Object.assign({
      barColor: '#3498db',
      highlightColor: '#ff8c00', // Orange color for current article
      textColor: '#333',
      countryColor: '#2ecc71', // Color for country-specific data
      bins: 5,
      showPercentile: true,
      animate: true,
      country: null,  // Currently selected country (null = global)
      dimension: 'moral' // Default to moral dimension
    }, options);
    
    this.entities = [];
    this.entityGlobalCounts = {};
    this.availableCountries = []; // Cache available countries
    this.scrollPosition = 0; // Track scroll position
  }
  
  // Set entities data for all histograms
  setEntitiesData(entities) {
    this.entities = entities;
    this.renderAllEntities();
  }
  
  // Set country filter
  setCountry(country) {
    // Save current scroll position
    if (this.container && this.container.parentElement) {
      this.scrollPosition = this.container.parentElement.scrollTop;
    }
    
    this.options.country = country;
    this.renderAllEntities().then(() => {
      // Restore scroll position after rendering
      if (this.container && this.container.parentElement) {
        this.container.parentElement.scrollTop = this.scrollPosition;
      }
      
      // Update all individual selectors to match
      this.updateAllCountrySelectors(country);
    });
  }
  
  // Set country filter with anchor positioning for individual selectors
  setCountryWithAnchor(country, anchorId) {
    this.options.country = country;
    this.renderAllEntities().then(() => {
      // Update all individual selectors to match
      this.updateAllCountrySelectors(country);
      
      // Scroll back to the specific histogram that was changed
      if (anchorId) {
        const targetElement = document.getElementById(anchorId);
        if (targetElement) {
          targetElement.scrollIntoView({ 
            behavior: 'instant', 
            block: 'center'
          });
        }
      }
    });
  }
  
  // Set dimension (power or moral)
  setDimension(dimension) {
    // Save current scroll position
    if (this.container && this.container.parentElement) {
      this.scrollPosition = this.container.parentElement.scrollTop;
    }
    
    this.options.dimension = dimension;
    this.renderAllEntities().then(() => {
      // Restore scroll position after rendering
      if (this.container && this.container.parentElement) {
        this.container.parentElement.scrollTop = this.scrollPosition;
      }
    });
  }
  
  // Create bins from data
  createBins(data, numBins = 5, normalize = false) {
    if (!data || data.length === 0) return [];
    
    // Fixed range for sentiment scores: -2 to +2
    const min = -2;
    const max = 2;
    const range = max - min;
    const binWidth = range / numBins;
    
    // Initialize bins
    const bins = Array(numBins).fill(0);
    
    // Count values in each bin
    data.forEach(value => {
      // Clamp values to the -2 to +2 range
      const clampedValue = Math.max(min, Math.min(max, value));
      
      // Handle edge case for max value
      if (clampedValue === max) {
        bins[numBins - 1]++;
      } else {
        const binIndex = Math.floor((clampedValue - min) / binWidth);
        bins[binIndex < 0 ? 0 : (binIndex >= numBins ? numBins - 1 : binIndex)]++;
      }
    });
    
    // Normalize to probabilities (softmax-like) if requested
    let normalizedBins = bins;
    if (normalize) {
      const total = bins.reduce((sum, count) => sum + count, 0);
      if (total > 0) {
        normalizedBins = bins.map(count => count / total);
      }
    }
    
    // Calculate bin boundaries for labels
    const binBoundaries = Array(numBins + 1).fill(0).map((_, i) => min + i * binWidth);
    
    return {
      counts: normalizedBins,
      boundaries: binBoundaries,
      max: Math.max(...normalizedBins)
    };
  }
  
  // Find bin for current value
  findBinForValue(value, binBoundaries) {
    for (let i = 0; i < binBoundaries.length - 1; i++) {
      if (value >= binBoundaries[i] && value <= binBoundaries[i + 1]) {
        return i;
      }
    }
    return -1;
  }

  // Render all entity histograms ordered by global count
  async renderAllEntities() {
    if (!this.container) return;
    
    // Clear container
    this.container.innerHTML = '';
    
    if (!this.entities || this.entities.length === 0) {
      this.container.innerHTML = '<div class="empty-message">No entities available</div>';
      return;
    }

    // Fetch global counts for all entities
    await this.fetchGlobalCounts();
    
    // Sort entities by global count (descending)
    const sortedEntities = [...this.entities].sort((a, b) => {
      const nameA = a.name || a.entity;
      const nameB = b.name || b.entity;
      const countA = this.entityGlobalCounts[nameA] || 0;
      const countB = this.entityGlobalCounts[nameB] || 0;
      return countB - countA;
    });

    // Render entities and collect results for reordering
    const renderResults = [];
    for (const entity of sortedEntities) {
      const result = await this.renderEntityHistogramWithResult(entity);
      renderResults.push(result);
    }

    // Reorder: successful renders first, then failed ones
    const successfulResults = renderResults.filter(r => r.success);
    const failedResults = renderResults.filter(r => !r.success);
    
    // Clear container again and add in correct order
    this.container.innerHTML = '';
    
    // Add successful renders first
    successfulResults.forEach(result => {
      this.container.appendChild(result.element);
    });
    
    // Add failed renders at the bottom
    failedResults.forEach(result => {
      this.container.appendChild(result.element);
    });
  }

  // Fetch global counts for entities
  async fetchGlobalCounts() {
    try {
      const response = await fetch('http://localhost:8000/stats/entity/global-counts');
      if (response.ok) {
        const data = await response.json();
        this.entityGlobalCounts = data.counts || {};
      }
    } catch (error) {
      console.warn('Could not fetch global entity counts:', error);
      this.entityGlobalCounts = {};
    }
  }

  // Render histogram for a single entity (returns success status)
  async renderEntityHistogramWithResult(entity) {
    const entityName = entity.name || entity.entity;
    if (!entityName) return { success: false, element: null };

    // Create container for this entity
    const entityContainer = document.createElement('div');
    entityContainer.className = 'entity-histogram-container';
    entityContainer.style.marginBottom = '30px';
    
    // Add unique ID for anchor functionality
    const safeEntityName = entityName.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    entityContainer.id = `histogram-${safeEntityName}`;
    entityContainer.setAttribute('data-entity-name', entityName);
    
    // Create title
    const title = document.createElement('h4');
    title.textContent = `${entityName} - ${this.options.dimension === 'moral' ? 'Moral' : 'Power'} Distribution`;
    title.style.marginBottom = '10px';
    title.style.fontSize = '14px';
    entityContainer.appendChild(title);

    // Create canvas
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 200;
    canvas.style.border = '1px solid #ddd';
    entityContainer.appendChild(canvas);

    // Create individual country selector
    const countrySelector = document.createElement('select');
    countrySelector.className = 'entity-country-selector';
    countrySelector.style.cssText = `
      width: 100%;
      padding: 4px 8px;
      margin-top: 8px;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-size: 12px;
      background-color: white;
    `;
    countrySelector.innerHTML = '<option value="">Global Comparison</option>';
    
    // Add event listener for this selector with anchor positioning
    countrySelector.addEventListener('change', (e) => {
      this.setCountryWithAnchor(e.target.value, entityContainer.id);
    });
    
    entityContainer.appendChild(countrySelector);

    // Create sample size info
    const sampleInfo = document.createElement('div');
    sampleInfo.className = 'sample-size-info';
    sampleInfo.style.fontSize = '12px';
    sampleInfo.style.color = '#666';
    sampleInfo.style.marginTop = '5px';
    sampleInfo.textContent = 'Loading...';
    entityContainer.appendChild(sampleInfo);

    // Populate country selector with available countries
    await this.populateCountrySelector(countrySelector, entityName);
    
    // Set current selection (only if this entity has data for the selected country)
    const hasSelectedCountry = Array.from(countrySelector.options).some(option => option.value === (this.options.country || ''));
    countrySelector.value = hasSelectedCountry ? (this.options.country || '') : '';
    
    // Fetch and render data for this entity
    const success = await this.fetchAndRenderEntityData(entity, canvas, sampleInfo, countrySelector);
    
    return { success, element: entityContainer };
  }

  // Render histogram for a single entity (legacy method for backward compatibility)
  async renderEntityHistogram(entity) {
    const result = await this.renderEntityHistogramWithResult(entity);
    if (result.element) {
      this.container.appendChild(result.element);
    }
  }

  // Fetch and render data for a specific entity
  async fetchAndRenderEntityData(entity, canvas, sampleInfo, countrySelector = null) {
    const entityName = entity.name || entity.entity;
    const dimension = this.options.dimension;
    // Use the individual selector's value if provided, otherwise fall back to global
    const country = countrySelector ? countrySelector.value : this.options.country;

    try {
      // Build API URL
      let apiUrl = `http://localhost:8000/stats/sentiment/distribution?entity_name=${encodeURIComponent(entityName)}&dimension=${dimension}`;
      if (country) {
        apiUrl += `&country=${encodeURIComponent(country)}`;
      }

      const response = await fetch(apiUrl);
      if (!response.ok) {
        // Check if it's a 400 error (insufficient data)
        if (response.status === 400) {
          this.renderEmptyCanvas(canvas, 'Not enough data');
          sampleInfo.textContent = 'Not enough data for meaningful analysis';
          sampleInfo.style.color = '#e67e22';
          sampleInfo.style.fontWeight = 'bold';
          return false; // Indicate failure
        }
        throw new Error(`API request failed: ${response.status}`);
      }

      const data = await response.json();
      
      // Check if we have valid data
      if (!data.has_data || !data.values || data.values.length < 5) {
        this.renderEmptyCanvas(canvas, 'Not enough data');
        sampleInfo.textContent = 'Not enough data for meaningful analysis';
        sampleInfo.style.color = '#e67e22';
        sampleInfo.style.fontWeight = 'bold';
        return false; // Indicate failure
      }

      // Get current entity's value from the entity object
      const currentValue = dimension === 'moral' ? entity.moral_score : entity.power_score;

      // Render the histogram
      this.renderEntityCanvas(canvas, data.values, currentValue, data.comparison_data, dimension);

      // Update sample size info
      let sampleText = `Sample: ${data.sample_size} mentions`;
      if (data.comparison_data) {
        const comparisonKey = Object.keys(data.comparison_data)[0];
        if (comparisonKey && data.comparison_data[comparisonKey]) {
          const comparisonCount = data.comparison_data[comparisonKey].length;
          sampleText += ` | ${comparisonKey}: ${comparisonCount} mentions`;
        }
      }
      sampleInfo.textContent = sampleText;
      sampleInfo.style.color = '#666'; // Reset to normal color
      sampleInfo.style.fontWeight = 'normal'; // Reset to normal weight
      
      return true; // Indicate success

    } catch (error) {
      console.error(`Error fetching data for entity ${entityName}:`, error);
      this.renderEmptyCanvas(canvas, 'Error loading data');
      sampleInfo.textContent = 'Error loading data from server';
      sampleInfo.style.color = '#e74c3c';
      sampleInfo.style.fontWeight = 'bold';
      return false; // Indicate failure
    }
  }

  // Render canvas for a specific entity
  renderEntityCanvas(canvas, values, currentValue, comparisonData, dimension) {
    const ctx = canvas.getContext('2d');
    const { barColor, highlightColor, textColor, countryColor, bins } = this.options;
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Check if we have comparison data
    let comparisonBinData = null;
    let hasComparison = false;
    
    if (comparisonData) {
      const comparisonKey = Object.keys(comparisonData)[0];
      if (comparisonKey && comparisonData[comparisonKey] && comparisonData[comparisonKey].length > 0) {
        const comparisonDataForBin = comparisonData[comparisonKey];
        comparisonBinData = this.createBins(comparisonDataForBin, bins, true); // Normalize country data
        // Add the raw values and label for percentile calculation
        comparisonBinData.values = comparisonDataForBin;
        comparisonBinData.label = comparisonKey;
        hasComparison = true;
      }
    }
    
    // Create bins for global data (normalize if we have comparison)
    const binData = this.createBins(values, bins, hasComparison);
    const { counts, boundaries } = binData;
    
    // Find which bin contains the current value
    const currentBin = this.findBinForValue(currentValue, boundaries);
    
    // Calculate dimensions
    const padding = { top: 20, right: 15, bottom: 60, left: 30 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const barWidth = chartWidth / bins;
    
    // Determine maximum value for scaling
    let maxValue = hasComparison ? 1.0 : Math.max(...counts);
    
    // Draw axes
    ctx.beginPath();
    ctx.strokeStyle = textColor;
    ctx.lineWidth = 1;
    ctx.moveTo(padding.left, height - padding.bottom);
    ctx.lineTo(width - padding.right, height - padding.bottom);
    ctx.stroke();
    
    // Y-axis
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, height - padding.bottom);
    ctx.stroke();
    
    // Draw bars and labels
    counts.forEach((count, i) => {
      const x = padding.left + i * barWidth;
      const barHeight = (count / maxValue) * chartHeight;
      const y = height - padding.bottom - barHeight;

      // Draw bar
      ctx.fillStyle = barColor;
      ctx.fillRect(x, y, barWidth - 1, barHeight);

      // Draw semantic labels
      ctx.fillStyle = textColor;
      ctx.textAlign = 'center';
      ctx.font = '9px Arial';

      let label = '';
      if (i === 0) {
        label = dimension === 'power' ? 'Very Weak' : 'Very Evil';
      } else if (i === 1) {
        label = dimension === 'power' ? 'Weak' : 'Evil';
      } else if (i === 2) {
        label = 'Neutral';
      } else if (i === 3) {
        label = dimension === 'power' ? 'Strong' : 'Good';
      } else {
        label = dimension === 'power' ? 'Very Strong' : 'Very Good';
      }

      ctx.fillText(label, x + barWidth / 2, height - padding.bottom + 15);
    });

    // Draw comparison bars if available (country-specific data)
    if (comparisonBinData) {
      comparisonBinData.counts.forEach((count, i) => {
        const x = padding.left + i * barWidth;
        const barHeight = (count / maxValue) * chartHeight;
        const y = height - padding.bottom - barHeight;
        
        // Draw country data as outlined bars with pattern
        ctx.strokeStyle = countryColor;
        ctx.lineWidth = 3;
        ctx.strokeRect(x + 2, y, barWidth - 5, barHeight);
        
        // Add diagonal line pattern for country data
        ctx.strokeStyle = countryColor;
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.6;
        
        // Draw diagonal lines pattern
        const lineSpacing = 4;
        for (let offset = -(barHeight + barWidth); offset < barWidth + barHeight; offset += lineSpacing) {
          ctx.beginPath();
          const startX = x + 2 + Math.max(0, offset);
          const startY = y + Math.max(0, -offset);
          const endX = x + 2 + Math.min(barWidth - 5, offset + barHeight);
          const endY = y + Math.min(barHeight, barHeight - offset);
          
          // Only draw if line is within the bar bounds
          if (startX < x + barWidth - 2 && startY < y + barHeight && endX > x + 2 && endY > y) {
            ctx.moveTo(startX, startY);
            ctx.lineTo(endX, endY);
          }
        }
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      });
    }

    // Draw current article indicator
    if (currentBin >= 0 && currentBin < counts.length) {
      const x = padding.left + currentBin * barWidth;
      const barHeight = (counts[currentBin] / maxValue) * chartHeight;
      const y = height - padding.bottom - barHeight;
      
      // Calculate percentile - use comparison data if available, otherwise global data
      let percentile, percentileLabel;
      if (comparisonBinData && comparisonBinData.values && comparisonBinData.values.length > 0) {
        // Calculate percentile relative to country/comparison data
        const comparisonValues = comparisonBinData.values;
        const lowerCountComparison = comparisonValues.filter(v => v < currentValue).length;
        percentile = Math.round((lowerCountComparison / comparisonValues.length) * 100);
        percentileLabel = `${percentile}th percentile (${comparisonBinData.label || 'comparison'})`;
      } else {
        // Calculate percentile relative to global data
        const lowerCount = values.filter(v => v < currentValue).length;
        percentile = Math.round((lowerCount / values.length) * 100);
        percentileLabel = `${percentile}th percentile (global)`;
      }
      
      // Draw orange circle overlay
      const circleRadius = (barWidth - 1) * 0.15;
      const circleX = x + barWidth / 2;
      const circleY = y + barHeight / 2;
      
      ctx.beginPath();
      ctx.fillStyle = highlightColor;
      ctx.arc(circleX, circleY, circleRadius, 0, 2 * Math.PI);
      ctx.fill();
      
      // Draw marker triangle
      ctx.beginPath();
      ctx.fillStyle = highlightColor;
      ctx.moveTo(x + barWidth / 2, y - 8);
      ctx.lineTo(x + barWidth / 2 - 5, y - 2);
      ctx.lineTo(x + barWidth / 2 + 5, y - 2);
      ctx.closePath();
      ctx.fill();

      // Add "Your Article" label
      ctx.fillStyle = highlightColor;
      ctx.textAlign = 'center';
      ctx.font = 'bold 8px Arial';
      ctx.fillText("Your Article", x + barWidth / 2, y - 18);
      
      ctx.font = '7px Arial';
      ctx.fillText(percentileLabel, x + barWidth / 2, y - 10);
    }

    // Draw average lines
    const minVal = -2;
    const maxVal = 2;
    const range = maxVal - minVal;
    
    // Global average line
    const average = values.reduce((sum, val) => sum + val, 0) / values.length;
    const avgX = padding.left + ((average - minVal) / range) * chartWidth;
    
    if (avgX >= padding.left && avgX <= width - padding.right) {
      ctx.beginPath();
      ctx.strokeStyle = hasComparison ? '#3498db' : '#666666';
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);
      ctx.moveTo(avgX, padding.top);
      ctx.lineTo(avgX, height - padding.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    
    // Comparison average line (if available)
    if (comparisonBinData && comparisonBinData.values && comparisonBinData.values.length > 0) {
      const comparisonAverage = comparisonBinData.values.reduce((sum, val) => sum + val, 0) / comparisonBinData.values.length;
      const comparisonAvgX = padding.left + ((comparisonAverage - minVal) / range) * chartWidth;
      
      if (comparisonAvgX >= padding.left && comparisonAvgX <= width - padding.right) {
        ctx.beginPath();
        ctx.strokeStyle = countryColor;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 2]);
        ctx.moveTo(comparisonAvgX, padding.top);
        ctx.lineTo(comparisonAvgX, height - padding.bottom);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }

    // Draw y-axis labels
    ctx.fillStyle = textColor;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    
    for (let i = 0; i <= 3; i++) {
      const value = maxValue * (i / 3);
      const y = height - padding.bottom - (chartHeight * (i / 3));
      
      if (hasComparison) {
        ctx.fillText((value).toFixed(1), padding.left - 3, y);
      } else {
        ctx.fillText(Math.round(value), padding.left - 3, y);
      }
    }
    
    // Draw mini legend if we have comparison data
    if (hasComparison) {
      const legendY = height - padding.bottom + 35;
      
      // Global data legend
      ctx.fillStyle = barColor;
      ctx.fillRect(padding.left, legendY, 12, 8);
      ctx.fillStyle = textColor;
      ctx.textAlign = 'left';
      ctx.font = '9px Arial';
      ctx.fillText('Global', padding.left + 16, legendY + 6);
      
      // Country data legend
      ctx.strokeStyle = countryColor;
      ctx.lineWidth = 2;
      ctx.strokeRect(padding.left + 60, legendY, 12, 8);
      ctx.fillStyle = countryColor;
      ctx.globalAlpha = 0.2;
      ctx.fillRect(padding.left + 60, legendY, 12, 8);
      ctx.globalAlpha = 1.0;
      ctx.fillStyle = textColor;
      ctx.fillText('Country', padding.left + 76, legendY + 6);
    }
  }

  // Render empty canvas
  renderEmptyCanvas(canvas, message = 'No data available') {
    const ctx = canvas.getContext('2d');
    const { textColor } = this.options;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = textColor;
    ctx.textAlign = 'center';
    ctx.font = '12px Arial';
    ctx.fillText(message, canvas.width / 2, canvas.height / 2);
  }
  
  // Populate individual country selector
  async populateCountrySelector(selector, entityName) {
    try {
      const apiUrl = `http://localhost:8000/stats/entity/available-countries?entity_name=${encodeURIComponent(entityName)}&dimension=${this.options.dimension}`;
      const response = await fetch(apiUrl);
      
      if (response.ok) {
        const data = await response.json();
        
        // Clear existing options except global
        selector.innerHTML = '<option value="">Global Comparison</option>';
        
        // Add countries with sufficient data
        data.countries.forEach(country => {
          const option = document.createElement('option');
          option.value = country.code;
          option.textContent = `${country.name} Comparison`;
          selector.appendChild(option);
        });
        
        // Cache available countries
        this.availableCountries = data.countries;
      }
    } catch (error) {
      console.warn('Could not fetch available countries for selector:', error);
      // Keep just global option on error
      selector.innerHTML = '<option value="">Global Comparison</option>';
    }
  }
  
  // Update all individual country selectors intelligently
  updateAllCountrySelectors(selectedCountry) {
    const selectors = this.container.querySelectorAll('.entity-country-selector');
    selectors.forEach(selector => {
      // Check if the selected country is available for this specific selector
      const hasCountryOption = Array.from(selector.options).some(option => option.value === selectedCountry);
      
      if (hasCountryOption) {
        // Country is available for this entity, select it
        selector.value = selectedCountry || '';
      } else {
        // Country not available for this entity, fall back to global
        selector.value = '';
      }
    });
  }
  
  // Legacy render method (kept for backward compatibility)
  render() {
    // This method is now deprecated - use renderAllEntities() instead
    console.warn('SentimentHistogram.render() is deprecated - use renderAllEntities() instead');
  }
  
}

// Export for use in popup.js
window.SentimentHistogram = SentimentHistogram;