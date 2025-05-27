// Topic Cluster Visualization
// This implements a force-directed graph visualization for topic clusters

class TopicClusterViz {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.options = Object.assign({
      width: this.canvas.width,
      height: this.canvas.height,
      backgroundColor: '#f8f9fa',
      textColor: '#333',
      nodeColors: ['#3a86ff', '#8338ec', '#ff006e', '#fb5607', '#ffbe0b', '#06d6a0'],
      selectedNodeColor: '#ff006e',
      nodeRadius: 10,
      linkColor: 'rgba(200, 200, 200, 0.5)',
      repulsionForce: 100,
      gravityForce: 0.05,
      linkStrength: 0.7,
      nodeCharge: -50,
      damping: 0.9,
      animate: true,
      tooltips: true
    }, options);
    
    this.nodes = [];
    this.links = [];
    this.simulationActive = false;
    this.selectedNode = null;
    this.hoveredNode = null;
    this.isDragging = false;
    this.draggedNode = null;
    
    // Node force simulation variables
    this.simulation = {
      alpha: 1,
      alphaMin: 0.001,
      alphaDecay: 0.02
    };
    
    // Init interaction
    this.initializeInteractions();
    
    // Initialize with placeholder text
    this.clear();
  }
  
  // Initialize mouse/touch interactions
  initializeInteractions() {
    // Mouse move (hover)
    this.canvas.addEventListener('mousemove', (event) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = event.clientX - rect.left;
      const mouseY = event.clientY - rect.top;
      
      if (this.isDragging && this.draggedNode) {
        // Update dragged node position
        this.draggedNode.x = mouseX;
        this.draggedNode.y = mouseY;
        this.draggedNode.vx = 0;
        this.draggedNode.vy = 0;
        this.render();
        return;
      }
      
      // Check if mouse is over a node
      const node = this.findNodeAt(mouseX, mouseY);
      
      if (node !== this.hoveredNode) {
        this.hoveredNode = node;
        this.canvas.style.cursor = node ? 'pointer' : 'default';
        this.render();
      }
    });
    
    // Mouse down (select/drag)
    this.canvas.addEventListener('mousedown', (event) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = event.clientX - rect.left;
      const mouseY = event.clientY - rect.top;
      
      const node = this.findNodeAt(mouseX, mouseY);
      
      if (node) {
        this.isDragging = true;
        this.draggedNode = node;
        
        if (node !== this.selectedNode) {
          this.selectedNode = node;
          this.render();
          
          // Trigger selection callback if provided
          if (this.options.onNodeSelected) {
            this.options.onNodeSelected(node);
          }
        }
      }
    });
    
    // Mouse up (end drag)
    document.addEventListener('mouseup', () => {
      this.isDragging = false;
      this.draggedNode = null;
    });
    
    // Mouse leave
    this.canvas.addEventListener('mouseleave', () => {
      this.hoveredNode = null;
      this.render();
    });
  }
  
  // Find node at position
  findNodeAt(x, y) {
    return this.nodes.find(node => {
      const dx = node.x - x;
      const dy = node.y - y;
      return Math.sqrt(dx * dx + dy * dy) <= this.options.nodeRadius;
    });
  }
  
  // Set data
  setData(data) {
    if (!data || !data.nodes || !data.links) {
      this.clear();
      return;
    }
    
    this.nodes = data.nodes.map(node => ({
      ...node,
      x: this.options.width * Math.random(),
      y: this.options.height * Math.random(),
      vx: 0,
      vy: 0,
      radius: node.size ? 
        Math.max(5, Math.min(15, this.options.nodeRadius * (node.size || 1))) :
        this.options.nodeRadius
    }));
    
    this.links = data.links.map(link => {
      const source = this.nodes.find(n => n.id === link.source);
      const target = this.nodes.find(n => n.id === link.target);
      
      if (!source || !target) {
        console.warn('Link references missing node:', link);
        return null;
      }
      
      return {
        ...link,
        source,
        target
      };
    }).filter(Boolean);
    
    // Start simulation
    this.startSimulation();
  }
  
  // Clear and reset
  clear() {
    const { width, height, backgroundColor, textColor } = this.options;
    
    // Clear canvas
    this.ctx.fillStyle = backgroundColor;
    this.ctx.fillRect(0, 0, width, height);
    
    // Draw placeholder text
    this.ctx.fillStyle = textColor;
    this.ctx.font = '12px Arial';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('No topic cluster data available', width / 2, height / 2 - 10);
    this.ctx.font = '10px Arial';
    this.ctx.fillText('Topics will appear as clusters based on entity relationships', width / 2, height / 2 + 10);
    
    // Reset state
    this.nodes = [];
    this.links = [];
    this.simulationActive = false;
    this.selectedNode = null;
    this.hoveredNode = null;
  }
  
  // Start force simulation
  startSimulation() {
    this.simulationActive = true;
    this.simulation.alpha = 1;
    
    // Start animation loop
    if (this.options.animate) {
      this.animateFrame();
    } else {
      // Run simulation until settled
      while (this.simulation.alpha > this.simulation.alphaMin) {
        this.updateSimulation();
      }
      this.render();
    }
  }
  
  // Update simulation (one step)
  updateSimulation() {
    if (this.simulation.alpha < this.simulation.alphaMin) {
      this.simulationActive = false;
      return;
    }
    
    // Reduce alpha (temperature)
    this.simulation.alpha *= (1 - this.simulation.alphaDecay);
    
    // Apply forces
    this.applyForces();
    
    // Update positions
    this.nodes.forEach(node => {
      if (node === this.draggedNode) return; // Skip if being dragged
      
      // Update position based on velocity
      node.x += node.vx;
      node.y += node.vy;
      
      // Apply damping
      node.vx *= this.options.damping;
      node.vy *= this.options.damping;
      
      // Constrain to canvas
      node.x = Math.max(node.radius, Math.min(this.options.width - node.radius, node.x));
      node.y = Math.max(node.radius, Math.min(this.options.height - node.radius, node.y));
    });
  }
  
  // Apply forces to nodes
  applyForces() {
    const { repulsionForce, gravityForce, linkStrength, nodeCharge } = this.options;
    
    // Apply repulsion between nodes
    for (let i = 0; i < this.nodes.length; i++) {
      const nodeA = this.nodes[i];
      
      for (let j = i + 1; j < this.nodes.length; j++) {
        const nodeB = this.nodes[j];
        
        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const distSq = dx * dx + dy * dy;
        const dist = Math.sqrt(distSq);
        
        if (dist === 0) continue;
        
        // Calculate repulsion (inverse square law)
        const force = (repulsionForce * nodeCharge) / distSq;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        
        nodeA.vx -= fx * this.simulation.alpha;
        nodeA.vy -= fy * this.simulation.alpha;
        nodeB.vx += fx * this.simulation.alpha;
        nodeB.vy += fy * this.simulation.alpha;
      }
    }
    
    // Apply gravity to center
    const centerX = this.options.width / 2;
    const centerY = this.options.height / 2;
    
    this.nodes.forEach(node => {
      const dx = centerX - node.x;
      const dy = centerY - node.y;
      node.vx += dx * gravityForce * this.simulation.alpha;
      node.vy += dy * gravityForce * this.simulation.alpha;
    });
    
    // Apply link forces
    this.links.forEach(link => {
      const dx = link.target.x - link.source.x;
      const dy = link.target.y - link.source.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      
      if (dist === 0) return;
      
      // Strength proportional to weight if available
      const strength = link.weight ? linkStrength * link.weight : linkStrength;
      
      // Apply force proportional to distance
      const force = strength * dist * this.simulation.alpha;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      
      link.source.vx += fx;
      link.source.vy += fy;
      link.target.vx -= fx;
      link.target.vy -= fy;
    });
  }
  
  // Animation frame loop
  animateFrame() {
    if (!this.simulationActive) return;
    
    this.updateSimulation();
    this.render();
    
    if (this.simulationActive) {
      requestAnimationFrame(() => this.animateFrame());
    }
  }
  
  // Render visualization
  render() {
    const { width, height, backgroundColor, linkColor, nodeColors } = this.options;
    
    // Clear canvas
    this.ctx.fillStyle = backgroundColor;
    this.ctx.fillRect(0, 0, width, height);
    
    if (this.nodes.length === 0) {
      this.clear();
      return;
    }
    
    // Draw links
    this.ctx.strokeStyle = linkColor;
    this.ctx.lineWidth = 1;
    
    this.links.forEach(link => {
      // Adjust opacity based on weight if available
      const opacity = link.weight ? Math.max(0.1, Math.min(0.8, link.weight)) : 0.5;
      this.ctx.strokeStyle = linkColor.replace(')', `, ${opacity})`).replace('rgba', 'rgba');
      
      this.ctx.beginPath();
      this.ctx.moveTo(link.source.x, link.source.y);
      this.ctx.lineTo(link.target.x, link.target.y);
      this.ctx.stroke();
    });
    
    // Draw nodes
    this.nodes.forEach(node => {
      // Select color based on cluster/group if available
      let colorIndex = node.group !== undefined ? 
        (node.group % nodeColors.length) : 
        (node.cluster !== undefined ? node.cluster % nodeColors.length : 0);
      
      // Use selected color if this node is selected
      const isSelected = node === this.selectedNode;
      const isHovered = node === this.hoveredNode;
      
      let nodeColor = isSelected ? 
        this.options.selectedNodeColor : 
        nodeColors[colorIndex];
      
      // Draw node circle
      this.ctx.fillStyle = nodeColor;
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      this.ctx.fill();
      
      // Add stroke for hover/selection
      if (isSelected || isHovered) {
        this.ctx.strokeStyle = '#333';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
      }
      
      // Draw node label
      this.ctx.fillStyle = '#fff';
      this.ctx.font = isSelected ? 'bold 10px Arial' : '9px Arial';
      this.ctx.textAlign = 'center';
      this.ctx.textBaseline = 'middle';
      
      // Only show label if node is larger than a minimum size
      if (node.radius >= 8) {
        this.ctx.fillText(node.label.substring(0, 1), node.x, node.y);
      }
    });
    
    // Draw tooltips
    if (this.options.tooltips && (this.hoveredNode || this.selectedNode)) {
      const node = this.hoveredNode || this.selectedNode;
      this.drawTooltip(node);
    }
    
    // Draw legend
    this.drawLegend();
  }
  
  // Draw tooltip for a node
  drawTooltip(node) {
    const { textColor } = this.options;
    
    const tooltip = {
      x: node.x,
      y: node.y - node.radius - 5,
      text: node.label || 'Topic',
      subtext: `${node.count || 0} entities`
    };
    
    // Measure text size
    this.ctx.font = 'bold 10px Arial';
    const labelWidth = this.ctx.measureText(tooltip.text).width;
    
    this.ctx.font = '9px Arial';
    const sublabelWidth = this.ctx.measureText(tooltip.subtext).width;
    
    const width = Math.max(labelWidth, sublabelWidth) + 16;
    const height = 32;
    
    // Draw tooltip background
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
    this.ctx.beginPath();
    this.ctx.roundRect(
      tooltip.x - width / 2, 
      tooltip.y - height, 
      width, 
      height, 
      4
    );
    this.ctx.fill();
    
    // Draw tooltip pointer
    this.ctx.beginPath();
    this.ctx.moveTo(tooltip.x, tooltip.y);
    this.ctx.lineTo(tooltip.x - 6, tooltip.y - 6);
    this.ctx.lineTo(tooltip.x + 6, tooltip.y - 6);
    this.ctx.closePath();
    this.ctx.fill();
    
    // Draw tooltip text
    this.ctx.fillStyle = '#fff';
    this.ctx.textAlign = 'center';
    
    this.ctx.font = 'bold 10px Arial';
    this.ctx.fillText(tooltip.text, tooltip.x, tooltip.y - height + 12);
    
    this.ctx.font = '9px Arial';
    this.ctx.fillText(tooltip.subtext, tooltip.x, tooltip.y - height + 26);
  }
  
  // Draw legend
  drawLegend() {
    const { width, height, textColor, nodeColors } = this.options;
    
    // Get unique clusters/groups
    const clusters = new Set();
    this.nodes.forEach(node => {
      if (node.group !== undefined) {
        clusters.add(node.group);
      } else if (node.cluster !== undefined) {
        clusters.add(node.cluster);
      }
    });
    
    // Skip if no clusters or only one
    if (clusters.size <= 1) return;
    
    // Draw legend box
    const legendWidth = 120;
    const legendHeight = 15 + (clusters.size * 15);
    const padding = 8;
    
    this.ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    this.ctx.beginPath();
    this.ctx.roundRect(
      width - legendWidth - padding, 
      padding, 
      legendWidth, 
      legendHeight, 
      4
    );
    this.ctx.fill();
    
    this.ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)';
    this.ctx.lineWidth = 1;
    this.ctx.stroke();
    
    // Draw legend title
    this.ctx.fillStyle = textColor;
    this.ctx.font = 'bold 10px Arial';
    this.ctx.textAlign = 'left';
    this.ctx.fillText('Topic Clusters', width - legendWidth - padding + 10, padding + 12);
    
    // Draw legend items
    const sortedClusters = Array.from(clusters).sort((a, b) => a - b);
    
    sortedClusters.forEach((cluster, index) => {
      const x = width - legendWidth - padding + 10;
      const y = padding + 28 + (index * 15);
      const colorIndex = cluster % nodeColors.length;
      
      // Draw color circle
      this.ctx.fillStyle = nodeColors[colorIndex];
      this.ctx.beginPath();
      this.ctx.arc(x + 5, y - 3, 5, 0, Math.PI * 2);
      this.ctx.fill();
      
      // Draw label
      this.ctx.fillStyle = textColor;
      this.ctx.font = '9px Arial';
      this.ctx.fillText(`Cluster ${cluster}`, x + 15, y);
    });
  }
  
}

// Add to window object for use in popup.js
window.TopicClusterViz = TopicClusterViz;