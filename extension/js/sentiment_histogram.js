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
      isMockData: false // Flag to indicate if data is real or mock
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
  
  // Create bins from data
  createBins(data, numBins = 10) {
    if (!data || data.length === 0) return [];
    
    // Find min and max values
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min;
    const binWidth = range / numBins;
    
    // Initialize bins
    const bins = Array(numBins).fill(0);
    
    // Count values in each bin
    data.forEach(value => {
      // Handle edge case for max value
      if (value === max) {
        bins[numBins - 1]++;
      } else {
        const binIndex = Math.floor((value - min) / binWidth);
        bins[binIndex < 0 ? 0 : (binIndex >= numBins ? numBins - 1 : binIndex)]++;
      }
    });
    
    // Calculate bin boundaries for labels
    const binBoundaries = Array(numBins + 1).fill(0).map((_, i) => min + i * binWidth);
    
    return {
      counts: bins,
      boundaries: binBoundaries,
      max: Math.max(...bins)
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
    
    // Create bins for global data
    const binData = this.createBins(this.data, bins);
    const { counts, boundaries, max } = binData;
    
    // Create bins for comparison data if available
    let comparisonBinData = null;
    let comparisonLabel = "";
    
    if (this.comparisonData) {
      const comparisonKey = Object.keys(this.comparisonData)[0];
      if (comparisonKey && this.comparisonData[comparisonKey] && this.comparisonData[comparisonKey].length >= 3) {
        const comparisonDataForBin = this.comparisonData[comparisonKey];
        comparisonBinData = this.createBins(comparisonDataForBin, bins);
        comparisonLabel = comparisonKey;
      }
    }
    
    // Find which bin contains the current value
    const currentBin = this.findBinForValue(this.currentValue, boundaries);
    
    // Calculate dimensions
    const padding = { top: 30, right: 20, bottom: 40, left: 40 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const barWidth = chartWidth / bins;
    
    // Determine maximum value for scaling
    const maxValue = comparisonBinData ? Math.max(max, comparisonBinData.max) : max;
    
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

      // Draw bar
      this.ctx.fillStyle = i === currentBin ? highlightColor : barColor;
      this.ctx.fillRect(x, y, barWidth - 0.1, barHeight);

      // Store current bin info for later drawing (after all bars)
      if (i === currentBin) {
        this.currentBinInfo = { x, y, barWidth };
      }

      // Draw bin boundary label (only show first, middle, and last for clarity)
      if (i === 0 || i === Math.floor(bins/2) || i === bins - 1) {
        this.ctx.fillStyle = textColor;
        this.ctx.textAlign = 'center';
        this.ctx.font = '10px Arial';

        // For middle and last labels, rotate them slightly to avoid overlap
        if (i !== 0) {
          this.ctx.save();
          this.ctx.translate(x + barWidth / 2, height - padding.bottom + 15);
          this.ctx.rotate(Math.PI / 6); // 30 degrees rotation
          this.ctx.fillText(boundaries[i].toFixed(1), 0, 0);
          this.ctx.restore();
        } else {
          // First label stays horizontal
          this.ctx.fillText(
            boundaries[i].toFixed(1),
            x + barWidth / 2,
            height - padding.bottom + 15
          );
        }
      }
    });
    
    // Draw comparison-specific bars if available
    if (comparisonBinData) {
      comparisonBinData.counts.forEach((count, i) => {
        const x = padding.left + i * barWidth + barWidth / 4;
        const barHeight = (count / maxValue) * chartHeight;
        const y = height - padding.bottom - barHeight;
        const narrowBarWidth = barWidth / 2;
        
        // Draw comparison bar overlay
        this.ctx.fillStyle = countryColor;
        this.ctx.globalAlpha = 0.7;
        this.ctx.fillRect(x, y, narrowBarWidth, barHeight);
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
      this.ctx.fillText(Math.round(value), padding.left - 5, y);
    }
    
    // Draw current article indicator after all bars (so it's on top)
    if (this.currentBinInfo) {
      const { x, y, barWidth } = this.currentBinInfo;
      
      // Calculate percentile for the second line of text
      const lowerCount = this.data.filter(v => v < this.currentValue).length;
      const percentile = Math.round((lowerCount / this.data.length) * 100);
      
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
    this.ctx.fillText('Frequency', 0, 0);
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