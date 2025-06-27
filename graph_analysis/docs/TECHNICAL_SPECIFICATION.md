# Entity Correlation Graph Analysis: Technical Specification

## Executive Summary

This document outlines a comprehensive graph analysis system for understanding news bias through entity co-occurrence and sentiment correlation patterns. Unlike traditional word-level analysis, this approach maps the relational structure of how news sources position entities relative to each other, revealing the hidden geometry of ideological space.

## Core Research Questions

### What Will We Actually Discover?

1. **The Hidden Architecture of Ideological Space**
   - **Question**: Do news sources have consistent, mathematically describable patterns in how they correlate entities?
   - **Expected Finding**: Each source has a unique "correlation signature" that places entities in predictable relationships
   - **Real Understanding**: We'll map the actual geometric structure of different worldviews, not just left/right but multi-dimensional ideological spaces
   - **Example**: Conservative sources might consistently correlate (Military + Economy + Tradition), while progressive sources correlate (Environment + Social Justice + International Cooperation)

2. **Narrative Contagion Mechanisms**
   - **Question**: How does sentiment spread through entity networks within and across sources?
   - **Expected Finding**: Sentiment follows mathematical laws of propagation through entity networks
   - **Real Understanding**: The physics of how political emotions spread through information ecosystems
   - **Example**: Track how Russia-Ukraine sentiment affects NATO sentiment, EU sentiment, energy policy sentiment in different sources

3. **Editorial Shift Prediction**
   - **Question**: Do entity relationship patterns change before explicit editorial positions change?
   - **Expected Finding**: Sources change their entity correlation patterns months before explicit editorial shifts
   - **Real Understanding**: Early warning system for major media narrative shifts
   - **Example**: Detect when Fox News starts decorrelating Trump from Republican Party before explicit criticism appears

4. **Polarization Physics**
   - **Question**: Which entities act as "polarization amplifiers" vs "consensus builders"?
   - **Expected Finding**: Entities have mathematical signatures that predict their divisive/unifying effects
   - **Real Understanding**: Quantitative laws governing political polarization
   - **Example**: Some politicians increase correlation variance across sources (polarizers), others decrease it (unifiers)

## Technical Architecture

### Phase 1: Data Infrastructure

#### 1.1 Database Schema Extensions

```sql
-- Entity co-occurrence tracking
CREATE TABLE entity_co_occurrences (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES news_sources(id),
    article_id INTEGER REFERENCES news_articles(id),
    entity1_id INTEGER REFERENCES entities(id),
    entity2_id INTEGER REFERENCES entities(id),
    entity1_sentiment FLOAT,
    entity2_sentiment FLOAT,
    distance_between INTEGER, -- words between entities
    article_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sentiment correlation matrices per source/time
CREATE TABLE entity_sentiment_correlations (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES news_sources(id),
    entity1_id INTEGER REFERENCES entities(id),
    entity2_id INTEGER REFERENCES entities(id),
    correlation_coefficient FLOAT,
    p_value FLOAT,
    sample_size INTEGER,
    time_window_start DATE,
    time_window_end DATE,
    significance_level VARCHAR(20), -- 'significant', 'not_significant'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_id, entity1_id, entity2_id, time_window_start)
);

-- Temporal changes in correlations
CREATE TABLE correlation_changes (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES news_sources(id),
    entity1_id INTEGER REFERENCES entities(id),
    entity2_id INTEGER REFERENCES entities(id),
    old_correlation FLOAT,
    new_correlation FLOAT,
    change_magnitude FLOAT,
    change_direction VARCHAR(20), -- 'increase', 'decrease', 'reversal'
    change_date DATE,
    statistical_significance FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Source ideological positioning
CREATE TABLE source_ideological_positions (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES news_sources(id),
    time_window_start DATE,
    time_window_end DATE,
    ideological_vector JSONB, -- PCA/t-SNE coordinates
    cluster_id INTEGER,
    distance_to_centroid FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Entity polarization scores
CREATE TABLE entity_polarization_scores (
    id SERIAL PRIMARY KEY,
    entity_id INTEGER REFERENCES entities(id),
    time_window_start DATE,
    time_window_end DATE,
    polarization_index FLOAT, -- variance of correlations across sources
    consensus_score FLOAT, -- agreement across sources
    influence_centrality FLOAT, -- network centrality measure
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 1.2 Data Collection Pipeline

**Article Processing Enhancement:**
```python
def extract_entity_co_occurrences(article_text, entities_found):
    """
    Extract all entity pairs that appear within N words of each other
    along with their sentiment scores and relative positions.
    """
    co_occurrences = []
    for i, entity1 in enumerate(entities_found):
        for entity2 in entities_found[i+1:]:
            distance = calculate_word_distance(entity1, entity2, article_text)
            if distance <= MAX_DISTANCE:  # e.g., 50 words
                co_occurrences.append({
                    'entity1_id': entity1.id,
                    'entity2_id': entity2.id,
                    'entity1_sentiment': entity1.sentiment,
                    'entity2_sentiment': entity2.sentiment,
                    'distance': distance
                })
    return co_occurrences
```

### Phase 2: Correlation Analysis Engine

#### 2.1 Weekly Correlation Computation

```python
class EntityCorrelationAnalyzer:
    def compute_weekly_correlations(self, source_id, week_start, week_end):
        """
        For each source, compute pairwise entity sentiment correlations
        for all entity pairs that co-occurred during the time window.
        """
        # Get all co-occurrences for this source/timeframe
        co_occurrences = self.get_co_occurrences(source_id, week_start, week_end)
        
        # Group by entity pairs
        entity_pairs = self.group_by_entity_pair(co_occurrences)
        
        correlations = []
        for (entity1_id, entity2_id), occurrences in entity_pairs.items():
            if len(occurrences) >= MIN_SAMPLE_SIZE:  # e.g., 10 co-occurrences
                sentiments1 = [occ.entity1_sentiment for occ in occurrences]
                sentiments2 = [occ.entity2_sentiment for occ in occurrences]
                
                correlation, p_value = pearsonr(sentiments1, sentiments2)
                
                correlations.append({
                    'source_id': source_id,
                    'entity1_id': entity1_id,
                    'entity2_id': entity2_id,
                    'correlation': correlation,
                    'p_value': p_value,
                    'sample_size': len(occurrences)
                })
        
        return correlations
```

#### 2.2 Cross-Source Comparison

```python
class IdeologicalSpaceMapper:
    def map_source_positions(self, time_window):
        """
        Use PCA/t-SNE to map sources in ideological space based on
        their entity correlation patterns.
        """
        # Build correlation matrix for each source
        source_correlation_matrices = {}
        for source in self.active_sources:
            correlations = self.get_correlations(source.id, time_window)
            source_correlation_matrices[source.id] = self.build_matrix(correlations)
        
        # Flatten matrices into feature vectors
        feature_vectors = []
        source_ids = []
        for source_id, matrix in source_correlation_matrices.items():
            # Use upper triangle of correlation matrix as features
            features = matrix[np.triu_indices(matrix.shape[0], k=1)]
            feature_vectors.append(features)
            source_ids.append(source_id)
        
        # Apply dimensionality reduction
        from sklearn.decomposition import PCA
        from sklearn.manifold import TSNE
        
        pca = PCA(n_components=10)
        pca_features = pca.fit_transform(feature_vectors)
        
        tsne = TSNE(n_components=2, random_state=42)
        tsne_coords = tsne.fit_transform(pca_features)
        
        # Store ideological positions
        for i, source_id in enumerate(source_ids):
            self.store_ideological_position(
                source_id=source_id,
                pca_coords=pca_features[i],
                tsne_coords=tsne_coords[i],
                time_window=time_window
            )
```

### Phase 3: Temporal Analysis

#### 3.1 Change Point Detection

```python
class NarrativeShiftDetector:
    def detect_correlation_changes(self, entity1_id, entity2_id, lookback_weeks=12):
        """
        Use change-point detection to identify when entity relationships
        shift significantly across sources.
        """
        from scipy import stats
        import ruptures as rpt  # change point detection library
        
        # Get historical correlations for this entity pair across all sources
        correlations = self.get_historical_correlations(
            entity1_id, entity2_id, lookback_weeks
        )
        
        changes = []
        for source_id, source_correlations in correlations.items():
            # Apply change point detection
            model = rpt.Pelt(model="rbf").fit(source_correlations)
            change_points = model.predict(pen=10)
            
            if len(change_points) > 1:  # Found significant changes
                for i, cp in enumerate(change_points[:-1]):
                    pre_period = source_correlations[:cp]
                    post_period = source_correlations[cp:change_points[i+1]]
                    
                    # Test significance of change
                    t_stat, p_value = stats.ttest_ind(pre_period, post_period)
                    
                    if p_value < 0.01:  # Significant change
                        changes.append({
                            'source_id': source_id,
                            'entity1_id': entity1_id,
                            'entity2_id': entity2_id,
                            'change_date': self.index_to_date(cp),
                            'old_correlation': np.mean(pre_period),
                            'new_correlation': np.mean(post_period),
                            'change_magnitude': abs(np.mean(post_period) - np.mean(pre_period)),
                            'p_value': p_value
                        })
        
        return changes
```

#### 3.2 Influence Network Analysis

```python
class SentimentCausalityAnalyzer:
    def analyze_sentiment_causality(self, time_window):
        """
        Use Granger causality to determine which entities influence
        sentiment changes in other entities.
        """
        from statsmodels.tsa.stattools import grangercausalitytests
        
        # Get time series of sentiment for all entities
        entity_sentiment_series = self.get_entity_sentiment_timeseries(time_window)
        
        causality_network = {}
        for entity1_id, series1 in entity_sentiment_series.items():
            causality_network[entity1_id] = {}
            for entity2_id, series2 in entity_sentiment_series.items():
                if entity1_id != entity2_id:
                    # Test if entity1 sentiment predicts entity2 sentiment
                    try:
                        result = grangercausalitytests(
                            np.column_stack([series2, series1]), 
                            maxlag=7,  # 7 days lookback
                            verbose=False
                        )
                        
                        # Extract p-value for 1-day lag
                        p_value = result[1][0]['ssr_ftest'][1]
                        causality_network[entity1_id][entity2_id] = {
                            'granger_p_value': p_value,
                            'is_causal': p_value < 0.05
                        }
                    except:
                        causality_network[entity1_id][entity2_id] = {
                            'granger_p_value': 1.0,
                            'is_causal': False
                        }
        
        return causality_network
```

### Phase 4: Experimental Framework

#### 4.1 Experiment 1: Ideological Distance Metrics

**Hypothesis**: News sources can be positioned in a low-dimensional ideological space based on their entity correlation patterns.

**Method**:
1. Compute correlation matrices for each source
2. Use matrix distance metrics (Frobenius norm, correlation distance)
3. Apply clustering and dimensionality reduction
4. Validate against known political alignments

**Expected Outcome**: Sources cluster into ideologically coherent groups with measurable distances.

**Success Metrics**:
- Clustering purity > 0.8 when compared to known political alignments
- Stable positioning over time for individual sources
- Meaningful interpretation of principal components

#### 4.2 Experiment 2: Polarization Index Development

**Hypothesis**: Entities have characteristic "polarization signatures" that predict their divisive effects.

**Method**:
1. Calculate variance of entity correlations across sources
2. Build entity polarization index: `PI = var(correlations) / mean(abs(correlations))`
3. Track polarization changes over time
4. Validate against historical polarizing events

**Expected Outcome**: Clear identification of most polarizing entities with predictive power.

**Success Metrics**:
- Polarization index correlates with known divisive figures/topics
- Temporal spikes align with major political events
- Cross-validation accuracy > 0.75 for predicting polarizing coverage

#### 4.3 Experiment 3: Narrative Shift Prediction

**Hypothesis**: Changes in entity correlation patterns precede explicit editorial position changes.

**Method**:
1. Identify historical editorial shifts (endorsement changes, position reversals)
2. Analyze correlation pattern changes in months preceding shifts
3. Build predictive model for editorial changes
4. Test on holdout period

**Expected Outcome**: 2-4 week early warning for major editorial shifts.

**Success Metrics**:
- Precision > 0.6 for predicting editorial shifts
- Recall > 0.4 for capturing actual shifts
- Lead time of 2+ weeks for predictions

#### 4.4 Experiment 4: Sentiment Contagion Mapping

**Hypothesis**: Sentiment spreads through entity networks following network topology.

**Method**:
1. Build entity influence networks using Granger causality
2. Model sentiment spread using network diffusion models
3. Predict sentiment changes based on network position
4. Validate against observed sentiment cascades

**Expected Outcome**: Mathematical model of sentiment propagation through political networks.

**Success Metrics**:
- R² > 0.5 for predicting sentiment changes from network position
- Successful prediction of sentiment cascades during major events
- Identification of key "super-spreader" entities

### Phase 5: Practical Applications

#### 5.1 Real-time Analysis Dashboard

**Entity Relationship Networks**:
- Interactive graph visualization of entity correlations per source
- Time-slider to show network evolution
- Highlighting of entities with recent correlation changes

**Source Positioning Map**:
- 2D scatter plot showing sources in ideological space
- Movement trails showing editorial drift over time
- Clustering visualization with confidence ellipses

**Polarization Monitor**:
- Real-time tracking of entity polarization indices
- Alerts for entities becoming unusually divisive
- Historical trend analysis for polarization patterns

#### 5.2 Intelligence System Integration

**Correlation Change Alerts**:
- Detect when entity relationships shift significantly
- Flag sources showing unusual correlation patterns
- Predict potential editorial position changes

**Polarization Warnings**:
- Identify entities becoming polarization amplifiers
- Track overall polarization trend across ecosystem
- Alert on rapid polarization increases

**Influence Network Updates**:
- Monitor changes in entity influence rankings
- Detect new influence pathways emerging
- Track sentiment leadership changes

### Phase 6: Validation Framework

#### 6.1 Ground Truth Validation

**Historical Event Analysis**:
- Test system predictions against known historical shifts
- Validate polarization scores against documented controversial periods
- Check source clustering against known political alignments

**Expert Judgment Comparison**:
- Compare entity relationship maps to political science literature
- Validate influence networks against known political influence patterns
- Cross-check polarization rankings with expert assessments

#### 6.2 Predictive Validation

**Out-of-sample Testing**:
- Hold out recent months for testing predictions
- Measure accuracy of editorial shift predictions
- Evaluate sentiment cascade prediction performance

**Cross-validation**:
- Split data by time periods and sources
- Test model generalization across different news cycles
- Validate stability of entity positioning over time

## Expected Research Outcomes

### 1. Mathematical Laws of Media Bias

**Discovery**: News bias follows quantifiable patterns describable by mathematical models.

**Impact**: Transform media analysis from subjective interpretation to objective measurement.

**Applications**: 
- Automated bias detection systems
- Media literacy education tools
- Regulatory compliance monitoring

### 2. Predictive Models for Information Warfare

**Discovery**: Narrative manipulation follows predictable network propagation patterns.

**Impact**: Early warning systems for coordinated disinformation campaigns.

**Applications**:
- National security monitoring
- Social media platform defense
- Democratic institution protection

### 3. Quantified Polarization Dynamics

**Discovery**: Political polarization has measurable mathematical signatures and predictable evolution patterns.

**Impact**: Scientific understanding of democratic stability threats.

**Applications**:
- Policy intervention timing
- Political reconciliation strategies
- Democratic health monitoring

### 4. Ideological Space Mapping

**Discovery**: Complete mathematical description of ideological space geometry.

**Impact**: Objective measurement of political positioning without left/right simplification.

**Applications**:
- International political analysis
- Cross-cultural political comparison
- Political movement prediction

## Implementation Timeline

### Month 1-2: Infrastructure
- Database schema implementation
- Data collection pipeline enhancement
- Basic correlation computation engine

### Month 3-4: Core Analysis
- Cross-source comparison algorithms
- Temporal change detection systems
- Polarization index development

### Month 5-6: Advanced Analytics
- Influence network analysis
- Predictive model development
- Validation framework implementation

### Month 7-8: Applications
- Dashboard development
- Intelligence system integration
- Real-time monitoring capabilities

### Month 9-12: Research & Validation
- Comprehensive historical validation
- Academic paper preparation
- System optimization and scaling

## Success Criteria

1. **Technical Success**: All experiments achieve stated success metrics
2. **Scientific Success**: Discoveries lead to published research advancing political science
3. **Practical Success**: System provides actionable intelligence for users
4. **Predictive Success**: Models successfully predict future events during validation period

This comprehensive analysis framework will transform our understanding of news bias from subjective interpretation to objective, mathematical science, providing unprecedented insight into the hidden forces shaping public discourse.