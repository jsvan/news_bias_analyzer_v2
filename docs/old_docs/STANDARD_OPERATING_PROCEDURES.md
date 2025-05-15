# News Bias Analyzer: Standard Operating Procedures

This document provides standardized procedures for working with the News Bias Analyzer system, ensuring consistent and reliable operation.

## Database Connection

### Connection String
The standard database connection string is:
```
postgresql://newsbias:newsbias@localhost:5432/news_bias
```

This can be overridden by setting the `DATABASE_URL` environment variable.

### Database Status
As of the latest update, the database contains:
- 52 news sources
- 80 total articles (67 analyzed)
- 430 entities
- 563 entity mentions
- 237 topics
- 112 quotes

## API Servers

### Simple API Server (Recommended)
The simplified API server provides direct database access with no sample data fallbacks:

```bash
# Start the server (bind to localhost)
cd /Users/jsv/Projects/news_bias_analyzer
source venv/bin/activate
python -m api.simple_api --host 127.0.0.1 --port 8005
```

Available endpoints:
- `/` - API status
- `/sources` - List of news sources
- `/entities` - List of entities
- `/articles` - Recent articles

### Full API Server
The full API includes additional endpoints with advanced bias analysis:

```bash
# Start the server (bind to localhost)
cd /Users/jsv/Projects/news_bias_analyzer
source venv/bin/activate
python -m api.local_api --host 127.0.0.1 --port 8000
```

Additional endpoints:
- `/similarity/source_list` - News sources
- `/similarity/entity_list` - Entities
- `/similarity/topic_list` - Topics
- `/similarity/source_similarity` - Source similarity analysis
- `/similarity/entity_trends` - Entity sentiment trends
- `/similarity/topic_coverage` - Topic coverage patterns

## Dashboard

### Running the Dashboard

```bash
# Start the dashboard with both frontend and backend
cd /Users/jsv/Projects/news_bias_analyzer
./run_dashboard.sh
```

Access the dashboard at:
- Frontend: http://localhost:3001
- API: http://localhost:8000

Dashboard options:
```bash
./run_dashboard.sh --frontend    # Run only frontend
./run_dashboard.sh --backend     # Run only backend
./run_dashboard.sh --setup-db    # Set up the database
./run_dashboard.sh --clean       # Clean and reinstall dependencies
```

## Data Processing

### Scraping Articles

```bash
# Run the full scraper (all sources)
./run_analyzer.sh scrape --max-articles 5

# Scrape specific sources
./run_analyzer.sh scrape --sources CNN BBC "New York Times" --max-articles 5

# Scrape and analyze in one step
./run_analyzer.sh scrape --sources CNN BBC --analyze
```

### Analyzing Articles

```bash
# Analyze unprocessed articles
./run_analyzer.sh analyze --limit 20

# Analyze all articles including previously analyzed
./run_analyzer.sh analyze --all

# Complete pipeline (scrape and analyze)
./run_analyzer.sh all --max-articles 5
```

### Database Summary

```bash
# View database statistics
./run_analyzer.sh summary

# Or use the Python script directly
python print_db_stats.py
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**
   - Check for processes using ports: `lsof -i :8000` or `lsof -i :8005`
   - Kill processes: `kill -9 $(lsof -ti:8000)`

2. **Database Connection Issues**
   - Verify Docker container is running: `docker ps | grep news-bias-postgres`
   - Restart Docker container if needed: `./scripts/utils/docker_setup.sh`

3. **API Connection Errors**
   - Ensure you're binding to localhost: Use `--host 127.0.0.1` instead of `0.0.0.0`
   - Check for firewalls blocking connections

### Testing Connections

```bash
# Test database connection
python -c "from sqlalchemy import create_engine; engine = create_engine('postgresql://newsbias:newsbias@localhost:5432/news_bias'); conn = engine.connect(); print('Connection successful')"

# Test API connection
curl http://127.0.0.1:8005/
```

## Best Practices

1. **Always use virtual environment**
   ```bash
   source venv/bin/activate
   ```

2. **Use localhost bindings for security**
   ```bash
   python -m api.simple_api --host 127.0.0.1 --port 8005
   ```

3. **Check database connection before starting API**
   ```bash
   python print_db_stats.py
   ```

4. **Keep the working directory consistent**
   All commands should be run from the project root: `/Users/jsv/Projects/news_bias_analyzer`

5. **Use consistent port numbers**
   - Simple API: Port 8005
   - Full API: Port 8000
   - Dashboard Frontend: Port 3001