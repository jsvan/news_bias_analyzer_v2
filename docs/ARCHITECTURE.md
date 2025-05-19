# News Bias Analyzer - System Architecture

This document describes the architecture of the News Bias Analyzer system, including component responsibilities, data flow, and design principles.

## System Overview

The News Bias Analyzer is a distributed system with the following high-level components:

1. **Scraper Service**: Collects articles from news sources
2. **Processing Pipeline**: Extracts entities and sentiment data
3. **Database Layer**: Stores articles, entities, and analysis data
4. **Statistical Analysis**: Detects patterns and anomalies in sentiment
5. **API Service**: Provides access to the data and analysis
6. **Browser Extension**: Provides real-time analysis of articles being read

## Design Principles

The system is built on several key principles:

1. **Separation of Extraction and Analysis**:
   - LLMs extract factual sentiment data without making evaluative judgments
   - Statistical tools perform all comparative analysis and bias detection

2. **Hierarchical Data Model**:
   - Entities are analyzed at global, national, and source-specific levels
   - Sentiment distributions allow for statistical comparisons

3. **Efficiency and Scalability**:
   - Batch processing of articles and API calls
   - Asynchronous operations where appropriate
   - Database optimized for time-series analysis

4. **Robustness**:
   - Error handling and retries throughout the system
   - Fallback mechanisms for API and database failures
   - Comprehensive logging for troubleshooting

## Component Details

### Scraper Service

**Responsibility**: Collect articles from news sources on a scheduled basis.

- **RSS Scraper**: Fetches articles from RSS feeds
- **Scheduler**: Manages daily, weekly, and monthly scraping jobs
- **Rate Limiting**: Ensures respectful scraping of news sites

**Technologies**:
- Python with requests, feedparser, and newspaper3k
- Schedule library for job scheduling

### Cultural Orientation Pipeline

**Responsibility**: Analyze how news sources implicitly establish moral direction through entity portrayal.

- **Entity Orientation Analyzer**: Uses OpenAI to identify entities that serve as moral anchors
- **Cultural Positioning Detector**: Analyzes how entities are framed relative to an implicit societal vision
- **Framing Analyzer**: Optional analysis of narrative framing techniques
- **Batch Processor**: Efficient processing of multiple articles

**Key Design Elements**:
- Inspired by Peter Pomerantsev's work on how information shapes perception
- Two-dimensional analysis: power portrayal and alignment with implicit societal direction
- Extraction of key phrases that reveal subtle moral positioning
- Tracking of how entity positioning shifts over time to align with strategic objectives
- Abstraction of individual mentions to their larger cultural/ideological forces

**Technologies**:
- OpenAI API with gpt-4.1-nano model for cost-efficiency
- Batch API processing for high-volume analysis
- Async processing for real-time extension analysis

### Database Layer

**Responsibility**: Store and efficiently retrieve articles, entities, and sentiment data.

**Schema**:
- `news_sources`: Information about news outlets
- `news_articles`: Scraped articles
- `entities`: Named entities (people, places, organizations)
- `entity_mentions`: Occurrences of entities with sentiment scores
- `entity_resolution`: Tracks entity aliases and merges
- `entity_stats`: Pre-calculated statistics for entities

**Technologies**:
- PostgreSQL with TimescaleDB extension
- SQLAlchemy ORM
- Alembic for migrations

### Statistical Analysis

**Responsibility**: Detect patterns, trends, and anomalies in sentiment data.

**Key Features**:
- **Sentiment Distributions**: Models how entities are portrayed at different levels
- **Statistical Testing**: Detects unusual sentiment patterns
- **Trend Analysis**: Tracks how sentiment changes over time
- **Fisher's Method**: Combines p-values for composite analysis

**Technologies**:
- NumPy and SciPy for statistical operations
- Pandas for data manipulation

### API Service

**Responsibility**: Provide access to data and analysis for clients.

**Key Endpoints**:
- `/entities`: Get information about entities
- `/trends`: Get sentiment trends over time
- `/analyze`: Run analysis on an article
- `/stats`: Get statistical distributions

**Technologies**:
- FastAPI
- Uvicorn ASGI server
- JWT for authentication

### Browser Extension

**Responsibility**: Analyze articles being read and compare to global patterns.

**Key Features**:
- Extracts article content from current page
- Sends content to API for analysis
- Displays sentiment scores and statistical significance
- Shows how unusual the article's sentiment is compared to typical coverage

**Technologies**:
- JavaScript/TypeScript
- Chrome Extension API

## Data Flow

1. **Scraping Phase**:
   - Scheduler triggers scraping jobs
   - RSS Scraper fetches article URLs and metadata
   - Article content is extracted and cleaned
   - Articles are stored in the database

2. **Processing Phase**:
   - Processor retrieves unprocessed articles
   - OpenAI API extracts entities and sentiment scores
   - Processed data is stored in database

3. **Analysis Phase**:
   - Statistical models are updated with new data
   - Sentiment distributions are calculated
   - Trends and anomalies are detected

4. **Access Phase**:
   - API serves data to clients
   - Browser extension analyzes articles being read
   - Users view comparisons and statistics

## Integration Points

1. **OpenAI API**:
   - Integration for entity extraction and sentiment analysis
   - Handles rate limiting, batching, and error handling

2. **Database**:
   - Connection pooling and session management
   - Migrations for schema evolution
   - Efficient queries for time-series data

3. **Browser Extension to API**:
   - RESTful API calls for analysis
   - Authentication and rate limiting

## Design Decisions and Tradeoffs

### LLM Usage Approach

**Decision**: Use LLMs only for entity extraction and sentiment scoring, not for bias detection.

**Rationale**:
- Keeps the data collection objective and free from LLM biases
- Allows for statistical analysis based on clean data
- Enables more transparent and explainable bias detection

**Tradeoff**: Loses some of the rich analysis that LLMs could provide, but gains scientific rigor.

### Two-Dimensional Sentiment Model

**Decision**: Use power/strength and moral/ethical dimensions for sentiment.

**Rationale**:
- Captures the most important aspects of entity portrayal
- Simple enough for consistent extraction
- Rich enough for meaningful analysis

**Tradeoff**: More dimensions would provide richer data but increase complexity and potential noise.

### Optional Framing Analysis

**Decision**: Offer framing analysis as a separate, optional component.

**Rationale**:
- Provides richer context when needed
- Keeps core sentiment data clean and objective
- Allows for different types of analysis

**Tradeoff**: Increases processing costs and complexity for a feature that isn't used in core statistical analysis.

## Future Extensions

1. **Entity Resolution Improvements**:
   - More sophisticated entity disambiguation
   - Handling of aliases and name variations
   - Entity knowledge graph

2. **Advanced Statistical Models**:
   - Bayesian hierarchical models
   - Time-series forecasting
   - Anomaly detection algorithms

3. **Additional Sentiment Dimensions**:
   - Competence/incompetence dimension
   - Agency/passivity dimension
   - Threat/safety dimension

4. **Multi-language Support**:
   - Expansion to non-English news sources
   - Cross-language sentiment comparison

5. **Real-time Alerts**:
   - Notification system for significant sentiment shifts
   - Monitoring of unusual coverage patterns