// Entity Tracking Visualization
// This component visualizes how an entity's sentiment changes over time

class EntityTrackingViz {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.options = Object.assign({
      width: this.canvas.width,
      height: this.canvas.height,
      powerColor: '#3a86ff',
      moralColor: '#ff006e',
      gridColor: '#ddd',
      textColor: '#333',
      backgroundColor: '#f8f9fa',
      animationDuration: 1000, // ms
      showLegend: true,
      showGrid: true,
      padding: { top: 30, right: 20, bottom: 40, left: 50 },
      entityName: 'Entity',
      entityType: 'Unknown',
      dateRange: '30 days'
    }, options);
    
    this.data = [];
    this.isAnimating = false;
    this.animation = {
      startTime: 0,
      progress: 0
    };
    
    // Save chart dimensions accounting for padding
    this.chartDimensions = {
      x: this.options.padding.left,
      y: this.options.padding.top,
      width: this.options.width - this.options.padding.left - this.options.padding.right,
      height: this.options.height - this.options.padding.top - this.options.padding.bottom
    };
    
    // Initialize with empty data
    this.clear();
  }
  
  // Set data for time series
  setData(data, entityName = '', entityType = '') {
    this.data = data;
    if (entityName) this.options.entityName = entityName;
    if (entityType) this.options.entityType = entityType;
    
    // Sort data by date
    this.data.sort((a, b) => new Date(a.date) - new Date(b.date));
    
    // Start animation
    this.startAnimation();
    
    // Immediately render the first frame
    this.render(0);
  }
  
  // Start animation sequence
  startAnimation() {
    this.isAnimating = true;
    this.animation.startTime = Date.now();
    this.animation.progress = 0;
    this.animationFrame();
  }
  
  // Animation frame
  animationFrame() {
    if (!this.isAnimating) return;
    
    const now = Date.now();
    const elapsed = now - this.animation.startTime;
    this.animation.progress = Math.min(1, elapsed / this.options.animationDuration);
    
    this.render(this.animation.progress);
    
    if (this.animation.progress < 1) {
      requestAnimationFrame(() => this.animationFrame());
    } else {
      this.isAnimating = false;
    }
  }
  
  // Clear canvas and draw empty state
  clear() {
    const { width, height, backgroundColor, textColor } = this.options;
    
    // Clear canvas
    this.ctx.fillStyle = backgroundColor;
    this.ctx.fillRect(0, 0, width, height);
    
    // Draw empty state text
    this.ctx.fillStyle = textColor;
    this.ctx.textAlign = 'center';
    this.ctx.font = '12px Arial';
    this.ctx.fillText('No tracking data available', width / 2, height / 2);
    
    // Draw subtitle
    this.ctx.font = '10px Arial';
    this.ctx.fillText('Select an entity to view sentiment changes over time', width / 2, height / 2 + 20);
  }
  
  // Render the chart with animation progress (0-1)
  render(progress = 1) {
    if (!this.data || this.data.length === 0) {
      this.clear();
      return;
    }
    
    const { width, height, backgroundColor, textColor, powerColor, moralColor, gridColor } = this.options;
    
    // Clear canvas
    this.ctx.fillStyle = backgroundColor;
    this.ctx.fillRect(0, 0, width, height);
    
    // Extract chart area dimensions
    const { x, y, width: chartWidth, height: chartHeight } = this.chartDimensions;
    
    // Get data ranges
    const dates = this.data.map(d => new Date(d.date));
    const minDate = new Date(Math.min(...dates));
    const maxDate = new Date(Math.max(...dates));
    
    // Calculate time range for display
    const timeRangeMs = maxDate - minDate;
    const timeRangeDays = Math.ceil(timeRangeMs / (1000 * 60 * 60 * 24));
    
    // Update date range option
    if (timeRangeDays <= 7) {
      this.options.dateRange = `${timeRangeDays} days`;
    } else if (timeRangeDays <= 30) {
      this.options.dateRange = `${Math.ceil(timeRangeDays / 7)} weeks`;
    } else if (timeRangeDays <= 365) {
      this.options.dateRange = `${Math.ceil(timeRangeDays / 30)} months`;
    } else {
      this.options.dateRange = `${Math.ceil(timeRangeDays / 365)} years`;
    }
    
    // Draw grid if enabled
    if (this.options.showGrid) {
      this.drawGrid(minDate, maxDate);
    }
    
    // Draw X and Y axes
    this.drawAxes();
    
    // Draw data lines with animation
    this.drawLines(progress, minDate, maxDate);
    
    // Draw title and legend
    this.drawTitleAndLegend();
  }
  
  // Draw grid lines
  drawGrid(minDate, maxDate) {
    const { gridColor } = this.options;
    const { x, y, width: chartWidth, height: chartHeight } = this.chartDimensions;
    
    this.ctx.strokeStyle = gridColor;
    this.ctx.lineWidth = 0.5;
    
    // Draw horizontal grid lines (for sentiment values)
    for (let i = -2; i <= 2; i += 0.5) {
      const yPos = y + chartHeight - ((i + 2) / 4) * chartHeight;
      
      this.ctx.beginPath();
      this.ctx.moveTo(x, yPos);
      this.ctx.lineTo(x + chartWidth, yPos);
      this.ctx.stroke();
    }
    
    // Draw vertical grid lines (for dates)
    const numVerticals = Math.min(this.data.length, 6);
    const interval = chartWidth / (numVerticals - 1);
    
    for (let i = 0; i < numVerticals; i++) {
      const xPos = x + i * interval;
      
      this.ctx.beginPath();
      this.ctx.moveTo(xPos, y);
      this.ctx.lineTo(xPos, y + chartHeight);
      this.ctx.stroke();
    }
  }
  
  // Draw X and Y axes
  drawAxes() {
    const { textColor } = this.options;
    const { x, y, width: chartWidth, height: chartHeight } = this.chartDimensions;
    
    this.ctx.strokeStyle = textColor;
    this.ctx.lineWidth = 1;
    this.ctx.fillStyle = textColor;
    this.ctx.font = '10px Arial';
    
    // X-axis
    this.ctx.beginPath();
    this.ctx.moveTo(x, y + chartHeight);
    this.ctx.lineTo(x + chartWidth, y + chartHeight);
    this.ctx.stroke();
    
    // Y-axis
    this.ctx.beginPath();
    this.ctx.moveTo(x, y);
    this.ctx.lineTo(x, y + chartHeight);
    this.ctx.stroke();
    
    // Y-axis labels (-2 to 2)
    this.ctx.textAlign = 'right';
    this.ctx.textBaseline = 'middle';
    
    for (let i = -2; i <= 2; i++) {
      const yPos = y + chartHeight - ((i + 2) / 4) * chartHeight;
      
      this.ctx.fillText(i.toString(), x - 5, yPos);
    }
    
    // X-axis labels (dates)
    this.ctx.textAlign = 'center';
    this.ctx.textBaseline = 'top';
    
    // Show a reasonable number of date labels
    const numLabels = Math.min(this.data.length, 6);
    const step = Math.max(1, Math.floor(this.data.length / numLabels));
    
    for (let i = 0; i < this.data.length; i += step) {
      if (i >= this.data.length) break;
      
      const dataPoint = this.data[i];
      const date = new Date(dataPoint.date);
      const xPos = x + (i / (this.data.length - 1)) * chartWidth;
      
      // Format date as MM/DD
      const formattedDate = `${date.getMonth() + 1}/${date.getDate()}`;
      
      this.ctx.fillText(formattedDate, xPos, y + chartHeight + 5);
    }
  }
  
  // Draw data lines with animation
  drawLines(progress, minDate, maxDate) {
    const { powerColor, moralColor } = this.options;
    const { x, y, width: chartWidth, height: chartHeight } = this.chartDimensions;
    
    // Calculate how many data points to show based on animation progress
    const pointsToShow = Math.ceil(this.data.length * progress);
    const visibleData = this.data.slice(0, pointsToShow);
    
    if (visibleData.length < 2) return;
    
    // Draw power score line
    this.ctx.strokeStyle = powerColor;
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();
    
    visibleData.forEach((dataPoint, index) => {
      const xPos = x + (index / (this.data.length - 1)) * chartWidth;
      const yPos = y + chartHeight - ((dataPoint.power_score + 2) / 4) * chartHeight;
      
      if (index === 0) {
        this.ctx.moveTo(xPos, yPos);
      } else {
        this.ctx.lineTo(xPos, yPos);
      }
    });
    
    this.ctx.stroke();
    
    // Draw moral score line
    this.ctx.strokeStyle = moralColor;
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();
    
    visibleData.forEach((dataPoint, index) => {
      const xPos = x + (index / (this.data.length - 1)) * chartWidth;
      const yPos = y + chartHeight - ((dataPoint.moral_score + 2) / 4) * chartHeight;
      
      if (index === 0) {
        this.ctx.moveTo(xPos, yPos);
      } else {
        this.ctx.lineTo(xPos, yPos);
      }
    });
    
    this.ctx.stroke();
    
    // Add data points
    visibleData.forEach((dataPoint, index) => {
      const xPos = x + (index / (this.data.length - 1)) * chartWidth;
      
      // Power score point
      const powerY = y + chartHeight - ((dataPoint.power_score + 2) / 4) * chartHeight;
      this.ctx.fillStyle = powerColor;
      this.ctx.beginPath();
      this.ctx.arc(xPos, powerY, 3, 0, Math.PI * 2);
      this.ctx.fill();
      
      // Moral score point
      const moralY = y + chartHeight - ((dataPoint.moral_score + 2) / 4) * chartHeight;
      this.ctx.fillStyle = moralColor;
      this.ctx.beginPath();
      this.ctx.arc(xPos, moralY, 3, 0, Math.PI * 2);
      this.ctx.fill();
    });
    
    // Add trend indicators if we have enough data points
    if (visibleData.length >= 4) {
      this.drawTrendIndicators(visibleData);
    }
  }
  
  // Draw trend indicators (arrows showing trend direction)
  drawTrendIndicators(visibleData) {
    const { powerColor, moralColor, textColor } = this.options;
    const { x, y, width: chartWidth } = this.chartDimensions;
    
    // Calculate trends using simple linear regression
    const powerTrend = this.calculateTrend(visibleData.map(d => d.power_score));
    const moralTrend = this.calculateTrend(visibleData.map(d => d.moral_score));
    
    // Draw power trend arrow
    const lastPowerY = y + this.chartDimensions.height - 
      ((visibleData[visibleData.length - 1].power_score + 2) / 4) * this.chartDimensions.height;
    
    this.drawTrendArrow(
      x + chartWidth + 5, 
      lastPowerY, 
      powerTrend, 
      powerColor
    );
    
    // Draw moral trend arrow
    const lastMoralY = y + this.chartDimensions.height - 
      ((visibleData[visibleData.length - 1].moral_score + 2) / 4) * this.chartDimensions.height;
    
    this.drawTrendArrow(
      x + chartWidth + 5, 
      lastMoralY, 
      moralTrend, 
      moralColor
    );
  }
  
  // Draw a trend arrow
  drawTrendArrow(x, y, trend, color) {
    this.ctx.fillStyle = color;
    
    // Determine arrow direction based on trend
    if (Math.abs(trend) < 0.05) {
      // Horizontal arrow for flat trend
      this.ctx.beginPath();
      this.ctx.moveTo(x, y);
      this.ctx.lineTo(x + 10, y);
      this.ctx.lineTo(x + 8, y - 3);
      this.ctx.moveTo(x + 10, y);
      this.ctx.lineTo(x + 8, y + 3);
      this.ctx.stroke();
    } else if (trend > 0) {
      // Upward arrow for positive trend
      this.ctx.beginPath();
      this.ctx.moveTo(x, y);
      this.ctx.lineTo(x + 5, y - 8);
      this.ctx.lineTo(x + 10, y);
      this.ctx.closePath();
      this.ctx.fill();
    } else {
      // Downward arrow for negative trend
      this.ctx.beginPath();
      this.ctx.moveTo(x, y);
      this.ctx.lineTo(x + 5, y + 8);
      this.ctx.lineTo(x + 10, y);
      this.ctx.closePath();
      this.ctx.fill();
    }
  }
  
  // Calculate trend using simple linear regression
  calculateTrend(values) {
    const n = values.length;
    if (n < 2) return 0;
    
    // Create x values (0, 1, 2, ...)
    const x = Array.from({ length: n }, (_, i) => i);
    
    // Calculate means
    const meanX = x.reduce((sum, val) => sum + val, 0) / n;
    const meanY = values.reduce((sum, val) => sum + val, 0) / n;
    
    // Calculate slope (trend)
    let numerator = 0;
    let denominator = 0;
    
    for (let i = 0; i < n; i++) {
      numerator += (x[i] - meanX) * (values[i] - meanY);
      denominator += (x[i] - meanX) ** 2;
    }
    
    return denominator !== 0 ? numerator / denominator : 0;
  }
  
  // Draw title and legend
  drawTitleAndLegend() {
    const { width, textColor, powerColor, moralColor } = this.options;
    
    // Draw title
    this.ctx.fillStyle = textColor;
    this.ctx.textAlign = 'center';
    this.ctx.font = 'bold 12px Arial';
    this.ctx.fillText(
      `${this.options.entityName} (${this.options.entityType}) - Past ${this.options.dateRange}`, 
      width / 2, 
      15
    );
    
    // Draw legend if enabled
    if (this.options.showLegend) {
      const legendY = this.options.height - 15;
      const legendX1 = width / 2 - 75;
      const legendX2 = width / 2 + 25;
      
      // Power score legend
      this.ctx.fillStyle = powerColor;
      this.ctx.fillRect(legendX1, legendY, 10, 2);
      this.ctx.beginPath();
      this.ctx.arc(legendX1 + 5, legendY + 1, 3, 0, Math.PI * 2);
      this.ctx.fill();
      
      this.ctx.fillStyle = textColor;
      this.ctx.textAlign = 'left';
      this.ctx.font = '10px Arial';
      this.ctx.fillText('Power Score', legendX1 + 15, legendY + 4);
      
      // Moral score legend
      this.ctx.fillStyle = moralColor;
      this.ctx.fillRect(legendX2, legendY, 10, 2);
      this.ctx.beginPath();
      this.ctx.arc(legendX2 + 5, legendY + 1, 3, 0, Math.PI * 2);
      this.ctx.fill();
      
      this.ctx.fillStyle = textColor;
      this.ctx.fillText('Moral Score', legendX2 + 15, legendY + 4);
    }
  }
  
  // Generate random demo data (for testing)
  static generateDemoData(entityName = 'Example Entity', numPoints = 10) {
    const data = [];
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - numPoints);
    
    for (let i = 0; i < numPoints; i++) {
      const date = new Date(startDate);
      date.setDate(date.getDate() + i);
      
      // Generate slightly trending data
      const powerBase = -0.5 + (i / numPoints) * 1.5; // Trend from -0.5 to 1.0
      const moralBase = 0.2 + (i / numPoints) * 0.8;  // Trend from 0.2 to 1.0
      
      // Add some random variance
      const powerScore = Math.min(2, Math.max(-2, powerBase + (Math.random() - 0.5)));
      const moralScore = Math.min(2, Math.max(-2, moralBase + (Math.random() - 0.5)));
      
      data.push({
        date: date.toISOString(),
        power_score: powerScore,
        moral_score: moralScore
      });
    }
    
    return {
      entity_name: entityName,
      entity_type: 'Person',
      data: data
    };
  }
}

// Export for use in popup.js
window.EntityTrackingViz = EntityTrackingViz;