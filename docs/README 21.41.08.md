# News Bias Analyzer

A comprehensive system for analyzing sentiment in news articles, tracking patterns across sources, and identifying potential bias.

## Project Overview

The News Bias Analyzer tracks sentiment patterns in global news articles, focusing on entities (people, organizations, countries) and how different news sources portray them. The system uses natural language processing to analyze articles and identify potential bias.

### Key Features

- Article scraping from various news sources
- Sentiment analysis using OpenAI's advanced NLP
- Entity extraction and tracking
- Time-series analysis of sentiment trends
- Bias detection using statistical significance testing (when sufficient data is available)
- Interactive dashboard for data visualization
- Browser extension for realtime article analysis

## Quick Start

```bash
# Start both API and dashboard
./run.sh all

# Run the scraper to collect news articles
./run.sh scraper

# Analyze articles using OpenAI
export OPENAI_API_KEY=your_api_key
./run.sh analyze
```

## Available Commands

- `./run.sh api` - Start the API server
- `./run.sh dashboard` - Start the web dashboard
- `./run.sh all` - Start both API and dashboard
- `./run.sh scraper` - Run the news scraper
- `./run.sh analyze` - Analyze already scraped articles
- `./run.sh setup` - Set up the environment and database
- `./run.sh stats` - Show database statistics
- `./run.sh stop` - Stop all running components
- `./run.sh help` - Show help message

## Requirements

- Python 3.9+
- Node.js 16+
- PostgreSQL 13+
- OpenAI API key for analysis

## Project Structure

- `/api` - FastAPI backend endpoints
- `/analysis` - Sentiment analysis and bias detection algorithms  
- `/database` - Database models and migration scripts
- `/docs` - Documentation and guides
- `/docker` - Docker configuration files
- `/frontend` - React dashboard and browser extension
- `/processors` - OpenAI integration for article analysis
- `/scrapers` - News source scrapers

## Documentation

Comprehensive documentation is available in the [docs directory](docs/README.md):

- [API Reference](docs/API_REFERENCE.md) - API endpoints and usage
- [API Usage Examples](docs/API_USAGE_EXAMPLES.md) - Code examples in multiple languages
- [Architecture Overview](docs/ARCHITECTURE.md) - System design and components
- [Development Guide](docs/DEVELOPMENT_GUIDE.md) - Setup for developers
- [Browser Extension Guide](docs/EXTENSION_USAGE.md) - Using the browser extension
- [Dashboard User Manual](docs/DASHBOARD_USAGE.md) - Using the analytics dashboard
- [Setup and Running](docs/SETUP_AND_RUNNING.md) - Installation instructions
- [OpenAI-Only API](docs/OPENAI_ONLY_API.md) - Information about the OpenAI-based analysis

## Environment Variables

The system requires the following environment variables:

- `OPENAI_API_KEY` - Required for article analysis
- `DATABASE_URL` - PostgreSQL connection string (default: postgresql://newsbias:newsbias@localhost:5432/news_bias)

You can set these in two ways:

1. **Using a `.env` file** in the project root:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   DATABASE_URL=postgresql://newsbias:newsbias@localhost:5432/news_bias
   ```

2. **Directly in your shell**:
   ```bash
   export OPENAI_API_KEY=your_openai_api_key_here
   export DATABASE_URL=postgresql://newsbias:newsbias@localhost:5432/news_bias
   ```

The run.sh script automatically loads variables from the `.env` file if it exists.

## Browser Extension

The News Bias Analyzer browser extension provides realtime analysis of news articles:

1. Navigate to a news article
2. Click the extension icon
3. View sentiment analysis and bias detection

To build the extension:
```bash
./run.sh extension
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- OpenAI for NLP capabilities
- Various open-source libraries and frameworks used in this project