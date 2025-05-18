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

Create a `.env` file in the project root:

```bash
touch .env
```

Add the following content (adjust as needed):

```
# OpenAI API credentials
OPENAI_API_KEY=your_openai_api_key_here

# Database connection
DATABASE_URL=postgresql://newsbias:newsbias@localhost:5432/news_bias

# Logging
LOG_LEVEL=INFO
```

Alternatively, you can set these variables in your environment:

```bash
# macOS/Linux
export OPENAI_API_KEY=your_openai_api_key_here
export DATABASE_URL=postgresql://newsbias:newsbias@localhost:5432/news_bias

# Windows
set OPENAI_API_KEY=your_openai_api_key_here
set DATABASE_URL=postgresql://newsbias:newsbias@localhost:5432/news_bias
```

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

The simplest way to run the dashboard is using the provided script:

```bash
# Make the script executable if needed
chmod +x run_dashboard.sh

# Run the dashboard (API and frontend)
./run_dashboard.sh
```

This will:
- Start the API server on port 8000
- Start the frontend on port 3001
- Connect to your database using the DATABASE_URL from environment variables

### 2. Accessing the Dashboard

Once started, you can access:
- Dashboard interface: http://localhost:3001
- API endpoints: http://localhost:8000

### 3. Running Components Separately

If you prefer to run components individually:

```bash
# Run just the backend API
./run_dashboard.sh --backend

# Run just the frontend
./run_dashboard.sh --frontend

# Set up the database
./run_dashboard.sh --setup-db
```

## Data Collection and Analysis

### 1. Starting the Scraper Scheduler

The scheduler runs scraping jobs at configured intervals (daily, weekly, monthly).

```bash
# Run the full scraper with analysis
./run_full_scraper.sh

# Run the scraper without analysis
./run_scraper_no_analysis.sh
```

### 2. Running Analysis on Articles

```bash
# Analyze all articles
./run_analyze_all.sh

# Analyze only articles that haven't been analyzed yet
./run_analyze_existing.sh
```

## Testing the Components

### 1. Entity Extraction and Sentiment Analysis

```bash
# Basic entity extraction test
python -m processors.examples.entity_extraction_example

# With framing analysis
python -m processors.examples.entity_extraction_example --framing

# Using a specific model
python -m processors.examples.entity_extraction_example --model gpt-4.1-nano
```

### 2. Test Scraping a Single Source

```bash
# Test scraping BBC
python -m scrapers.rss_scraper BBC
```

## Advanced Configuration

### Dashboard API Settings

The dashboard API settings are configured in `api/fixed_api.py`. The main settings include:

- Database connection URL
- CORS configuration for cross-origin requests
- Sample data for fallback when the database is unavailable

### Using Docker

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d api
```

### Running Statistical Analysis

```bash
# Generate entity sentiment distributions
python -m analysis.generate_distributions

# Analyze sentiment trends
python -m analysis.trend_analysis --entity "United States" --days 90
```

## Monitoring and Maintenance

### 1. Checking Database Status

View the current database status and statistics:

```bash
./run_db_stats.sh
```

### 2. Checking Logs

```bash
# View API logs
cat logs/api-server.log

# View frontend logs
cat logs/frontend.log
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
```

### 4. API Usage Monitoring

```bash
# View OpenAI API usage statistics
python -m processors.usage_stats
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
   psql -U newsbias -d news_bias -h localhost
   ```

### 2. Database Connection Errors

- Verify PostgreSQL is running: `pg_isready`
- Check credentials in `.env` file
- Ensure database exists: `psql -U newsbias -c "SELECT 1" news_bias`

### 3. OpenAI API Errors

- Verify API key is valid
- Check API rate limits and quotas
- Test with minimal example: `python -m processors.test_openai_connection`

### 4. Scraper Issues

- Check internet connectivity
- Verify site hasn't changed its structure
- Test single source: `python -m scrapers.rss_scraper CNN --verbose`

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