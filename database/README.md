# Database Component

The database component stores news articles, entities, and sentiment analysis results.

## Database Schema

### Core Tables

- `news_sources`: Information about news publications
- `news_articles`: Article content and metadata
- `entities`: Entities mentioned in articles (people, organizations, etc.)
- `entity_mentions`: Sentiment analysis of entities in articles

### Quote Tracking Tables

- `public_figures`: Notable people whose quotes are being tracked
- `quotes`: Quotes extracted from articles
- `topics`: Topic categorization for quotes
- `quote_topics`: Links quotes to topics with relevance scores

### Similarity Analysis Tables

- `similarity_embeddings`: Article embedding vectors
- `topic_models`: Topic clustering models and results
- `article_similarities`: Precomputed similarity scores between article pairs

## Database Diagram

```
news_sources
  ↓
news_articles
  ↓
┌───────────────┬────────────────┐
│               │                │
entities        quotes           similarity_embeddings
  ↓               ↓                     
entity_mentions  quote_topics    article_similarities
                   ↑                      
                 topics         topic_models
```

## Features
- SQLAlchemy ORM models
- Alembic migrations for schema changes
- Entity resolution and sentiment tracking
- Text compression for efficient storage
- Quote extraction and tracking

## Key Files
- `db.py` - Database connection manager
- `models.py` - Core data models
- `models_similarity.py` - Similarity-specific models
- `create_tables.py` - Table creation utility
- `setup_db.sh` - Database setup script
- `db_stats.py` - Database statistics utilities

## Database Setup

Run the setup script to initialize the database:

```sh
./run.sh setup
```

## Database Statistics

```sh
./run.sh status
```