# News Bias Analysis Dashboard

This dashboard provides visualizations for analyzing bias patterns across different news sources. It offers tools to:

1. Compare news sources by similarity in how they cover the same topics
2. Track sentiment trends for entities (people, organizations, countries) across different sources
3. Compare topic coverage patterns over time
4. Analyze political clustering of media outlets

## Quick Start

To run the dashboard:

```bash
./run_dashboard.sh
```

This script will:
1. Kill any existing processes on the required ports (8000, 3001)
2. Set up the needed dependencies
3. Try to connect to a PostgreSQL database if available
4. Fall back to sample data if database connection fails
5. Start the backend API server
6. Start the frontend dashboard interface

Access the dashboard at:
- **Frontend**: http://localhost:3001
- **API**: http://localhost:8000

Press `Ctrl+C` to stop all dashboard services.

## Running Options

The dashboard script supports several options:

```bash
./run_dashboard.sh [option]
```

### Available Options

- No option: Run both frontend and backend (will use database if available, otherwise sample data)
- `--frontend`: Run only the frontend (API must be running separately)
- `--backend`: Run only the backend API server
- `--setup-db`: Set up the database (required before first run with real data)
- `--clean`: Clean all node_modules and reinstall dependencies
- `--help`: Show help message

## Database Connection (Real Data)

The dashboard now automatically attempts to connect to a PostgreSQL database. If the connection succeeds, it will use real data. If the connection fails, it will fall back to sample data.

You'll know which mode the dashboard is running in:
- The API root endpoint (http://localhost:8000) will indicate "connected to database" or "using sample data"
- Log messages will show ✅ or ❌ connection status

### Setting Up a Database Connection

To use real data:

```bash
# Set your database connection string (otherwise defaults to localhost)
export DATABASE_URL="postgresql://username:password@localhost:5432/news_bias"

# Set up the database (only needed once)
./run_dashboard.sh --setup-db

# Run with automatic database connection
./run_dashboard.sh
```

The dashboard will try to use your database and gracefully fall back to sample data if any issues occur.

## Dashboard Features

### Component Structure

The dashboard has three main visualization tabs:

1. **Source Similarity**
   - Shows clustering of news sources by sentiment patterns
   - Identifies sources with similar reporting styles
   - Visualizes political leaning clusters

2. **Entity Sentiment Trends**
   - Tracks how entities are portrayed across different sources
   - Compares sentiment evolution over time
   - Highlights reporting bias for specific entities

3. **Topic Coverage Comparison**
   - Analyzes different sources' attention to various topics
   - Compares coverage intensity between outlets
   - Shows topic prioritization differences

### Dependencies

The dashboard requires:
- Node.js 14+
- npm
- Python 3.8+
- (Optional) PostgreSQL database for real data

If you encounter any dependency issues, use the `--clean` option:
```bash
./run_dashboard.sh --clean
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**
   - If ports 8000 or 3001 are already in use, the dashboard may fail to start
   - The script attempts to kill any existing processes on these ports
   - If problems persist, manually check what's using these ports:
     ```bash
     lsof -i :8000
     lsof -i :3001
     ```

2. **TypeScript Errors**
   - TypeScript warnings may appear during development
   - These won't prevent the dashboard from running
   - The script has been updated to suppress these errors

3. **API Connection Issues**
   - If the frontend shows errors connecting to the API
   - Check if the API is running: `curl http://localhost:8000`
   - Restart the dashboard with `./run_dashboard.sh`

### Logs

Check the log files in the `logs/` directory:
- `api-server.log`: Backend API server logs
- `frontend.log`: React frontend logs

For more details, consult the full documentation in the `docs/` directory.