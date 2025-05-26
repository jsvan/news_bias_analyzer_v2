/**
 * Source similarity functionality for the extension
 * Uses the new clustering API endpoints
 */

// Get source similarity data
async function loadSourceSimilarityData(sourceId) {
  try {
    // Get API_ENDPOINT from window or use default
    const apiEndpoint = window.API_ENDPOINT || 'http://localhost:8080/api';
    const response = await fetch(`${apiEndpoint}/similarity/sources/${sourceId}/similar?limit=20`);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error loading source similarity:', error);
    throw error;
  }
}

// Get volatile entities
async function loadVolatileEntities(limit = 20) {
  try {
    const apiEndpoint = window.API_ENDPOINT || 'http://localhost:8080/api';
    const response = await fetch(`${apiEndpoint}/similarity/entities/volatile?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error loading volatile entities:', error);
    throw error;
  }
}

// Get source drift data
async function loadSourceDrift(sourceId, weeks = 4) {
  try {
    const apiEndpoint = window.API_ENDPOINT || 'http://localhost:8080/api';
    const response = await fetch(`${apiEndpoint}/similarity/sources/${sourceId}/drift?weeks=${weeks}`);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error loading source drift:', error);
    throw error;
  }
}

// Get source clusters visualization
async function loadSourceClusters(country = null) {
  try {
    const apiEndpoint = window.API_ENDPOINT || 'http://localhost:8080/api';
    let url = `${apiEndpoint}/similarity/sources/clusters`;
    if (country) {
      url += `?country=${encodeURIComponent(country)}`;
    }
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error loading source clusters:', error);
    throw error;
  }
}

// Get source comparison for current article
async function loadArticleSourceComparison(articleId) {
  try {
    const apiEndpoint = window.API_ENDPOINT || 'http://localhost:8080/api';
    const response = await fetch(`${apiEndpoint}/similarity/articles/${articleId}/source-comparison`);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error loading source comparison:', error);
    throw error;
  }
}

// Get source info by name
async function getSourceByName(sourceName) {
  try {
    const apiEndpoint = window.API_ENDPOINT || 'http://localhost:8080/api';
    const response = await fetch(`${apiEndpoint}/similarity/sources/by-name/${encodeURIComponent(sourceName)}`);
    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error(`API request failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error getting source by name:', error);
    throw error;
  }
}

// Format similarity score for display
function formatSimilarityScore(score) {
  return `${Math.round(score * 100)}%`;
}

// Create HTML for similar sources list
function createSimilarSourcesHTML(similarSources, currentSourceName) {
  if (!similarSources || similarSources.length === 0) {
    return `
      <div class="no-data-message">
        <p>No similarity data available yet. Weekly similarity computation runs on Sundays.</p>
      </div>
    `;
  }

  const html = `
    <div class="similar-sources-container">
      <h4>Sources Similar to ${currentSourceName}</h4>
      <div class="similar-sources-list">
        ${similarSources.map(source => `
          <div class="similar-source-item">
            <div class="source-info">
              <span class="source-name">${source.source_name}</span>
              <span class="source-country">${source.country || 'Unknown'}</span>
            </div>
            <div class="similarity-info">
              <span class="similarity-score">${formatSimilarityScore(source.similarity_score)}</span>
              <span class="common-entities">${source.common_entities} common entities</span>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
  
  return html;
}

// Create HTML for volatile entities
function createVolatileEntitiesHTML(volatileEntities) {
  if (!volatileEntities || volatileEntities.length === 0) {
    return `
      <div class="no-data-message">
        <p>No volatile entities detected this week.</p>
      </div>
    `;
  }

  const html = `
    <div class="volatile-entities-container">
      <h4>Current Hot Topics (High Disagreement)</h4>
      <div class="volatile-entities-list">
        ${volatileEntities.slice(0, 10).map(entity => `
          <div class="volatile-entity-item">
            <div class="entity-info">
              <span class="entity-name">${entity.entity_name}</span>
              <span class="entity-type">${entity.entity_type}</span>
            </div>
            <div class="volatility-info">
              <span class="volatility-score">Volatility: ${entity.volatility_score.toFixed(2)}</span>
              <span class="mention-count">${entity.mention_count} mentions</span>
            </div>
            ${entity.divergent_sources && entity.divergent_sources.length > 0 ? `
              <div class="divergent-sources">
                <small>Top divergent sources:</small>
                ${entity.divergent_sources.slice(0, 3).map(s => 
                  `<span class="divergent-source">${s.source_name}: ${s.sentiment.toFixed(1)}</span>`
                ).join(', ')}
              </div>
            ` : ''}
          </div>
        `).join('')}
      </div>
    </div>
  `;
  
  return html;
}

// Create visualization for source clusters
function visualizeSourceClusters(clusterData, canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  
  // Clear canvas
  ctx.clearRect(0, 0, width, height);
  
  if (!clusterData || !clusterData.clusters || clusterData.clusters.length === 0) {
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.font = '14px Arial';
    ctx.fillText('No cluster data available', width/2, height/2);
    return;
  }
  
  // Simple visualization - position clusters in a grid
  const clusters = clusterData.clusters;
  const cols = Math.ceil(Math.sqrt(clusters.length));
  const rows = Math.ceil(clusters.length / cols);
  const cellWidth = width / cols;
  const cellHeight = height / rows;
  
  clusters.forEach((cluster, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const x = col * cellWidth + cellWidth / 2;
    const y = row * cellHeight + cellHeight / 2;
    
    // Draw cluster
    const radius = Math.min(cellWidth, cellHeight) / 3;
    const nodeRadius = Math.sqrt(cluster.size) * 2;
    
    // Cluster circle
    ctx.fillStyle = cluster.level === 1 ? '#e74c3c' : '#3498db';
    ctx.globalAlpha = 0.6;
    ctx.beginPath();
    ctx.arc(x, y, nodeRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
    
    // Cluster label
    ctx.fillStyle = '#333';
    ctx.textAlign = 'center';
    ctx.font = '10px Arial';
    const label = cluster.cluster_id.split('_').slice(-1)[0];
    ctx.fillText(label, x, y + nodeRadius + 15);
    
    // Member count
    ctx.font = '8px Arial';
    ctx.fillText(`${cluster.size} sources`, x, y + nodeRadius + 25);
  });
  
  // Legend
  ctx.fillStyle = '#e74c3c';
  ctx.fillRect(10, height - 25, 10, 10);
  ctx.fillStyle = '#333';
  ctx.font = '10px Arial';
  ctx.textAlign = 'left';
  ctx.fillText('Tier 1 (Major)', 25, height - 17);
  
  ctx.fillStyle = '#3498db';
  ctx.fillRect(100, height - 25, 10, 10);
  ctx.fillText('Tier 2 (Clustered)', 115, height - 17);
}

// Export functions for use in popup.js
window.sourceSimilarity = {
  loadSourceSimilarityData,
  loadVolatileEntities,
  loadSourceDrift,
  loadSourceClusters,
  loadArticleSourceComparison,
  getSourceByName,
  createSimilarSourcesHTML,
  createVolatileEntitiesHTML,
  visualizeSourceClusters
};