# News Bias Analyzer Server

One consolidated FastAPI app serves the browser extension, the dashboard
frontend, and the snapshot exporter.

## Components

- `extension_api.py`: the single FastAPI app (port 8000). Declares the core
  endpoints (`/entities`, `/sources`, `/analyze`, `/stats/*` basics) and mounts
  every router.
- `deps.py`: shared database dependency (`get_db`) — one engine, sessions
  closed per request.
- `routers/`: one module per endpoint group, each declared in exactly one place:
  - `statistical_endpoints.py` (`/stats/*` distributions, tracking, top-entities)
  - `similarity_endpoints.py` (`/similarity/*`)
  - `narrative_endpoints.py`, `embeddings_endpoints.py`, `drift_endpoints.py`
    (`/narrative/*`)
  - `dashboard_endpoints.py` (entity/source detail pages)
- `export_snapshots.py`: dumps API responses to `frontend/public/snapshots/`
  for the GitHub Pages static dashboard.

## Usage

```bash
./run.sh server
# equivalent to: uvicorn server.extension_api:app --host 0.0.0.0 --port 8000
```

The full route table is at http://localhost:8000/docs.

## History

`dashboard_api.py` (a second app on port 8001), `server_manager.py` (a
subprocess babysitter), and the Python router trees inside `extension/api/` and
`frontend/api/` were consolidated into this layout in July 2026 — one app, one
port, one `uvicorn` command.
