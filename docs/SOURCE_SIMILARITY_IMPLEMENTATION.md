# Source Similarity Implementation Plan

## Overview
Implement two complementary similarity metrics for news sources:
1. **Static Similarity**: How similarly sources cover entities (Pearson correlation)
2. **Temporal Similarity**: How similarly sources react to events over time

## Detailed Implementation Tasks

### 1. Pearson Correlation Similarity Module

**Location**: `/analyzer/source_similarity.py`

```python
def pearson_similarity_on_common_entities(source1_id, source2_id, start_date, end_date):
    """
    Algorithm:
    1. Query entity mentions for both sources in time window
    2. Find intersection of entities (only those covered by BOTH)
    3. Calculate average sentiment per entity per source
    4. Create aligned vectors for common entities
    5. Compute Pearson correlation using scipy.stats.pearsonr
    
    Returns:
    {
        'score': float,          # Correlation coefficient [-1, 1]
        'p_value': float,        # Statistical significance
        'common_entities': int,   # Number of shared entities
        'entity_list': [...]     # List of common entities
    }
    """
```

**Edge Cases**:
- Less than 5 common entities → return None
- One source has zero variance → return 0
- Handle missing data with pairwise deletion

### 2. Temporal Correlation Function

```python
def temporal_correlation(source1_id, source2_id, entity_id, granularity='daily'):
    """
    Algorithm:
    1. Get daily sentiment averages for specific entity from both sources
    2. Calculate daily changes: sentiment[t] - sentiment[t-1]
    3. Align time series (forward-fill missing days)
    4. Compute correlation of changes (not absolute values)
    5. Also compute Dynamic Time Warping for async reactions
    
    Returns:
    {
        'correlation': float,     # How similarly they react
        'optimal_lag': int,       # Days source2 lags source1
        'dtw_distance': float,    # Dissimilarity allowing time shifts
    }
    """
```

### 3. Weekly Computation Pipeline

**Script**: `/analyzer/compute_weekly_similarities.py`

```python
class WeeklySimilarityComputer:
    def run_weekly_computation(self):
        """
        Pipeline (runs every Sunday 2 AM UTC):
        1. Get ISO week boundaries (previous Sunday-Saturday)
        2. For all source pairs:
           - Compute Pearson similarity
           - Store in source_similarity_matrix
        3. For each source-entity pair:
           - Calculate weekly average sentiment
           - Compare to previous week
           - Store in source_temporal_drift
        4. Identify high-volatility entities:
           - Cross-source variance > threshold
           - Temporal variance > threshold
           - Store in entity_volatility
        5. Warm cache for top sources
        """
```

**Optimization**:
- Use multiprocessing.Pool for parallel computation
- Process in batches of 100 source pairs
- Memory limit: 4GB (chunk if >1000 sources)

### 4. Volatility Detection Algorithm

```python
def compute_entity_volatility(entity_id, time_window):
    """
    Volatility Components:
    1. Cross-source variance: How much sources disagree
       - σ²(sentiments across sources on same day)
    2. Temporal variance: How much sentiment changes
       - σ²(daily sentiment changes)
    3. Volume variance: How mention frequency varies
       - σ²(daily mention counts)
    
    Final Score = 0.5 * cross_source + 0.3 * temporal + 0.2 * volume
    
    Flag as "hot" if score > mean + 2*stddev
    """
```

### 5. API Endpoints

**File**: `/extension/api/similarity_endpoints.py`

```python
@app.get("/api/source/{source_id}/similarity")
async def get_source_similarities(source_id: int, limit: int = 20):
    """
    Returns most similar sources based on latest week's data.
    Query optimized with indexes on source_similarity_matrix.
    """

@app.get("/api/source/{source_id}/drift")
async def get_source_drift(source_id: int, weeks: int = 4):
    """
    Returns sentiment trends for top entities over time.
    Shows how source's coverage is evolving.
    """

@app.get("/api/entities/volatile")
async def get_volatile_entities(limit: int = 50):
    """
    Returns entities with highest volatility scores.
    These are the current "battleground" topics.
    """
```

### 6. Caching Strategy

**Technology**: Redis (or in-memory if not available)

**Cache Keys**:
- `similarity:{source1}:{source2}:{week}` → similarity score
- `drift:{source}:{entity}:{week}` → sentiment average
- `volatile:{week}` → list of volatile entities

**TTL**:
- Current week: 1 hour
- Past weeks: 7 days
- Volatile entities: 6 hours

### 7. Database Migration

Run: `./run.sh sql 'alembic upgrade head'`

Creates tables:
- `source_similarity_matrix`: Pairwise similarities
- `source_temporal_drift`: Weekly sentiment snapshots
- `entity_volatility`: Hot topic detection

### 8. Performance Targets

- Full weekly computation: <5 minutes for 1000 sources
- API response time: <100ms (from cache)
- Cache miss penalty: <500ms
- Memory usage: <4GB during computation

### 9. Monitoring & Alerts

Log metrics:
- Computation time per phase
- Number of source pairs processed
- Cache hit rates
- Detected editorial shifts
- Error rates and retries

Alert conditions:
- Computation fails or exceeds 30 minutes
- Cache hit rate drops below 80%
- Major editorial shift detected (>3σ change)

### 10. Future Enhancements

- **Source Clustering**: Hierarchical clustering visualization
- **Narrative Detection**: Identify coordinated messaging
- **Predictive Modeling**: Forecast sentiment trends
- **Real-time Updates**: Incremental similarity updates
- **Geographic Analysis**: Regional similarity patterns













