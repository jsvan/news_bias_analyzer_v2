# News Bias Analyzer Scripts

This document provides an overview of the utility scripts available in the project.

## Consolidated Script (New Approach)

The project now uses a consolidated script approach that combines all functionality in a single tool:

- **`run_analyzer.sh`**: All-in-one script that handles Docker setup, database initialization, and provides a unified interface for all operations.

```bash
# Show available commands
./run_analyzer.sh

# Run complete pipeline (scrape and analyze)
./run_analyzer.sh all --max-articles 10

# Scrape articles only
./run_analyzer.sh scrape --sources CNN BBC --max-articles 5 

# Analyze existing articles
./run_analyzer.sh analyze --limit 20

# Show database summary
./run_analyzer.sh summary
```

### Available Commands

| Command | Description | Options |
|---------|-------------|---------|
| `all` | Run complete pipeline (scrape and analyze) | `--max-articles` (default: 5)<br>`--limit` (default: unlimited)<br>`--batch-size` (default: 5) |
| `scrape` | Scrape articles only | `--sources` (default: all sources)<br>`--max-articles` (default: 5)<br>`--workers` (default: 10)<br>`--analyze` (optional: analyze after scraping) |
| `analyze` | Analyze existing articles and extract quotes | `--limit` (default: unlimited)<br>`--all` (analyze all articles, including previously analyzed)<br>`--batch-size` (default: 5) |
| `summary` | Show database summary | None |

### Examples

```bash
# Run complete pipeline with 10 articles per source
./run_analyzer.sh all --max-articles 10

# Scrape CNN and BBC articles (5 per source)
./run_analyzer.sh scrape --sources CNN BBC --max-articles 5

# Scrape and immediately analyze articles
./run_analyzer.sh scrape --sources CNN BBC --analyze

# Analyze 20 unanalyzed articles
./run_analyzer.sh analyze --limit 20

# Analyze all articles, including previously analyzed ones
./run_analyzer.sh analyze --all

# Process articles in batches of 10 for better resumability
./run_analyzer.sh analyze --batch-size 10

# Analyze articles and extract quotes in one step (quotes are now extracted automatically)
./run_analyzer.sh analyze --limit 5

# Process all articles, including scraping, analysis, and quote extraction
./run_analyzer.sh all

# Show database summary
./run_analyzer.sh summary
```

## Legacy Scripts (Deprecated)

The following scripts are now deprecated and will be removed in a future update. Please use the consolidated `run_analyzer.sh` script instead.

### Article Scraping and Analysis

- **`run_news_scraper.sh`**: Basic pipeline with default sources (use `run_analyzer.sh scrape` instead)
- **`run_full_scraper.sh`**: Interactive scraper with 50+ news sources (use `run_analyzer.sh scrape` instead)
- **`run_scraper_no_analysis.sh`**: Scrapes without analysis (use `run_analyzer.sh scrape` instead)
- **`run_analyze_existing.sh`**: Analyzes a specific number of articles (use `run_analyzer.sh analyze --limit N` instead)
- **`run_analyze_all.sh`**: Analyzes all unprocessed articles (use `run_analyzer.sh analyze` instead)
- **`run_all.sh`**: Complete pipeline (use `run_analyzer.sh all` instead)

### Database and Analysis Viewing

- **`view_database.sh`**: Interactive database query (use `run_analyzer.sh summary` instead)
- **`view_analysis.sh`**: Shows sentiment analysis results (use `run_analyzer.sh summary` instead)
- **`run_api_server.sh`**: Starts the local API server (still supported)

## Utility Scripts (Still Supported)

### Data Management Tools

- **`python -m scripts.add_news_sources`**: Tool for adding more news sources to the database.
  ```bash
  # List all available sources
  python -m scripts.add_news_sources --list
  
  # Add all sources
  python -m scripts.add_news_sources --all
  
  # Add sources by country
  python -m scripts.add_news_sources --country "United States"
  
  # Add sources by political leaning
  python -m scripts.add_news_sources --leaning center-right
  
  # Add specific sources
  python -m scripts.add_news_sources --sources CNN BBC "New York Times"
  ```

### Analysis Monitoring

- **`python -m scripts.analysis_progress`**: Shows current progress of article analysis.
  ```bash
  # Basic progress report
  python -m scripts.analysis_progress
  
  # Detailed progress report
  python -m scripts.analysis_progress --verbose
  
  # Continuous monitoring (updates every 60 seconds)
  python -m scripts.analysis_progress --continuous
  
  # Customize monitoring interval 
  python -m scripts.analysis_progress --continuous --interval 30
  ```

## Environment Configuration

The project uses a `.env` file for configuration. Create this file in the project root with the following settings:

```
# Database
DATABASE_URL=postgresql://newsbias:newsbias@localhost:5432/news_bias

# OpenAI API
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-nano  # Optional, override default model

# Scraper settings
MAX_ARTICLES_PER_SOURCE=5
MAX_WORKERS=3
```

## Error Handling and Resumability

The consolidated script now includes robust error handling and resumability features:

1. **Batch Processing**: Articles are processed in configurable batches (default: 5 articles per batch). Each batch is independently committed to the database, so if the script is interrupted, only the current batch is affected.

2. **Auto-Resume**: When restarted, the script automatically continues from where it left off, processing only unanalyzed articles.

3. **Error Handling**: OpenAI API errors are properly handled:
   - Articles with errors are marked as processed to prevent infinite retry loops
   - Detailed error logs are provided
   - The script continues with the next article rather than aborting

4. **Raw OpenAI Response Display**: All raw OpenAI responses are displayed on screen for monitoring, along with token usage statistics.

5. **Progress Tracking**: Detailed progress information is shown during processing, including percentage complete and estimated time remaining.

## Database Status

The `run_analyzer.sh summary` command provides a detailed overview of the database contents, including:

- Total news sources
- Total articles (analyzed and unanalyzed)
- Entities and entity mentions
- Top sources by article count

## Running a Full Database Population

To populate the database with articles:

1. Edit `.env` to increase `MAX_ARTICLES_PER_SOURCE` if desired
2. Run the complete pipeline:
   ```bash
   ./run_analyzer.sh all --max-articles 10
   ```
3. If you want to add more articles later:
   ```bash
   ./run_analyzer.sh scrape --sources CNN BBC
   ```
4. Analyze unanalyzed articles:
   ```bash
   ./run_analyzer.sh analyze
   ```
5. View the results:
   ```bash
   ./run_analyzer.sh summary
   ```