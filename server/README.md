# News Bias Analyzer Server

This directory contains the server implementations for the browser extension and the dashboard frontend.

## Components

- `extension_api.py`: API server for the browser extension
- `dashboard_api.py`: API server for the dashboard frontend
- `server_manager.py`: Utility to run both servers in parallel

## Usage

The servers can be started using the main run script:

```bash
# Start both servers (extension API on port 8000, dashboard API on port 8001)
./run.sh server

# Start only the extension API server (port 8000)
./run.sh server extension

# Start only the dashboard API server (port 8001)
./run.sh server dashboard
```

## API Endpoints

### Extension API (Port 8000)

- `/health`: Health check endpoint
- `/entities`: List entities in the database
- `/entity/{entity_id}/sentiment`: Get sentiment data for a specific entity
- `/sources`: List all news sources
- `/trends`: Get sentiment trends for entities

### Dashboard API (Port 8001)

- `/health`: Health check endpoint
- `/entities`: List entities in the database
- `/entities/{entity_id}`: Get detailed information about a specific entity
- `/entities/{entity_id}/sentiment`: Get sentiment data for a specific entity
- `/sources`: List all news sources
- `/sources/{source_id}`: Get detailed information about a specific news source
- `/sources/{source_id}/sentiment`: Get sentiment data for a specific news source

## Development

Both servers use FastAPI and can be extended by adding new endpoints or routers.
The servers are configured to reload automatically when code changes are detected.