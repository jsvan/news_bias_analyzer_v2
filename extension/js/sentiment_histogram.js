// Sentiment Histogram Implementation
// This implements a histogram showing sentiment distribution with current article positioning

class SentimentHistogram {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    
    // Ensure canvas dimensions match HTML attributes
    this.canvas.width = 320;
    this.canvas.height = 300;
    
    this.options = Object.assign({
      width: this.canvas.width,
      height: this.canvas.height,
      barColor: '#3498db',
      highlightColor: '#ff8c00', // Orange color for current article
      textColor: '#333',
      countryColor: '#2ecc71', // Color for country-specific data
      bins: 10,
      showPercentile: true,
      animate: true,
      country: null,  // Currently selected country (null = global)
      dimension: 'power' // Track current dimension (power or moral)
    }, options);
    
    this.data = null;
    this.currentValue = null;
    this.currentBinInfo = null;
  }
  
  // Set data for histogram
  setData(data, currentValue, comparisonData = null) {
    this.data = data;          // Global data
    this.comparisonData = comparisonData; // Comparison data (country/source)
    this.currentValue = currentValue;
    this.render();
  }
  
  // Set country filter
  setCountry(country) {
    this.options.country = country;
    this.render();
  }
  
  // Set dimension (power or moral)
  setDimension(dimension) {
    this.options.dimension = dimension;
    this.render();
  }
  
  // Create bins from data
  createBins(data, numBins = 10, normalize = false) {
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
  
  // Render the histogram
  render() {
    if (!this.data || this.data.length === 0 || (this.data.length < 5 && this.data.every(val => val === 0))) {
      this.drawEmptyState("No data available for this entity");
      return;
    }
    
    const { width, height, barColor, highlightColor, countryColor, textColor, bins, showPercentile, country } = this.options;
    
    // Clear canvas and reset current bin info
    this.ctx.clearRect(0, 0, width, height);
    this.currentBinInfo = null;
    
    // Check if we have comparison data to determine normalization
    let comparisonBinData = null;
    let comparisonLabel = "";
    let hasComparison = false;
    
    if (this.comparisonData) {
      const comparisonKey = Object.keys(this.comparisonData)[0];
      if (comparisonKey && this.comparisonData[comparisonKey] && this.comparisonData[comparisonKey].length > 0) {
        const comparisonDataForBin = this.comparisonData[comparisonKey];
        comparisonBinData = this.createBins(comparisonDataForBin, bins, true); // normalize comparison
        comparisonLabel = comparisonKey;
        hasComparison = true;
      }
    }
    
    // Create bins for global data (normalize if we have comparison data)
    const binData = this.createBins(this.data, bins, hasComparison);
    const { counts, boundaries, max } = binData;
    
    
    // Find which bin contains the current value
    const currentBin = this.findBinForValue(this.currentValue, boundaries);
    
    // Calculate dimensions
    const padding = { top: 30, right: 20, bottom: 40, left: 40 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const barWidth = chartWidth / bins;
    
    // Determine maximum value for scaling
    let maxValue;
    if (hasComparison) {
      // When normalized, max value should be 1.0 for consistent scaling
      maxValue = 1.0;
    } else {
      maxValue = max;
    }
    
    
    // Draw axes
    this.ctx.beginPath();
    this.ctx.strokeStyle = textColor;
    this.ctx.lineWidth = 1;
    this.ctx.moveTo(padding.left, height - padding.bottom);
    this.ctx.lineTo(width - padding.right, height - padding.bottom);
    this.ctx.stroke();
    
    // Y-axis
    this.ctx.beginPath();
    this.ctx.moveTo(padding.left, padding.top);
    this.ctx.lineTo(padding.left, height - padding.bottom);
    this.ctx.stroke();
    
    // Draw global data bars
    counts.forEach((count, i) => {
      const x = padding.left + i * barWidth;
      const barHeight = (count / maxValue) * chartHeight;
      const y = height - padding.bottom - barHeight;

      // Draw bar (all bars are blue)
      this.ctx.fillStyle = barColor;
      this.ctx.fillRect(x, y, barWidth - 0.1, barHeight);

      // Store current bin info for later drawing (after all bars)
      if (i === currentBin) {
        this.currentBinInfo = { x, y, barWidth, barHeight };
      }

      // Draw semantic labels (only show first, middle, and last for clarity)
      if (i === 0 || i === Math.floor(bins/2) || i === bins - 1) {
        this.ctx.fillStyle = textColor;
        this.ctx.textAlign = 'center';
        this.ctx.font = '11px Arial';

        // Get semantic label based on dimension and position
        let label = '';
        const { dimension } = this.options;
        
        if (i === 0) {
          // Left side (negative values)
          label = dimension === 'power' ? 'Weak' : 'Evil';
        } else if (i === Math.floor(bins/2)) {
          // Center (neutral)
          label = 'Neutral';
        } else {
          // Right side (positive values)
          label = dimension === 'power' ? 'Strong' : 'Good';
        }

        // All labels stay horizontal for better readability
        this.ctx.fillText(
          label,
          x + barWidth / 2,
          height - padding.bottom + 15
        );
      }
    });
    
    // Draw comparison-specific bars if available
    if (comparisonBinData) {
      comparisonBinData.counts.forEach((count, i) => {
        const x = padding.left + i * barWidth;
        const barHeight = (count / maxValue) * chartHeight;
        const y = height - padding.bottom - barHeight;
        
        // Draw comparison bars as outlined bars (same width as main bars)
        this.ctx.strokeStyle = countryColor;
        this.ctx.lineWidth = 3;
        this.ctx.strokeRect(x, y, barWidth - 0.1, barHeight);
        
        // Fill with semi-transparent comparison color
        this.ctx.fillStyle = countryColor;
        this.ctx.globalAlpha = 0.3;
        this.ctx.fillRect(x, y, barWidth - 0.1, barHeight);
        this.ctx.globalAlpha = 1.0;
      });
    }
    
    // Draw y-axis labels
    this.ctx.fillStyle = textColor;
    this.ctx.textAlign = 'right';
    this.ctx.textBaseline = 'middle';
    
    // Draw a few y-axis labels
    for (let i = 0; i <= 5; i++) {
      const value = maxValue * (i / 5);
      const y = height - padding.bottom - (chartHeight * (i / 5));
      
      if (hasComparison) {
        // Show as probability (0.0 to 1.0)
        this.ctx.fillText((value).toFixed(1), padding.left - 5, y);
      } else {
        // Show as count
        this.ctx.fillText(Math.round(value), padding.left - 5, y);
      }
    }
    
    // Draw current article indicator after all bars (so it's on top)
    if (this.currentBinInfo) {
      const { x, y, barWidth, barHeight } = this.currentBinInfo;
      
      // Calculate percentile for the second line of text
      const lowerCount = this.data.filter(v => v < this.currentValue).length;
      const percentile = Math.round((lowerCount / this.data.length) * 100);
      
      // Draw orange circle overlay on the bar (slightly narrower than bar)
      const circleRadius = (barWidth - 0.1) * 0.4; // Circle slightly narrower than bar
      const circleX = x + barWidth / 2;
      const circleY = y + barHeight / 2; // Center vertically on the bar
      
      this.ctx.beginPath();
      this.ctx.fillStyle = highlightColor;
      this.ctx.arc(circleX, circleY, circleRadius, 0, 2 * Math.PI);
      this.ctx.fill();
      
      // Draw marker triangle above the bar
      this.ctx.beginPath();
      this.ctx.fillStyle = highlightColor;
      this.ctx.moveTo(x + barWidth / 2, y - 10);
      this.ctx.lineTo(x + barWidth / 2 - 7, y - 3);
      this.ctx.lineTo(x + barWidth / 2 + 7, y - 3);
      this.ctx.closePath();
      this.ctx.fill();

      // Add "Your Article" label (on top of everything)
      this.ctx.fillStyle = highlightColor;
      this.ctx.textAlign = 'center';
      this.ctx.font = 'bold 10px Arial';
      this.ctx.fillText("Your Article", x + barWidth / 2, y - 25);
      
      // Add percentile as second line
      this.ctx.font = '9px Arial';
      this.ctx.fillText(`${percentile}th percentile`, x + barWidth / 2, y - 15);
    }
    
    // Draw axes labels
    this.ctx.fillStyle = textColor;  // Reset to black for axis labels
    this.ctx.textAlign = 'center';
    this.ctx.font = '12px Arial';
    this.ctx.fillText('Sentiment Score', width / 2, height - 5);

    this.ctx.save();
    this.ctx.translate(15, height / 2);
    this.ctx.rotate(-Math.PI / 2);
    this.ctx.fillStyle = textColor;  // Reset to black for y-axis label
    this.ctx.fillText(hasComparison ? 'Probability' : 'Frequency', 0, 0);
    this.ctx.restore();
    
    // Title is now handled in HTML, not drawn on canvas
    
    // Percentile info is now part of the "Your Article" pointer above
    
    // Draw legend for comparison data
    if (comparisonBinData) {
      const legendY = padding.top + 15;
      const legendX1 = padding.left + 10;
      const legendX2 = padding.left + chartWidth / 2;
      
      // Global/All Sources legend
      this.ctx.fillStyle = barColor;
      this.ctx.fillRect(legendX1, legendY, 10, 10);
      this.ctx.fillStyle = textColor;
      this.ctx.textAlign = 'left';
      this.ctx.font = '10px Arial';
      this.ctx.fillText('All Sources', legendX1 + 15, legendY + 5);
      
      // Comparison legend (country or source)
      this.ctx.fillStyle = countryColor;
      this.ctx.fillRect(legendX2, legendY, 10, 10);
      this.ctx.fillStyle = textColor;
      this.ctx.fillText(comparisonLabel, legendX2 + 15, legendY + 5);
    }
  }
  
  // Draw empty state when no data
  drawEmptyState(message = 'No data available') {
    const { width, height, textColor } = this.options;

    this.ctx.clearRect(0, 0, width, height);
    this.ctx.fillStyle = textColor;
    this.ctx.textAlign = 'center';
    this.ctx.font = '12px Arial';
    this.ctx.fillText(message, width / 2, height / 2);

    // Draw a small legend or explanation
    this.ctx.font = '10px Arial';
    this.ctx.fillText('Analysis requires more data points for this entity', width / 2, height / 2 + 25);
  }
  
}

// Export for use in popup.js
window.SentimentHistogram = SentimentHistogram;