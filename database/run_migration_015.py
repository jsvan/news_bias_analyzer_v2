#!/usr/bin/env python3
"""
Run migration 015: add mv_source_entity_week, the per-source-entity-week aggregate the
dashboard's cross-source statistics (analyzer/narrative_metrics.py's kernels - archetype,
contested_ranking, svd_source_map, etc.) need.

This is deliberately a *new*, separate artifact from weekly_sentiment_stats /
analyzer/hotelling_t2.py::update_weekly_statistics - that table serves a different purpose
(per-article extremeness scoring against a recent global entity-level baseline, no source
dimension needed) and stays as-is.

entity_id is resolved through COALESCE(canonical_id, id) so entity-merge cleanups
(analyzer/entity_resolution.py) automatically reach every downstream query built on this
view, and week_start buckets on the article's publish_date (when the news happened), not
when our pipeline got around to analyzing it.

A materialized view needs at least one unique index to support REFRESH ... CONCURRENTLY
(see refresh_mv_source_entity_week, scheduled daily in scheduler/job_scheduler.py) - the
(source_id, entity_id, week_start) index below is both that unique index and the
query-performance index the original per-source query gap needed.

Run with: ./run.sh custom 'database/run_migration_015.py'
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
    """Run migration 015: create mv_source_entity_week."""

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False

    try:
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("Starting migration 015: mv_source_entity_week...")

        check_view = text("""
            SELECT matviewname FROM pg_matviews WHERE matviewname = 'mv_source_entity_week'
        """)
        if session.execute(check_view).fetchone():
            logger.info("mv_source_entity_week already exists, skipping creation")
        else:
            logger.info("Creating mv_source_entity_week...")
            session.execute(text("""
                CREATE MATERIALIZED VIEW mv_source_entity_week AS
                SELECT
                    na.source_id,
                    COALESCE(e.canonical_id, e.id) AS entity_id,
                    date_trunc('week', na.publish_date)::date AS week_start,
                    AVG(em.power_score) AS mean_power,
                    AVG(em.moral_score) AS mean_moral,
                    COUNT(*) AS n
                FROM entity_mentions em
                JOIN news_articles na ON em.article_id = na.id
                JOIN entities e ON em.entity_id = e.id
                WHERE em.power_score IS NOT NULL
                    AND em.moral_score IS NOT NULL
                    AND na.publish_date IS NOT NULL
                    AND na.source_id IS NOT NULL
                GROUP BY na.source_id, COALESCE(e.canonical_id, e.id),
                         date_trunc('week', na.publish_date)::date
            """))
            session.commit()
            logger.info("✓ Created mv_source_entity_week")

        check_index = text("""
            SELECT indexname FROM pg_indexes
            WHERE indexname = 'idx_mv_source_entity_week_pk'
        """)
        if session.execute(check_index).fetchone():
            logger.info("idx_mv_source_entity_week_pk already exists, skipping")
        else:
            logger.info("Creating unique index (required for CONCURRENTLY refresh)...")
            session.execute(text("""
                CREATE UNIQUE INDEX idx_mv_source_entity_week_pk
                ON mv_source_entity_week (source_id, entity_id, week_start)
            """))
            session.commit()
            logger.info("✓ Created idx_mv_source_entity_week_pk")

        logger.info("Migration 015 completed successfully!")

        summary = session.execute(text(
            "SELECT COUNT(*) AS rows, COUNT(DISTINCT source_id) AS sources, "
            "COUNT(DISTINCT entity_id) AS entities FROM mv_source_entity_week"
        )).fetchone()
        logger.info("\n=== Migration Summary ===")
        logger.info(f"mv_source_entity_week rows: {summary.rows}")
        logger.info(f"Distinct sources: {summary.sources}")
        logger.info(f"Distinct entities: {summary.entities}")

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
