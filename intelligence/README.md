# Intelligence System

The Intelligence system provides statistical analysis of global news sentiment patterns to identify meaningful anomalies, polarization events, and source behavior changes. It focuses on detecting statistically significant changes that are truly meaningful (p < 0.01, roughly once-per-year events) rather than day-to-day noise.

## Overview

This system analyzes sentiment patterns to identify:

- **Sentiment Anomalies**: Entities with statistically significant sentiment shifts
- **Source Divergence**: Sources that historically moved together but begin to diverge  
- **Polarization**: Entities becoming more divisive across news sources
- **Clustering Insights**: Changes in source clustering and narrative cohesion

## Architecture

### Core Components

1. **Statistical Database** (`statistical_database/`)
   - SQLite database for analysis state and findings
   - Isolated from main PostgreSQL database for reliability
   - Stores baseline statistics, findings, and cached analysis results

2. **Analysis Modules** (`intelligence/`)
   - `sentiment_anomaly_detector.py` - Detects unusual sentiment patterns
   - `source_divergence_detector.py` - Identifies diverging source pairs
   - `polarization_detector.py` - Measures increasing sentiment polarization
   - `clustering_insights_analyzer.py` - Processes clustering results

3. **Intelligence Manager** (`intelligence_manager.py`)
   - Coordinates all analysis modules
   - Manages the analysis pipeline
   - Provides unified API for intelligence functions

4. **API Endpoints** (`api_endpoints.py`)
   - FastAPI endpoints for dashboard integration
   - Provides findings, trends, and analysis results

### Database Schema

The statistical database contains several key tables:

- **`statistical_findings`** - Significant anomalies and patterns
- **`analysis_state`** - Latest computed state for each analysis type  
- **`baseline_statistics`** - Rolling statistics for anomaly detection
- **`source_divergence_tracking`** - Historical source correlations
- **`clustering_cache`** - Processed clustering results

## Key Principles

### Statistical Rigor
- Uses p-value < 0.01 for significance (roughly once-per-year events)
- Requires week-to-week changes (not day-to-day noise)
- Focuses on entities with substantial mention counts
- Uses sliding window analysis for trend detection

### Global Perspective
- Analyzes patterns across multiple countries and languages
- Detects cross-cultural sentiment divergence
- Identifies global vs. regional sentiment patterns

### Meaningful Insights
- Prioritizes findings that indicate real editorial shifts
- Focuses on sources that historically moved together
- Detects emerging narrative fragmentation or consensus

## Usage

### Running Weekly Analysis

```python
from intelligence.intelligence_manager import IntelligenceManager
from database.db import get_session

# Initialize intelligence manager
intelligence = IntelligenceManager()

# Run weekly analysis
with get_session() as session:
    results = intelligence.run_weekly_analysis(session)
    
print(f"Found {len(results['sentiment_anomalies'])} sentiment anomalies")
print(f"Found {len(results['source_divergences'])} source divergences")
```

### Getting Dashboard Findings

```python
# Get findings for dashboard display
findings = intelligence.get_dashboard_findings(
    category='anomaly',  # anomaly, divergence, polarization, trending
    limit=20
)

for finding in findings:
    print(f"{finding['title']}: {finding['description']}")
```

### API Integration

```python
# Add intelligence endpoints to main API
from intelligence.api_endpoints import router as intelligence_router

app.include_router(intelligence_router)
```

## API Endpoints

### Core Endpoints

- `GET /intelligence/findings` - Get statistical findings
- `GET /intelligence/status` - System health and status  
- `GET /intelligence/trends` - Global sentiment trends
- `POST /intelligence/analyze/run` - Trigger new analysis

### Detailed Analysis

- `GET /intelligence/entity/{id}/analysis` - Entity-focused analysis
- `GET /intelligence/source/{id}/analysis` - Source-focused analysis
- `GET /intelligence/divergences` - Source divergence events
- `GET /intelligence/polarization` - Polarization events

### Reports

- `GET /intelligence/report/weekly` - Comprehensive weekly report
- `GET /intelligence/clustering/insights` - Clustering behavior patterns

## Analysis Types

### 1. Sentiment Anomaly Detection

**Purpose**: Identify entities with unusual sentiment shifts

**Method**: 
- Uses 12-week rolling baseline
- Calculates z-scores for sentiment changes
- Requires consecutive anomalous days to reduce false positives

**Significance**: Indicates major news events or editorial shifts

### 2. Source Divergence Detection

**Purpose**: Find sources that historically agreed but now diverge

**Method**:
- Calculates pairwise correlation on entity sentiment
- Compares recent vs. historical correlation
- Uses Fisher's z-transformation for significance testing

**Significance**: Indicates emerging polarization or editorial repositioning

### 3. Polarization Detection  

**Purpose**: Identify entities becoming more divisive

**Method**:
- Measures sentiment variance across sources
- Detects bimodal distributions (true polarization)
- Uses Levene's test for variance significance

**Significance**: Shows topics becoming more politically charged

### 4. Clustering Insights

**Purpose**: Analyze source behavior and narrative cohesion

**Method**:
- Processes clustering results from main database
- Tracks cluster stability and membership changes
- Identifies emerging/dissolving narrative clusters

**Significance**: Reveals media ecosystem structure changes

## Configuration

### Analysis Parameters

```python
# Sentiment anomaly detection
BASELINE_WEEKS = 12           # Historical baseline period
SIGNIFICANCE_THRESHOLD = 0.01 # p-value threshold
MIN_MENTIONS_PER_WEEK = 10    # Minimum mentions for analysis

# Source divergence detection  
HISTORICAL_WEEKS = 24         # Historical correlation period
RECENT_WEEKS = 4              # Recent comparison period
MIN_HISTORICAL_CORRELATION = 0.7  # Minimum historical correlation

# Polarization detection
MIN_SOURCES_PER_ENTITY = 8    # Minimum source coverage
POLARIZATION_THRESHOLD = 1.5  # Variance increase threshold
```

### Database Configuration

```python
# Statistical database path
STATISTICAL_DB_PATH = "statistical_database/intelligence_analysis.db"

# Cleanup settings
FINDINGS_RETENTION_DAYS = 90  # How long to keep findings
```

## Implementation Status

### ✅ Completed

- Database schema design
- Core data structures  
- API endpoint definitions
- Analysis module frameworks
- Intelligence manager coordination

### 🚧 TODO Implementation

Each analysis module contains detailed TODO comments for implementation:

1. **Database Integration**
   - Connect to main PostgreSQL database
   - Implement entity and source queries
   - Add database session management

2. **Statistical Calculations**
   - Implement baseline statistics computation
   - Add proper statistical significance testing
   - Implement correlation and variance analysis

3. **Analysis Logic**
   - Implement anomaly detection algorithms
   - Add divergence detection logic
   - Implement polarization measurement
   - Add clustering analysis processing

4. **Dashboard Integration**
   - Complete API endpoint implementations
   - Add proper error handling
   - Implement authentication/authorization

## Monitoring and Maintenance

### Health Checks

The system provides health monitoring through:
- `GET /intelligence/status` - Overall system status
- Database connectivity checks
- Analysis module status
- Recent error counts

### Automated Cleanup

- Old findings are automatically cleaned up (90-day retention)
- Analysis state is maintained for trend analysis
- Database is periodically optimized

### Performance Considerations

- Analysis runs are computationally intensive
- Should be scheduled during low-usage periods
- Consider implementing analysis queuing for large datasets
- Cache results for dashboard performance

## Dashboard Integration

The intelligence system is designed to showcase insights to potential customers by highlighting:

1. **Real-time Anomalies** - What's happening right now that's unusual
2. **Source Behavior** - How different news sources are positioning themselves  
3. **Global Patterns** - Cross-cultural and international sentiment trends
4. **Historical Context** - How current events compare to baseline patterns

This provides a compelling demonstration of the system's ability to detect meaningful patterns in the global news landscape.