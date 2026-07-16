"""
Refresh jobs for materialized views. See database/run_migration_015.py for
mv_source_entity_week's definition.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def refresh_mv_source_entity_week(session: Session) -> None:
    """Refresh mv_source_entity_week (CONCURRENTLY - doesn't block reads mid-refresh).

    Requires the unique index created alongside the view in run_migration_015.py.
    Intended to run daily via scheduler/job_scheduler.py - weekly grain doesn't need
    more frequent refreshes, and this runs after the entity merge/pruning jobs so
    canonical_id resolution in the view reflects the latest merges.
    """
    logger.info("Refreshing mv_source_entity_week...")
    session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_source_entity_week"))
    session.commit()
    logger.info("✓ Refreshed mv_source_entity_week")
