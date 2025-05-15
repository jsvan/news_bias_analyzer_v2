# Full Text Storage Guide

This document explains how article text is stored in the News Bias Analyzer system and the improvements made to ensure full text is preserved.

## Overview

The News Bias Analyzer now stores the complete text of each article in the database, allowing for:

1. More accurate analysis
2. Better search capabilities 
3. Comprehensive quote extraction
4. Complete article viewing in the dashboard

PostgreSQL's built-in compression is used after analysis to reduce database size without losing any data.

## Storage Process

The article storage process follows these steps:

1. **Scraping**: Full article text is extracted from news websites using the parallel scraper
2. **Storage**: Complete text is stored in the database (no truncation)
3. **Analysis**: Articles are analyzed by the OpenAI processor
4. **Compression**: After analysis, PostgreSQL compression is applied to save space

## Managing Article Storage

Several utilities are provided to help manage article storage:

### Delete Truncated Articles

The `delete_truncated_articles.py` script identifies and removes ONLY articles that meet BOTH criteria:
- Have NOT YET been analyzed (processed_at is NULL)
- Have truncated text (contain the marker '[...additional content truncated...]')

IMPORTANT: Articles that have already been analyzed will NOT be deleted, even if they have truncated text. This script only removes unanalyzed articles with incomplete text so they can be re-scraped with full text.

The script will show you detailed statistics and ask for confirmation before deleting anything:

```bash
# Dry run (just show what would be deleted)
python scripts/delete_truncated_articles.py

# Actually delete the articles
python scripts/delete_truncated_articles.py --execute
```

### Compress Analyzed Articles

The `compress_analyzed_articles.py` script uses PostgreSQL's compression to reduce database size after analysis. It only compresses articles that have been fully analyzed.

```bash
# Dry run (just show what would be compressed)
python scripts/compress_analyzed_articles.py

# Actually compress the articles
python scripts/compress_analyzed_articles.py --execute

# Process in bigger batches (default is 100)
python scripts/compress_analyzed_articles.py --execute --batch-size 200
```

The script automatically detects what compression type your PostgreSQL version supports:
- LZ4 compression (PostgreSQL 14+): Better compression ratio and faster decompression
- PGLZ compression: Default for older PostgreSQL versions

## Technical Implementation

### Changes Made

1. Modified `scrapers/scrape_to_db.py` to store full article text instead of just a summary
2. Created utilities to manage articles with truncated text and compress analyzed articles
3. Updated `run_analyzer.sh` to automatically compress articles after analysis
4. Used PostgreSQL's built-in compression features for efficient storage

### Database Model

The `NewsArticle` model includes fields for both the full text and the HTML content:

```python
class NewsArticle(Base):
    __tablename__ = 'news_articles'
    
    id = Column(String(32), primary_key=True)
    # ... other fields ...
    text = Column(Text)  # Full article text
    html = Column(Text, nullable=True)  # Original HTML if available
    # ... other fields ...
```

## Benefits

This approach provides several benefits:

1. **Data Integrity**: No information is lost from the original articles
2. **Efficient Storage**: Compression is applied after analysis to save space
3. **Better Analysis**: Access to the full article text improves analysis quality
4. **Future-Proof**: All article data is preserved for future analysis methods

## Recommended PostgreSQL Settings

For optimal performance with full article text storage:

1. Ensure your PostgreSQL version is 14+ for LZ4 compression
2. Configure appropriate TOAST settings for large text fields
3. Consider increasing work_mem for large text operations
4. Set maintenance_work_mem appropriately for vacuum operations

The system will use whatever compression is available in your PostgreSQL version, but LZ4 is recommended for best performance.