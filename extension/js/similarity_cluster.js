// Article Similarity Cluster Visualization
class SimilarityClusterViz {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.options = Object.assign({
      width: this.canvas.width,
      height: this.canvas.height,
      currentArticleColor: '#e74c3c',
      articleColors: ['#3a86ff', '#8338ec', '#06d6a0', '#ffbe0b'],
      backgroundColor: '#f8f9fa',
      maxNodes: 20,
      animate: true
    }, options);
    
    this.articles = [];
    this.currentArticleId = null;
    this.zoom = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    
    // Initialize interaction
    this.setupInteraction();
  }
  
  setupInteraction() {
    // Add zoom and drag functionality if needed
    this.canvas.addEventListener('mousemove', (event) => {
      const rect = this.canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      
      // Check if hovering over any node
      const hoveredNode = this.findNodeAt(x, y);
      if (hoveredNode) {
        this.canvas.style.cursor = 'pointer';
        this.hoveredNode = hoveredNode;
        this.render(); // Redraw with hover effect
      } else if (this.hoveredNode) {
        this.canvas.style.cursor = 'default';
        this.hoveredNode = null;
        this.render(); // Redraw without hover effect
      }
    });
    
    this.canvas.addEventListener('click', (event) => {
      const rect = this.canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      
      const clickedNode = this.findNodeAt(x, y);
      if (clickedNode && clickedNode.url) {
        window.open(clickedNode.url, '_blank');
      }
    });
  }
  
  findNodeAt(x, y) {
    // Find article node at the given coordinates
    const radius = 10; // Node radius for hit testing
    
    for (const article of this.articles) {
      if (!article.x || !article.y) continue;
      
      const dx = article.x - x;
      const dy = article.y - y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance <= radius) {
        return article;
      }
    }
    
    return null;
  }
  
  setData(articles, currentArticleId) {
    this.articles = articles;
    this.currentArticleId = currentArticleId;
    
    // Validate that all articles have coordinate data
    const hasCoordinates = articles.every(a => a.x !== undefined && a.y !== undefined);
    if (!hasCoordinates) {
      console.error('SimilarityClusterViz: Articles missing coordinate data. Real clustering algorithm required.');
      this.showError('Clustering data missing coordinates. Real dimensionality reduction algorithm needed.');
      return;
    }
    
    this.render();
  }
  
  showError(message) {
    const { width, height, backgroundColor } = this.options;
    
    // Clear canvas
    this.ctx.fillStyle = backgroundColor;
    this.ctx.fillRect(0, 0, width, height);
    
    // Draw error message
    this.ctx.fillStyle = '#e74c3c';
    this.ctx.textAlign = 'center';
    this.ctx.font = 'bold 14px Arial';
    this.ctx.fillText('Clustering Visualization Error', width / 2, height / 2 - 20);
    
    this.ctx.fillStyle = '#333';
    this.ctx.font = '12px Arial';
    this.ctx.fillText(message, width / 2, height / 2 + 10);
  }
  
  getArticleColor(article) {
    if (article.id === this.currentArticleId) {
      return this.options.currentArticleColor;
    }
    
    // Color by cluster if available
    if (article.cluster !== undefined) {
      const clusterIndex = Math.abs(article.cluster) % this.options.articleColors.length;
      return this.options.articleColors[clusterIndex];
    }
    
    // Default color for unclustered articles
    return '#8d99ae';
  }
  
  render() {
    const { width, height, backgroundColor } = this.options;
    
    // Clear canvas
    this.ctx.fillStyle = backgroundColor;
    this.ctx.fillRect(0, 0, width, height);
    
    // Draw connecting lines between similar articles
    this.drawConnections();
    
    // Draw each article node
    this.articles.forEach(article => {
      this.drawArticleNode(article);
    });
    
    // Draw tooltips for hovered node
    if (this.hoveredNode) {
      this.drawTooltip(this.hoveredNode);
    }
  }
  
  drawConnections() {
    // Only draw connections to/from the current article
    const currentArticle = this.articles.find(a => a.id === this.currentArticleId);
    if (!currentArticle) return;
    
    this.articles.forEach(article => {
      if (article.id === this.currentArticleId) return;
      
      const similarity = article.similarity || 0;
      if (similarity > 0.5) {
        // Higher similarity = more visible line
        const alpha = Math.min(1, (similarity - 0.5) * 2);
        this.ctx.strokeStyle = `rgba(0, 0, 0, ${alpha * 0.3})`;
        this.ctx.lineWidth = 1 + similarity;
        
        this.ctx.beginPath();
        this.ctx.moveTo(currentArticle.x, currentArticle.y);
        this.ctx.lineTo(article.x, article.y);
        this.ctx.stroke();
      }
    });
  }
  
  drawArticleNode(article) {
    if (!article.x || !article.y) return;
    
    const isCurrentArticle = article.id === this.currentArticleId;
    const isHovered = this.hoveredNode === article;
    const radius = isCurrentArticle ? 10 : (isHovered ? 9 : 7);
    
    // Draw node
    this.ctx.fillStyle = this.getArticleColor(article);
    this.ctx.beginPath();
    this.ctx.arc(article.x, article.y, radius, 0, Math.PI * 2);
    this.ctx.fill();
    
    // Add border for current article
    if (isCurrentArticle || isHovered) {
      this.ctx.strokeStyle = '#333';
      this.ctx.lineWidth = 2;
      this.ctx.stroke();
    }
    
    // Label for current article
    if (isCurrentArticle) {
      this.ctx.fillStyle = '#333';
      this.ctx.textAlign = 'center';
      this.ctx.font = 'bold 10px Arial';
      this.ctx.fillText('Current', article.x, article.y - 15);
    }
  }
  
  drawTooltip(article) {
    const x = article.x;
    const y = article.y - 15;
    
    const title = article.title || 'Article';
    const source = article.source || 'Unknown Source';
    const similarity = article.similarity ? `${Math.round(article.similarity * 100)}%` : '';
    
    // Measure text for tooltip size
    this.ctx.font = '10px Arial';
    const titleWidth = this.ctx.measureText(title).width;
    const sourceWidth = this.ctx.measureText(source).width;
    const boxWidth = Math.max(titleWidth, sourceWidth) + 20;
    
    // Draw tooltip box
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
    this.ctx.beginPath();
    this.ctx.roundRect(x - boxWidth / 2, y - 40, boxWidth, 30, 4);
    this.ctx.fill();
    
    // Draw tooltip text
    this.ctx.fillStyle = '#fff';
    this.ctx.textAlign = 'center';
    this.ctx.font = 'bold 10px Arial';
    this.ctx.fillText(title, x, y - 25);
    
    this.ctx.font = '9px Arial';
    this.ctx.fillText(`${source} ${similarity}`, x, y - 15);
  }
}

// Add to window object for use in popup.js
window.SimilarityClusterViz = SimilarityClusterViz;