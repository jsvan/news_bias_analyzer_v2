# State of the Project — July 2026 Review

A full review after a year dormant. This records what's real, what was cleaned up, and
what's deliberately deferred — so decisions don't get re-litigated.

## What the system actually is (verified July 2026)

- **Pipeline**: `run.sh` dispatches everything. Scrape (124 RSS sources hardcoded in
  `scrapers/news_sources.py`) → analyze (OpenAI Batch API, `analyzer/batch_analyzer.py`,
  power/moral scores per entity mention) → Postgres/TimescaleDB → two FastAPI servers
  (`server/extension_api.py`, `server/dashboard_api.py`) → React dashboard + Chrome
  extension (Manifest V3).
- **No hosted backend exists.** The GitHub Pages frontend (jsvan.github.io/news_analysis)
  shows "API unavailable" without a locally running server. All `*.example.com` API URLs
  were placeholders (now removed).
- The synchronous analyzer path (`analyzer/openai_integration.py`) is NOT dead code — it
  serves the extension's real-time `POST /analyze`. The Batch API path handles bulk.

## Cleaned up in this pass (July 2026)

- Deleted the dead Docker/Celery deployment: phantom services in `docker-compose.yml`
  (referenced nonexistent `./api`, `./processors`, `./analysis`), all of `docker/`,
  `docs/deployment_infrastructure.md`, `docs/aws_deployment.md`. Compose now runs only
  TimescaleDB, driven by `database/db-docker.sh`.
- Removed dead `run.sh` commands `batch` and `api` (pointed at nonexistent modules);
  fixed the `extension` command's path.
- Deleted dead frontend code: `NewsComparisonPage.tsx`, `CountryEntityChart.tsx`
  (unreferenced), duplicate `frontend/src/config/environment.ts`.
- Deleted the superseded extension popup monolith `extension/js/popup.js` (the popup
  runs on `popup-new.js` + `js/components/`).
- **Fixed a real extension bug**: `api-service.js` resolved its endpoint from
  environment detection that returned the placeholder production URL inside the popup.
  The endpoint now comes from chrome.storage (options page), matching `background.js`.
- Simplified `frontend/services/config/environment.ts` (no staging env, no fake
  hosts; `VITE_API_BASE_URL` or empty). Frontend typechecks and builds clean.
- Added `.env.example`; rewrote fictional commands in `docs/SETUP_AND_RUNNING.md` and
  the fictional directory tree in `docs/DEVELOPMENT_GUIDE.md`.
- New: `docs/SEEDING_AND_MODELS.md` — bulk datasets for backfill + current model pricing.

## Known warts, deliberately deferred

Do these on a machine that can run the full stack (DB + servers), not blind:

1. **Server consolidation.** Two FastAPI apps with overlapping routes (`/entities`,
   `/sources`, stats) plus `server/server_manager.py`, a subprocess babysitter that
   polls every second. Target: one FastAPI app, two routers, one `uvicorn` command,
   delete the manager. Requires resolving route collisions and updating the frontend
   and extension clients — needs runtime testing.
2. **DB layer over-layering.** `database/db.py` → `services.py` → `repositories.py` is
   a chain (not duplicates); `repositories.py` has exactly one consumer (`services.py`),
   which has one real consumer (`batch_analyzer.py`). Could be flattened to ~1 file.
   Low value, medium risk — only worth it when touching the analyzer anyway.
3. **Python-in-JS-trees.** `extension/api/` and `frontend/api/` contain Python routers
   imported by the servers. Move to `server/routers/` during the server consolidation.
4. **Intelligence layer is half-built.** `intelligence/intelligence_manager.py` has ~43
   TODO-stubbed methods; `graph_analysis/` is empty scaffolding (docs/roadmap only).
   Decide: finish or fold findings into Postgres and delete the separate SQLite DB
   (`statistical_database/`).
5. **Stale cost limiter.** `estimate_cost()` in `analyzer/openai_integration.py` uses
   2023 prices, so the $50/day limit math is wrong. Fix when changing models.
6. **Structured outputs.** Move batch + sync analyzers from `json_object` to strict
   `json_schema` when next touching them.

## Deployment plan (agreed direction)

- **Dashboard**: precompute JSON snapshots from weekly stats and publish them with the
  frontend to GitHub Pages. No hosted server needed for the public dashboard.
- **Extension**: needs a live API (`POST /analyze`). Host the consolidated FastAPI app
  on a small VPS/fly.io when ready; until then, localhost via the options page.
- **Backfill**: seed history per `docs/SEEDING_AND_MODELS.md`, then `./run.sh analyze
  daemon` chews through it via the Batch API.

## Roadmap (unchanged in spirit from todo.txt)

The highest-value unbuilt feature is **source similarity** (todo.txt items 1–5):
Pearson correlation on common entities, weekly similarity matrix, clustering. It's the
feature that makes the project's thesis visible. Build it before adding new data
machinery.
