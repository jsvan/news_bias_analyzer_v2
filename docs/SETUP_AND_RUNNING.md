# News Bias Analyzer - Setup and Running Guide

This document provides step-by-step instructions for setting up and running all components of the News Bias Analyzer system.

## Prerequisites

- Python 3.8+ with pip and venv
- PostgreSQL 12+ with TimescaleDB extension (optional but recommended)
- OpenAI API key with access to GPT-4 models (for sentiment analysis)
- Node.js 16+ and npm (for the dashboard frontend)
- Internet connection for scraping news sites
- Git (for cloning the repository)

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/news_bias_analyzer.git
cd news_bias_analyzer
```

### 2. Create and Activate Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# On macOS/Linux
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Environment Variables

```bash
cp .env.example .env
# then edit .env and set your OPENAI_API_KEY
```

`run.sh` loads `.env` automatically. See `.env.example` for all supported variables.

## Database Setup

### 1. Using Docker (Recommended)

The easiest way to set up the database is to use the Docker commands:

```bash
# Start the PostgreSQL database in Docker
./run.sh docker up

# Initialize the database schema (creates tables and runs migrations)
./run.sh docker init
```

The Docker setup automatically:
- Creates a PostgreSQL container with the correct configuration
- Sets up the necessary user accounts
- Installs the TimescaleDB extension
- Creates tables and runs all migrations

### 2. Database Management Commands

```bash
# View database status
./run.sh docker status

# Stop the database container
./run.sh docker down

# Connect to database with psql shell
./run.sh docker shell

# Create a database backup
./run.sh docker backup
```

## Running the Dashboard

The News Bias Analyzer Dashboard provides visualization of the collected and analyzed data.

### 1. Starting the Dashboard

```bash
# Start the API servers (extension + dashboard APIs)
./run.sh server

# In another terminal, start the frontend dev server
./run.sh dashboard
```

### 2. Accessing the Dashboard

Once started, you can access:
- Dashboard interface: the URL Vite prints (typically http://localhost:5173)
- API endpoints: http://localhost:8000

### 3. Running Components Separately

```bash
# Only the extension API or only the dashboard API
./run.sh server extension
./run.sh server dashboard
```

## Data Collection and Analysis

### 1. Scraping Articles

```bash
# Scrape all configured sources (limit per feed from SCRAPER_LIMIT_PER_FEED in .env)
./run.sh scraper
```

### 2. Running Analysis on Articles

```bash
# Submit unanalyzed articles to the OpenAI Batch API (one-time check)
./run.sh analyze

# Run continuously: submits new batches and collects finished ones
./run.sh analyze daemon

# Check batch progress
./run.sh analyze status
```

### 3. Running Statistical Analysis

```bash
# Weekly statistics, intelligence findings, and source clustering
./run.sh statistics

# Options: --force, --intelligence-only, --clustering-only, --status
```

## Monitoring and Maintenance

### 1. Checking Database Status

View the current database status and statistics:

```bash
# General database statistics
./run.sh status

# Detailed source statistics
./run.sh status sources

# Run analyzer diagnostics
./run.sh analyze diag
```

### 2. Checking Logs

```bash
# View API logs
cat logs/api-server.log

# View frontend logs
cat logs/frontend.log

# Monitor batch analyzer in real-time
./run.sh analyze status
```

### 3. Database Maintenance

```bash
# Backup database using Docker helper
./run.sh docker backup

# Database migrations are handled automatically by:
./run.sh docker init

# To run migrations manually:
cd database/migrations
alembic upgrade head

# Reset articles stuck in processing
./run.sh analyze reset-stuck --hours 24

# Reset database (clear entity data and reset article status)
./run.sh analyze reset-database --dry-run  # Check what would be reset
./run.sh analyze reset-database  # Actually reset the database
./run.sh analyze reset-database --keep-recent-hours=48  # Keep recent data
```

### 4. Data Recovery

```bash
# Recover from OpenAI batches
./run.sh analyze recover-batches

# View recovery options
./run.sh analyze recover-batches --help

# Recover only today's batches
./run.sh analyze recover-batches --today
```

## Troubleshooting

### 1. Dashboard Connection Issues

If the dashboard shows "Failed to load data" or connection errors:

1. Verify the API is running:
   ```bash
   curl http://localhost:8000
   ```

2. Check the API logs for errors:
   ```bash
   cat logs/api-server.log
   ```

3. Ensure the database connection is working:
   ```bash
   psql -U postgres -d news_bias -h localhost   # or: ./run.sh docker shell
   ```

### 2. Database Connection Errors

- Verify PostgreSQL is running: `pg_isready`
- Check credentials in `.env` file
- Ensure database exists: `psql -U postgres -c "SELECT 1" news_bias`

### 3. OpenAI API Errors

- Verify API key is valid
- Check API rate limits and quotas
- Run the analyzer diagnostic: `./run.sh analyze diag`

### 4. Scraper Issues

- Check internet connectivity
- Verify the feed hasn't moved: feed URLs live in `scrapers/news_sources.py`
- Run with a small limit: `SCRAPER_LIMIT_PER_FEED=1 ./run.sh scraper`

## Security Notes

1. Never commit `.env` files or any file containing API keys
2. Set appropriate file permissions for configuration files
3. Use API rate limiting and authentication for production deployments
4. Consider using a proxy for high-volume OpenAI API requests

## Next Steps After Setup

1. Configure scraping sources in `scrapers/news_sources.py`
2. Adjust scraping schedule in config
3. Start collecting data by running the scraper scheduler
4. Begin analysis once you have sufficient data
5. Explore the dashboard to visualize results