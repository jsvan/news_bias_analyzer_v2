#!/usr/bin/env python3
"""
Run migration 017: add entity_drift_events, the precomputed table backing the
drift-detection feed (analyzer/drift_detection.py + server/routers/drift_endpoints.py's
GET /narrative/drift-feed).

Distinguishes two kinds of statistically-significant sentiment changepoint
(analyzer/narrative_metrics.py::pettitt_test) for an entity's power/moral trajectory:
- GLOBAL (source_id IS NULL): the whole corpus's mean series shifted - "everyone moved
  together," an expected/real-world-driven event.
- SOURCE-SPECIFIC (source_id set): a single source's *residual* from the global mean
  (narrative_metrics.py::residual_series) shifted on its own - the interesting
  editorial-stance signal this feature exists to surface.

This table is a full-rebuild cache (analyzer/drift_detection.py::run_drift_detection_job
DELETEs and re-inserts every run, same convention as other scheduled recomputation jobs
in this codebase e.g. mv_source_entity_week's REFRESH) - not an append-only log, so no
unique constraint on (entity_id, source_id, dimension) is needed.

Run with: ./run.sh custom 'database/run_migration_017.py'
"""

import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run migration 017: create entity_drift_events."""

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False

    try:
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("Starting migration 017: entity_drift_events...")

        check_table = text("""
            SELECT table_name FROM information_schema.tables WHERE table_name = 'entity_drift_events'
        """)
        if session.execute(check_table).fetchone():
            logger.info("entity_drift_events already exists, skipping creation")
        else:
            logger.info("Creating entity_drift_events...")
            session.execute(text("""
                CREATE TABLE entity_drift_events (
                    id SERIAL PRIMARY KEY,
                    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                    source_id INTEGER REFERENCES news_sources(id) ON DELETE CASCADE,
                    dimension VARCHAR(10) NOT NULL,
                    week_start DATE NOT NULL,
                    statistic DOUBLE PRECISION NOT NULL,
                    p_value DOUBLE PRECISION NOT NULL,
                    mean_before DOUBLE PRECISION NOT NULL,
                    mean_after DOUBLE PRECISION NOT NULL,
                    detected_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            session.commit()
            logger.info("✓ Created entity_drift_events")

        check_lookup_index = text("""
            SELECT indexname FROM pg_indexes WHERE indexname = 'idx_entity_drift_events_lookup'
        """)
        if session.execute(check_lookup_index).fetchone():
            logger.info("idx_entity_drift_events_lookup already exists, skipping")
        else:
            logger.info("Creating idx_entity_drift_events_lookup...")
            session.execute(text("""
                CREATE INDEX idx_entity_drift_events_lookup ON entity_drift_events (entity_id, source_id)
            """))
            session.commit()
            logger.info("✓ Created idx_entity_drift_events_lookup")

        check_sig_index = text("""
            SELECT indexname FROM pg_indexes WHERE indexname = 'idx_entity_drift_events_significance'
        """)
        if session.execute(check_sig_index).fetchone():
            logger.info("idx_entity_drift_events_significance already exists, skipping")
        else:
            logger.info("Creating idx_entity_drift_events_significance...")
            session.execute(text("""
                CREATE INDEX idx_entity_drift_events_significance ON entity_drift_events (p_value)
            """))
            session.commit()
            logger.info("✓ Created idx_entity_drift_events_significance")

        logger.info("Migration 017 completed successfully!")

        summary = session.execute(text(
            "SELECT COUNT(*) AS rows FROM entity_drift_events"
        )).fetchone()
        logger.info("\n=== Migration Summary ===")
        logger.info(f"entity_drift_events rows: {summary.rows}")

        session.close()
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
