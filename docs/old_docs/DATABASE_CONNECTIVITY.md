# News Bias Analyzer: Database Connectivity

## Summary

The News Bias Analyzer uses a PostgreSQL database to store real news articles, entities, sentiment data, and more. This document summarizes the database connectivity and working approach.

## Database Content

As of May 10, 2025, the database contains:
- 52 news sources
- 80 total articles (67 of which have been analyzed)
- 430 entities
- 563 entity mentions
- 237 topics
- 112 quotes

## Key Entities

The database contains information about several key political figures and entities, including:
- Donald Trump (18 mentions)
- Joe Biden (4 mentions)
- China (5 mentions)
- Russia (2 mentions)

## Stable API Access

We've created a simplified API (simple_api.py) that offers a clean, reliable connection to the database with these endpoints:
- `/sources` - List of all news sources with article counts
- `/entities` - List of entities with mention counts
- `/articles` - Recent articles with basic metadata

## Connection Details

### Database URL
```
postgresql://newsbias:newsbias@localhost:5432/news_bias
```

### Connecting Programmatically
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create engine and session
engine = create_engine("postgresql://newsbias:newsbias@localhost:5432/news_bias")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Use the session
with SessionLocal() as db:
    sources = db.query(NewsSource).all()
```

## Running the API Server

Use the provided script for a reliable API server start:
```bash
./run_simple_api.sh
```

This script will:
1. Check if the port is already in use and clear it
2. Activate the virtual environment
3. Install required packages if needed
4. Test the database connection
5. Start the database Docker container if needed
6. Start the API server on 127.0.0.1:8005

## Checking Database Status

To view the current database contents:
```bash
./run_db_stats.sh
```

This provides a comprehensive overview of news sources, articles, entities, and sentiment statistics.

## Bias Analysis

The database schema supports several types of bias analysis:
- Time-weighted sentiment analysis using exponential decay
- Statistical bias detection with Z-scores (indicating deviation from norms)
- Entity sentiment comparison across different news sources
- Topic coverage patterns showing media priorities

## Docker Management

The database runs in a Docker container named `news-bias-postgres`. You can manage it with:
```bash
# Check if running
docker ps | grep news-bias-postgres

# Start/restart container
./scripts/utils/docker_setup.sh
```