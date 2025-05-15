# News Comparison and Bias Visualization

This module allows you to visualize and compare how different news sources cover the same entities and topics over time, providing insights into media bias patterns and political alignments.

## Key Features

### Source Similarity Analysis
- **Clustering Visualization**: See how news sources cluster based on their sentiment patterns
- **2D Projection Map**: Interactive visualization of source relationships
- **Political Leaning Indicators**: Color-coded by political orientation for easy pattern identification
- **Similarity Matrix**: Quantitative measure of how closely sources align in their coverage

### Entity Sentiment Trends
- **Temporal Sentiment Analysis**: Track how sentiment for specific entities evolves over time
- **Multi-source Comparison**: Compare how different outlets portray the same entity
- **Power and Moral Dimension Analysis**: View both power/agency and moral/ethical sentiment dimensions
- **Coverage Volume Tracking**: See which sources mention an entity more frequently

### Topic Coverage Comparison
- **Topic Persistence Analysis**: Identify when sources amplify or abandon specific topics
- **Coverage Volume Heat Map**: Visualize relative focus on different topics
- **Temporal Coverage Patterns**: Track shifting priorities in news coverage
- **Political Bias Detection**: Identify patterns in topic selection that indicate bias

## Technical Implementation

### Data Science Techniques

The system uses several sophisticated techniques to analyze media bias:

1. **Cosine Similarity Matrix**: To measure how similarly news sources portray the same entities
   ```python
   # Distance calculation using cosine similarity
   distance_matrix = squareform(pdist(feature_matrix, metric='cosine'))
   # Convert to similarity (higher value = more similar)
   similarity_matrix = 1 - distance_matrix
   ```

2. **Dimensionality Reduction with t-SNE**: For visualizing high-dimensional sentiment patterns in 2D
   ```python
   # Convert complex sentiment patterns to 2D visualization
   tsne = TSNE(n_components=2, perplexity=30, random_state=42, metric='precomputed')
   coordinates = tsne.fit_transform(distance_matrix)
   ```

3. **Hierarchical Agglomerative Clustering**: To identify groups of news sources with similar bias patterns
   ```python
   # Group sources into clusters based on similarity
   clustering = AgglomerativeClustering(
       n_clusters=None,
       distance_threshold=0.5,
       affinity='precomputed',
       linkage='average'
   )
   clusters = clustering.fit_predict(distance_matrix)
   ```

4. **Statistical Analysis of Sentiment Patterns**: To identify unusual or statistically significant differences in coverage
   ```python
   # Calculate significance of sentiment differences
   p_value = 2 * min(
       sentiment_distribution.cdf(observed_score),
       1 - sentiment_distribution.cdf(observed_score)
   )
   ```

### API Endpoints

The module exposes the following API endpoints:

- `GET /similarity/source_similarity` - Get similarity data between news sources
- `GET /similarity/entity_trends` - Get sentiment trends for a specific entity
- `GET /similarity/topic_coverage` - Get topic coverage comparison across sources
- `GET /similarity/source_list` - Get list of available news sources
- `GET /similarity/topic_list` - Get list of available topics
- `GET /similarity/entity_list` - Get list of available entities

See the API reference documentation for detailed parameters and response formats.

## Getting Started

### Running the Application

1. Start the API server:
   ```bash
   ./run_news_comparison_api.sh
   ```

2. Access the dashboard at:
   ```
   http://localhost:3000/news-comparison
   ```

### Example Usage

**Finding Political Clusters:**
1. Navigate to the Source Similarity Map tab
2. Look for clusters of news sources with similar colors
3. Examine which sources are consistently grouped together

**Detecting Topic Bias:**
1. Navigate to the Topic Coverage Comparison tab
2. Select a politically charged topic (e.g., "Climate Change")
3. Look for significant disparities in coverage volume between sources
4. Note when some sources abandon coverage while others persist

**Tracking Entity Sentiment Shifts:**
1. Navigate to the Entity Sentiment Trends tab
2. Select a prominent political figure
3. Observe divergence points where sources shift sentiment differently
4. Note correlations between sentiment shifts and major events

## Understanding the Visualizations

### Source Similarity Network
- **Nodes**: Individual news sources
- **Edges**: Similarity connections (thicker = more similar)
- **Color**: Automatically assigned cluster
- **Size**: Volume of entity mentions

### Entity Trend Charts
- **X-Axis**: Time periods
- **Y-Axis**: Sentiment score (-2 to +2)
- **Lines**: Sentiment trajectory
- **Bar Chart**: Mention frequency

### Topic Heat Map
- **Rows**: News sources
- **Columns**: Topics
- **Color Intensity**: Coverage volume
- **Time Series**: Shows evolution of coverage over time

## Interpreting Results

When analyzing the visualizations, look for:

1. **Persistent Clusters**: Sources that consistently appear together across different entities/topics
2. **Coverage Drop-offs**: Sudden decreases in topic coverage that may indicate editorial decisions
3. **Sentiment Reversals**: Sharp changes in sentiment after specific events
4. **Statistical Outliers**: Coverage patterns that differ significantly from the norm

These patterns can help identify both subtle and obvious bias patterns in news media coverage.