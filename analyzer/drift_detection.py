#!/usr/bin/env python3
"""
Weekly statistical-surprise / drift-detection job (Phase 5 of the narrative-analysis
roadmap, docs/ROADMAP_IDEAS_2026.md).

Distinguishes two kinds of statistically-significant changepoint
(analyzer/narrative_metrics.py::pettitt_test) in an entity's power/moral trajectory:

  GLOBAL   - the corpus-wide mean series itself shifted: "everyone moved together,"
             an expected/real-world-driven event (e.g. a war breaking out).
  SOURCE   - one source's *residual* from the global mean
             (analyzer/narrative_metrics.py::residual_series) shifted on its own -
             "this source moved unexplained by the global trend," the actually-
             interesting editorial-stance signal this feature exists to surface.

Results are written to entity_drift_events (database/run_migration_017.py). This is a
full-rebuild cache, same convention as this codebase's other scheduled recomputation
jobs (e.g. mv_source_entity_week's REFRESH): every run DELETEs and re-inserts, no
attempt to diff against prior rows.

Run manually via: ./run.sh custom 'analyzer/drift_detection.py' [--dry-run]
Intended to be wired into scheduler/job_scheduler.py (not done here - someone else
owns that file for this phase).
"""

import os
import sys
import logging
from pathlib import Path

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.narrative_metrics import pettitt_test, residual_series

# No basicConfig here: this module is imported as a library, and configuring
# the root logger at import time silently overrides the entrypoint's config.
logger = logging.getLogger(__name__)

DIMENSIONS = ["power", "moral"]


def _global_series(session: Session, entity_id: int, dim: str):
    """Unweighted per-week average across sources for one entity/dimension.

    Returns (weeks, values) both ordered by week_start. Only weeks with at least one
    source row appear (mv_source_entity_week has no NaN rows), so values has no gaps.
    """
    col = f"mean_{dim}"
    rows = session.execute(text(f"""
        SELECT week_start, AVG({col}) AS val
        FROM mv_source_entity_week
        WHERE entity_id = :entity_id
        GROUP BY week_start
        ORDER BY week_start
    """), {"entity_id": entity_id}).fetchall()
    weeks = [r.week_start for r in rows]
    values = [float(r.val) for r in rows]
    return weeks, values


def _source_series_by_source(session: Session, entity_id: int, dim: str, weeks):
    """{source_id: [value-or-NaN aligned to `weeks`]} for sources with >= 8 non-null
    weeks of data for this entity - matching pettitt_test's own floor, so we don't
    even attempt sources that could never produce a result."""
    col = f"mean_{dim}"
    rows = session.execute(text(f"""
        SELECT source_id, week_start, {col} AS val
        FROM mv_source_entity_week
        WHERE entity_id = :entity_id
    """), {"entity_id": entity_id}).fetchall()

    by_source = {}
    for r in rows:
        by_source.setdefault(r.source_id, {})[r.week_start] = float(r.val)

    aligned = {}
    for source_id, week_map in by_source.items():
        if len(week_map) < 8:
            continue
        aligned[source_id] = [week_map.get(w, np.nan) for w in weeks]
    return aligned


def _event_from_result(entity_id, source_id, dim, weeks, result):
    """Map a pettitt_test result onto our (week_start, ...) row shape.

    changepoint_index is a position in the ORIGINAL (pre-NaN-drop) series - i.e. it
    indexes directly into `weeks` - so the first week of the "after" segment (the
    actual shift date we store) is simply weeks[changepoint_index + 1].
    """
    after_idx = result["changepoint_index"] + 1
    if after_idx >= len(weeks):
        return None  # defensive; pettitt_test's construction should never produce this
    return {
        "entity_id": entity_id,
        "source_id": source_id,
        "dimension": dim,
        "week_start": weeks[after_idx],
        "statistic": result["statistic"],
        "p_value": result["p_value"],
        "mean_before": result["mean_before"],
        "mean_after": result["mean_after"],
    }


def _compute_events(session: Session, min_mentions: int = 10,
                     significance: float = 0.05) -> list:
    """Core computation shared by the real run and --dry-run: candidate entities ->
    global + per-source-residual pettitt tests -> list of event dicts. Read-only."""
    candidates = session.execute(text("""
        SELECT entity_id, SUM(n) AS total_n
        FROM mv_source_entity_week
        GROUP BY entity_id
        HAVING SUM(n) >= :min_mentions
    """), {"min_mentions": min_mentions}).fetchall()
    logger.info(f"{len(candidates)} candidate entities with >= {min_mentions} mentions")

    events = []
    for row in candidates:
        entity_id = row.entity_id
        for dim in DIMENSIONS:
            weeks, global_values = _global_series(session, entity_id, dim)
            if len(global_values) < 8:
                continue

            g_result = pettitt_test(global_values)
            if g_result is not None and g_result["p_value"] < significance:
                event = _event_from_result(entity_id, None, dim, weeks, g_result)
                if event:
                    events.append(event)

            source_series = _source_series_by_source(session, entity_id, dim, weeks)
            for source_id, series in source_series.items():
                resid = residual_series(series, global_values)
                s_result = pettitt_test(resid)
                if s_result is not None and s_result["p_value"] < significance:
                    event = _event_from_result(entity_id, source_id, dim, weeks, s_result)
                    if event:
                        events.append(event)

    logger.info(f"Computed {len(events)} significant drift events (p < {significance})")
    return events


def run_drift_detection_job(session: Session, min_mentions: int = 10,
                             significance: float = 0.05) -> int:
    """Recompute all drift events and write them to entity_drift_events.

    Returns the number of events written.
    """
    events = _compute_events(session, min_mentions, significance)

    session.execute(text("DELETE FROM entity_drift_events"))
    if events:
        session.execute(text("""
            INSERT INTO entity_drift_events
                (entity_id, source_id, dimension, week_start, statistic, p_value,
                 mean_before, mean_after)
            VALUES
                (:entity_id, :source_id, :dimension, :week_start, :statistic, :p_value,
                 :mean_before, :mean_after)
        """), events)
    session.commit()
    logger.info(f"Wrote {len(events)} rows to entity_drift_events")
    return len(events)


def _print_summary_from_computed(session: Session, events: list, limit: int = 10):
    """Dry-run summary: top `limit` events by ascending p_value, using in-memory results
    (nothing was written)."""
    if not events:
        logger.info("No significant drift events found - nothing would be written.")
        return

    entity_ids = {e["entity_id"] for e in events}
    source_ids = {e["source_id"] for e in events if e["source_id"] is not None}
    entity_names = dict(session.execute(text(
        "SELECT id, name FROM entities WHERE id = ANY(:ids)"
    ), {"ids": list(entity_ids)}).fetchall())
    source_names = dict(session.execute(text(
        "SELECT id, name FROM news_sources WHERE id = ANY(:ids)"
    ), {"ids": list(source_ids)}).fetchall()) if source_ids else {}

    ranked = sorted(events, key=lambda e: e["p_value"])[:limit]
    _log_table(ranked, entity_names, source_names)


def _print_summary_from_db(session: Session, limit: int = 10):
    """Real-run summary: top `limit` rows actually persisted in entity_drift_events."""
    rows = session.execute(text("""
        SELECT ede.entity_id, e.name AS entity_name, ede.source_id, ns.name AS source_name,
               ede.dimension, ede.week_start, ede.statistic, ede.p_value,
               ede.mean_before, ede.mean_after
        FROM entity_drift_events ede
        JOIN entities e ON e.id = ede.entity_id
        LEFT JOIN news_sources ns ON ns.id = ede.source_id
        ORDER BY ede.p_value ASC
        LIMIT :limit
    """), {"limit": limit}).fetchall()

    if not rows:
        logger.info("No rows in entity_drift_events.")
        return

    logger.info(f"\n=== Top {len(rows)} drift events by significance (as written) ===")
    for r in rows:
        scope = f"source={r.source_name}" if r.source_name else "GLOBAL"
        logger.info(
            f"  entity={r.entity_name!r:30s} {scope:30s} dim={r.dimension:5s} "
            f"week={r.week_start}  {r.mean_before:+.3f} -> {r.mean_after:+.3f}  "
            f"p={r.p_value:.5f}  K={r.statistic:.1f}"
        )


def _log_table(ranked, entity_names, source_names):
    logger.info(f"\n=== Top {len(ranked)} drift events by significance (dry run) ===")
    for e in ranked:
        scope = f"source={source_names.get(e['source_id'], e['source_id'])}" \
            if e["source_id"] is not None else "GLOBAL"
        entity_name = entity_names.get(e["entity_id"], e["entity_id"])
        logger.info(
            f"  entity={entity_name!r:30s} {scope:30s} dim={e['dimension']:5s} "
            f"week={e['week_start']}  {e['mean_before']:+.3f} -> {e['mean_after']:+.3f}  "
            f"p={e['p_value']:.5f}  K={e['statistic']:.1f}"
        )


if __name__ == "__main__":
    import argparse
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    parser = argparse.ArgumentParser(description="Run entity drift detection (Phase 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute and print the summary without writing to the DB")
    parser.add_argument("--min-mentions", type=int, default=10)
    parser.add_argument("--significance", type=float, default=0.05)
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        if args.dry_run:
            logger.info("DRY RUN - no changes will be written")
            events = _compute_events(session, args.min_mentions, args.significance)
            _print_summary_from_computed(session, events)
        else:
            n = run_drift_detection_job(session, args.min_mentions, args.significance)
            logger.info(f"Wrote {n} events")
            _print_summary_from_db(session)
    finally:
        session.close()
