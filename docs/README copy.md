# News Bias Analyzer

This project analyzes news articles to detect bias and sentiment patterns across different sources.

## Core Components

1. **Database** - PostgreSQL database with SQLAlchemy models
2. **Scraper** - RSS feed scraper to collect articles from various news sources
3. **Analyzer** - OpenAI-powered text analysis for sentiment and framing
4. **Frontend** - Web dashboard for visualizing sentiment statistics
5. **Extension** - Chrome extension for contextualizing articles within global sentiment

Each component is designed to be modular and focused on its specific responsibility.

## Docker Database Setup

The project now includes a Docker-based database setup for reliable, persistent data storage:

```bash
# Start the PostgreSQL database in Docker
./run.sh docker up

# Initialize the database schema
./run.sh docker init

# Check database status
./run.sh docker status

# Connect to the database with psql
./run.sh docker shell
```

See [Database Docker Guide](database/DATABASE_DOCKER_GUIDE.md) for complete details on database management with Docker.

## Usage

The project includes a simplified runner script (`run.sh`) to execute the various components:

```bash
# Run the news scraper
./run.sh scraper

# Run the analyzer (default 10 articles)
./run.sh analyzer

# Run the analyzer with a specific limit
./run.sh analyzer 50

# Start the API server
./run.sh api

# Start the web dashboard
./run.sh dashboard

# Manage the Docker database
./run.sh docker [up|down|restart|status|logs|init|backup|restore|shell]

# Run a custom Python script
./run.sh custom path/to/script.py
```

### Custom Scripts

The `custom` command allows you to run your own Python scripts in the project environment. Scripts can be structured in two ways:

1. With a `go()` function (recommended):
   ```python
   def go():
       # Your code here
       from database.db import DatabaseManager
       # Access project modules and resources
       
   if __name__ == "__main__":
       go()
   ```

2. Direct execution:
   ```python
   # Your code here
   from database.db import DatabaseManager
   # Access project modules and resources
   ```

Custom scripts have access to all project modules and the environment variables loaded from `.env`.