"""
Tiny Postgres-backed system-metrics counters.

Replaces the last real use of the separate SQLite statistical database
(StatisticalDBManager.get/increment_system_metric), which was deleted in July
2026 - the running total of pruned entities was the only cross-run state it
still held. The table is created on first use (same defensive-DDL pattern as
entity_pruning.add_last_updated_column).
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_ENSURE = text("""
    CREATE TABLE IF NOT EXISTS system_metrics (
        metric_name TEXT PRIMARY KEY,
        metric_value BIGINT NOT NULL DEFAULT 0,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
""")


def get_system_metric(session: Session, name: str) -> int:
    """Current value of a named counter (0 if never written)."""
    session.execute(_ENSURE)
    value = session.execute(text(
        "SELECT metric_value FROM system_metrics WHERE metric_name = :name"
    ), {"name": name}).scalar()
    return int(value) if value is not None else 0


def increment_system_metric(session: Session, name: str, delta: int) -> int:
    """Atomically add delta to a named counter; returns the new value."""
    session.execute(_ENSURE)
    new_value = session.execute(text("""
        INSERT INTO system_metrics (metric_name, metric_value, updated_at)
        VALUES (:name, :delta, NOW())
        ON CONFLICT (metric_name)
        DO UPDATE SET metric_value = system_metrics.metric_value + :delta,
                      updated_at = NOW()
        RETURNING metric_value
    """), {"name": name, "delta": delta}).scalar()
    session.commit()
    return int(new_value)
