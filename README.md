# News Bias Analyzer

A non-judgmental computational framework for analyzing global news sentiment patterns.
LLMs extract entity-sentiment tuples (power and moral dimensions, −2..+2) from articles
scraped across ~124 global sources; statistics do all comparative analysis — the system
reveals divergence between information spheres without declaring anyone "biased."

See [CLAUDE.md](CLAUDE.md) for the project philosophy.

## Components

- **Pipeline**: RSS scraping → OpenAI Batch API entity-sentiment extraction →
  Postgres/TimescaleDB
- **Dashboard**: React + Vite web frontend (`frontend/`)
- **Extension**: Chrome extension (Manifest V3) analyzing the article you're reading
  against global baselines (`extension/`)

## Pipeline: from article to signal

```mermaid
flowchart TD
    subgraph Ingest
        A[RSS / CC-NEWS scrape] --> B[(news_articles<br/>text, html, publish_date)]
    end

    subgraph Extract
        B --> C[OpenAI Structured Outputs<br/>analyzer/prompts.py<br/>entity_type: country/person/business/<br/>organization/event/concept]
        C --> D[(entity_mentions<br/>power_score, moral_score per entity per article)]
        D --> E[(entities<br/>canonical_id resolves name variants)]
    end

    subgraph Resolve["Weekly resolution jobs"]
        E --> F[entity merge<br/>analyzer/entity_resolution.py]
        E --> G[entity pruning<br/>database/entity_pruning.py]
    end

    subgraph Aggregate
        D --> H[(mv_source_entity_week<br/>source x entity x week)]
    end

    subgraph Kernels["Analysis kernels (analyzer/narrative_metrics.py)"]
        H --> K1[contested_ranking<br/>cross-country JSD divergence]
        H --> K2[archetype / trajectory<br/>hero-villain-victim-nuisance]
        H --> K3[svd_source_map<br/>empirical ideological axes]
        H --> K4[salience_asymmetry<br/>who covers what, how loud]
        D --> K5[entity_embeddings<br/>PPMI+SVD cooccurrence,<br/>sentiment-profile SVD]
        H --> K6[drift_detection<br/>Pettitt changepoint:<br/>global vs source-residual]
    end

    subgraph Surface["Dashboard + extension"]
        K1 --> S1[The front line]
        K2 --> S2[Entity profile: archetype]
        K3 --> S3[Source map]
        K4 --> S4[Salience view]
        K5 --> S5[Related entities]
        K6 --> S6[Statistical surprise feed]
        B --> S7[Chrome extension:<br/>this article vs global baseline]
    end
```

Each kernel in the diagram is a pure, self-tested function (`python -m analyzer.narrative_metrics`)
over `mv_source_entity_week` or `entity_mentions` — no manual review or human-in-the-loop step
anywhere in the pipeline, by design (see [CLAUDE.md](CLAUDE.md)). `analyzer/event_study.py` is a
standalone, read-only script (not part of the live pipeline) that checks the project's founding
axiom — "sentiment moves in lockstep during real global events" — against the actual corpus.

## Quick start

```bash
cp .env.example .env         # set your OPENAI_API_KEY
./run.sh docker up           # start the TimescaleDB container
./run.sh docker init         # create tables / run migrations
./run.sh scraper             # scrape articles
./run.sh analyze daemon      # analyze via OpenAI Batch API
./run.sh server              # start the API servers
./run.sh dashboard           # start the frontend dev server
```

`./run.sh help` lists all commands.

## Documentation

- [State of the Project (2026)](docs/STATE_OF_PROJECT_2026.md) — current reality,
  cleanup log, deferred work, deployment plan
- [Seeding & Models](docs/SEEDING_AND_MODELS.md) — bulk datasets for backfilling
  history, model pricing, local-model options
- [Setup and Running](docs/SETUP_AND_RUNNING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Full documentation index](docs/README.md)
