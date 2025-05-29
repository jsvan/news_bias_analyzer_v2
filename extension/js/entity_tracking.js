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
      confidenceColor: 'rgba(58, 134, 255, 0.2)', // Light blue for confidence intervals
      gridColor: '#ddd',
      textColor: '#333',
      backgroundColor: '#f8f9fa',
      animationDuration: 1000, // ms
      showLegend: false,
      showGrid: true,
      showConfidenceIntervals: true,
      padding: { top: 40, right: 20, bottom: 20, left: 50 },
      entityName: 'Entity',
      entityType: 'Unknown',
      dateRange: '30 days',
      isMockData: false // Flag to indicate if data is real or mocked
    }, options);
    
    this.data = [];
    this.isAnimating = false;
    this.animation = {
      startTime: 0,
      progress: 0
    };
    
    // Hover state
    this.isHovering = false;
    this.hoveredLine = null;
    this.mousePos = { x: 0, y: 0 };
    
    // Add mouse event listeners
    this.setupMouseEvents();
    
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
  
  // Setup mouse event listeners for hover functionality
  setupMouseEvents() {
    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      this.mousePos.x = e.clientX - rect.left;
      this.mousePos.y = e.clientY - rect.top;
      this.checkHover();
    });
    
    this.canvas.addEventListener('mouseleave', () => {
      this.isHovering = false;
      this.hoveredLine = null;
      this.canvas.style.cursor = 'default';
      this.redrawWithTooltip();
    });
  }
  
  // Check if mouse is hovering over a line
  checkHover() {
    if (!this.data || this.data.length === 0) return;
    
    const { x, y, width: chartWidth, height: chartHeight } = this.chartDimensions;
    const tolerance = 8; // Pixels tolerance for line detection
    
    let closestLine = null;
    let minDistance = Infinity;
    
    // Check each data point for proximity to lines
    for (let i = 0; i < this.data.length - 1; i++) {
      const x1 = x + (i / (this.data.length - 1)) * chartWidth;
      const x2 = x + ((i + 1) / (this.data.length - 1)) * chartWidth;
      
      // Check if mouse X is between these two points
      if (this.mousePos.x >= x1 && this.mousePos.x <= x2) {
        // Check Source Power line
        const y1_power = y + chartHeight - ((this.data[i].power_score + 2) / 4) * chartHeight;
        const y2_power = y + chartHeight - ((this.data[i + 1].power_score + 2) / 4) * chartHeight;
        const interpY_power = y1_power + ((this.mousePos.x - x1) / (x2 - x1)) * (y2_power - y1_power);
        const distance_power = Math.abs(this.mousePos.y - interpY_power);
        
        if (distance_power < tolerance && distance_power < minDistance) {
          minDistance = distance_power;
          closestLine = 'Source Power';
        }
        
        // Check Source Moral line
        const y1_moral = y + chartHeight - ((this.data[i].moral_score + 2) / 4) * chartHeight;
        const y2_moral = y + chartHeight - ((this.data[i + 1].moral_score + 2) / 4) * chartHeight;
        const interpY_moral = y1_moral + ((this.mousePos.x - x1) / (x2 - x1)) * (y2_moral - y1_moral);
        const distance_moral = Math.abs(this.mousePos.y - interpY_moral);
        
        if (distance_moral < tolerance && distance_moral < minDistance) {
          minDistance = distance_moral;
          closestLine = 'Source Moral';
        }
        
        // Check Global Power line (if available)
        if (this.data[i].global_power_avg !== undefined) {
          const y1_global_power = y + chartHeight - ((this.data[i].global_power_avg + 2) / 4) * chartHeight;
          const y2_global_power = y + chartHeight - ((this.data[i + 1].global_power_avg + 2) / 4) * chartHeight;
          const interpY_global_power = y1_global_power + ((this.mousePos.x - x1) / (x2 - x1)) * (y2_global_power - y1_global_power);
          const distance_global_power = Math.abs(this.mousePos.y - interpY_global_power);
          
          if (distance_global_power < tolerance && distance_global_power < minDistance) {
            minDistance = distance_global_power;
            closestLine = 'Global Power';
          }
        }
        
        // Check Global Moral line (if available)
        if (this.data[i].global_moral_avg !== undefined) {
          const y1_global_moral = y + chartHeight - ((this.data[i].global_moral_avg + 2) / 4) * chartHeight;
          const y2_global_moral = y + chartHeight - ((this.data[i + 1].global_moral_avg + 2) / 4) * chartHeight;
          const interpY_global_moral = y1_global_moral + ((this.mousePos.x - x1) / (x2 - x1)) * (y2_global_moral - y1_global_moral);
          const distance_global_moral = Math.abs(this.mousePos.y - interpY_global_moral);
          
          if (distance_global_moral < tolerance && distance_global_moral < minDistance) {
            minDistance = distance_global_moral;
            closestLine = 'Global Moral';
          }
        }
        
        break;
      }
    }
    
    // Update hover state
    const wasHovering = this.isHovering;
    const previousLine = this.hoveredLine;
    
    this.isHovering = closestLine !== null;
    this.hoveredLine = closestLine;
    this.canvas.style.cursor = this.isHovering ? 'pointer' : 'default';
    
    // Redraw if hover state changed
    if (wasHovering !== this.isHovering || previousLine !== this.hoveredLine) {
      this.redrawWithTooltip();
    }
  }
  
  // Redraw chart with tooltip if hovering
  redrawWithTooltip() {
    if (!this.isAnimating) {
      this.render(1); // Render at full progress
      
      if (this.isHovering && this.hoveredLine) {
        this.drawTooltip();
      }
    }
  }
  
  // Draw tooltip for hovered line
  drawTooltip() {
    if (!this.hoveredLine) return;
    
    const { textColor, powerColor, moralColor } = this.options;
    
    // Get line properties
    let lineColor, isDashed, tooltipText;
    switch (this.hoveredLine) {
      case 'Source Power':
        lineColor = powerColor;
        isDashed = true;
        tooltipText = 'Source Power';
        break;
      case 'Source Moral':
        lineColor = moralColor;
        isDashed = true;
        tooltipText = 'Source Moral';
        break;
      case 'Global Power':
        lineColor = powerColor;
        isDashed = false;
        tooltipText = 'Global Power';
        break;
      case 'Global Moral':
        lineColor = moralColor;
        isDashed = false;
        tooltipText = 'Global Moral';
        break;
    }
    
    // Calculate tooltip dimensions
    this.ctx.font = '11px Arial';
    const textWidth = this.ctx.measureText(tooltipText).width;
    const lineWidth = 20;
    const padding = 8;
    const gap = 6;
    const tooltipWidth = lineWidth + gap + textWidth + padding * 2;
    const tooltipHeight = 24;
    
    let tooltipX = this.mousePos.x - tooltipWidth / 2;
    let tooltipY = this.mousePos.y - tooltipHeight - 10;
    
    // Ensure tooltip stays within canvas bounds
    if (tooltipX < 5) tooltipX = 5;
    if (tooltipX + tooltipWidth > this.canvas.width - 5) {
      tooltipX = this.canvas.width - tooltipWidth - 5;
    }
    if (tooltipY < 5) {
      tooltipY = this.mousePos.y + 15;
    }
    
    // Draw tooltip background with rounded corners and shadow
    this.ctx.save();
    
    // Shadow
    this.ctx.shadowColor = 'rgba(0, 0, 0, 0.2)';
    this.ctx.shadowBlur = 4;
    this.ctx.shadowOffsetX = 2;
    this.ctx.shadowOffsetY = 2;
    
    // Background
    this.ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
    this.ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)';
    this.ctx.lineWidth = 1;
    
    // Rounded rectangle
    const radius = 4;
    this.ctx.beginPath();
    this.ctx.moveTo(tooltipX + radius, tooltipY);
    this.ctx.lineTo(tooltipX + tooltipWidth - radius, tooltipY);
    this.ctx.quadraticCurveTo(tooltipX + tooltipWidth, tooltipY, tooltipX + tooltipWidth, tooltipY + radius);
    this.ctx.lineTo(tooltipX + tooltipWidth, tooltipY + tooltipHeight - radius);
    this.ctx.quadraticCurveTo(tooltipX + tooltipWidth, tooltipY + tooltipHeight, tooltipX + tooltipWidth - radius, tooltipY + tooltipHeight);
    this.ctx.lineTo(tooltipX + radius, tooltipY + tooltipHeight);
    this.ctx.quadraticCurveTo(tooltipX, tooltipY + tooltipHeight, tooltipX, tooltipY + tooltipHeight - radius);
    this.ctx.lineTo(tooltipX, tooltipY + radius);
    this.ctx.quadraticCurveTo(tooltipX, tooltipY, tooltipX + radius, tooltipY);
    this.ctx.closePath();
    this.ctx.fill();
    this.ctx.stroke();
    
    this.ctx.restore();
    
    // Draw line sample
    const lineY = tooltipY + tooltipHeight / 2;
    const lineStartX = tooltipX + padding;
    const lineEndX = lineStartX + lineWidth;
    
    this.ctx.strokeStyle = lineColor;
    this.ctx.lineWidth = 2;
    
    if (isDashed) {
      this.ctx.setLineDash([4, 2]);
    } else {
      this.ctx.setLineDash([]);
      this.ctx.globalAlpha = 0.8;
    }
    
    this.ctx.beginPath();
    this.ctx.moveTo(lineStartX, lineY);
    this.ctx.lineTo(lineEndX, lineY);
    this.ctx.stroke();
    
    this.ctx.globalAlpha = 1;
    this.ctx.setLineDash([]);
    
    // Draw text
    this.ctx.fillStyle = '#333';
    this.ctx.textAlign = 'left';
    this.ctx.textBaseline = 'middle';
    this.ctx.font = '11px Arial';
    this.ctx.fillText(tooltipText, lineEndX + gap, lineY);
  }
  
  // Set data for time series
  setData(data, entityName = '', entityType = '') {
    this.data = data;
    if (entityName) this.options.entityName = entityName;
    if (entityType) this.options.entityType = entityType;
    
    // Sort data by date
    if (this.data && this.data.length > 0) {
      this.data.sort((a, b) => new Date(a.date) - new Date(b.date));
      
      // Start animation
      this.startAnimation();
      
      // Immediately render the first frame
      this.render(0);
    } else {
      // If no data, show empty state
      this.clear();
    }
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
    this.ctx.fillText('Not enough data points collected for this entity', width / 2, height / 2 + 20);
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
    const { powerColor, moralColor, confidenceColor, showConfidenceIntervals } = this.options;
    const { x, y, width: chartWidth, height: chartHeight } = this.chartDimensions;
    
    // Calculate how many data points to show based on animation progress
    const pointsToShow = Math.ceil(this.data.length * progress);
    const visibleData = this.data.slice(0, pointsToShow);
    
    if (visibleData.length < 2) return;
    
    // Draw global confidence intervals first (if available and enabled)
    if (showConfidenceIntervals && visibleData[0].global_power_ci_lower !== undefined) {
      console.log('Drawing confidence intervals for entity tracking');
      this.drawGlobalConfidenceIntervals(visibleData);
    } else if (showConfidenceIntervals) {
      console.log('Confidence intervals not available - missing global_power_ci_lower field');
      console.log('Sample data point:', visibleData[0]);
    }
    
    // Draw global average lines if available
    if (visibleData[0].global_power_avg !== undefined) {
      // Global power average (solid line)
      this.ctx.strokeStyle = powerColor;
      this.ctx.lineWidth = this.hoveredLine === 'Global Power' ? 3 : 2;
      this.ctx.setLineDash([]);
      this.ctx.globalAlpha = this.hoveredLine === 'Global Power' ? 1.0 : 0.7;
      this.ctx.beginPath();
      
      visibleData.forEach((dataPoint, index) => {
        const xPos = x + (index / (this.data.length - 1)) * chartWidth;
        const yPos = y + chartHeight - ((dataPoint.global_power_avg + 2) / 4) * chartHeight;
        
        if (index === 0) {
          this.ctx.moveTo(xPos, yPos);
        } else {
          this.ctx.lineTo(xPos, yPos);
        }
      });
      
      this.ctx.stroke();
      
      // Global moral average (solid line)
      this.ctx.strokeStyle = moralColor;
      this.ctx.lineWidth = this.hoveredLine === 'Global Moral' ? 3 : 2;
      this.ctx.globalAlpha = this.hoveredLine === 'Global Moral' ? 1.0 : 0.7;
      this.ctx.beginPath();
      
      visibleData.forEach((dataPoint, index) => {
        const xPos = x + (index / (this.data.length - 1)) * chartWidth;
        const yPos = y + chartHeight - ((dataPoint.global_moral_avg + 2) / 4) * chartHeight;
        
        if (index === 0) {
          this.ctx.moveTo(xPos, yPos);
        } else {
          this.ctx.lineTo(xPos, yPos);
        }
      });
      
      this.ctx.stroke();
      
      // Reset alpha
      this.ctx.globalAlpha = 1;
    }
    
    // Draw source-specific power score line (dashed)
    this.ctx.strokeStyle = powerColor;
    this.ctx.lineWidth = this.hoveredLine === 'Source Power' ? 3 : 2;
    this.ctx.setLineDash([5, 5]);
    this.ctx.globalAlpha = this.hoveredLine === 'Source Power' ? 1.0 : 0.9;
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
    this.ctx.globalAlpha = 1;
    
    // Draw source-specific moral score line (dashed)
    this.ctx.strokeStyle = moralColor;
    this.ctx.lineWidth = this.hoveredLine === 'Source Moral' ? 3 : 2;
    this.ctx.setLineDash([5, 5]);
    this.ctx.globalAlpha = this.hoveredLine === 'Source Moral' ? 1.0 : 0.9;
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
    this.ctx.globalAlpha = 1;
    
    // Reset line style
    this.ctx.setLineDash([]);
    
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
  }
  
  // Draw confidence intervals for global averages as shaded areas
  drawGlobalConfidenceIntervals(visibleData) {
    const { confidenceColor } = this.options;
    const { x, y, width: chartWidth, height: chartHeight } = this.chartDimensions;
    
    this.ctx.fillStyle = confidenceColor;
    
    // Draw power score confidence interval
    this.ctx.beginPath();
    
    // Draw upper boundary
    visibleData.forEach((dataPoint, index) => {
      if (dataPoint.global_power_ci_upper === undefined) return;
      const xPos = x + (index / (this.data.length - 1)) * chartWidth;
      const yPos = y + chartHeight - ((dataPoint.global_power_ci_upper + 2) / 4) * chartHeight;
      
      if (index === 0) {
        this.ctx.moveTo(xPos, yPos);
      } else {
        this.ctx.lineTo(xPos, yPos);
      }
    });
    
    // Draw lower boundary (in reverse order to close the path)
    for (let index = visibleData.length - 1; index >= 0; index--) {
      const dataPoint = visibleData[index];
      if (dataPoint.global_power_ci_lower === undefined) continue;
      const xPos = x + (index / (this.data.length - 1)) * chartWidth;
      const yPos = y + chartHeight - ((dataPoint.global_power_ci_lower + 2) / 4) * chartHeight;
      this.ctx.lineTo(xPos, yPos);
    }
    
    this.ctx.closePath();
    this.ctx.fill();
    
    // Draw moral score confidence interval
    this.ctx.beginPath();
    
    // Draw upper boundary
    visibleData.forEach((dataPoint, index) => {
      if (dataPoint.global_moral_ci_upper === undefined) return;
      const xPos = x + (index / (this.data.length - 1)) * chartWidth;
      const yPos = y + chartHeight - ((dataPoint.global_moral_ci_upper + 2) / 4) * chartHeight;
      
      if (index === 0) {
        this.ctx.moveTo(xPos, yPos);
      } else {
        this.ctx.lineTo(xPos, yPos);
      }
    });
    
    // Draw lower boundary (in reverse order to close the path)
    for (let index = visibleData.length - 1; index >= 0; index--) {
      const dataPoint = visibleData[index];
      if (dataPoint.global_moral_ci_lower === undefined) continue;
      const xPos = x + (index / (this.data.length - 1)) * chartWidth;
      const yPos = y + chartHeight - ((dataPoint.global_moral_ci_lower + 2) / 4) * chartHeight;
      this.ctx.lineTo(xPos, yPos);
    }
    
    this.ctx.closePath();
    this.ctx.fill();
  }
  
  
  // Draw title
  drawTitleAndLegend() {
    const { width, textColor } = this.options;
    
    // Draw title
    this.ctx.fillStyle = textColor;
    this.ctx.textAlign = 'center';
    this.ctx.font = 'bold 12px Arial';
    this.ctx.fillText(
      `${this.options.entityName} (${this.options.entityType}) - Past ${this.options.dateRange}`, 
      width / 2, 
      15
    );
  }
  
}

// Export for use in popup.js
window.EntityTrackingViz = EntityTrackingViz;