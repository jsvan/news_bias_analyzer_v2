"""
Drift-detection endpoints (Phase 5 of the narrative-analysis roadmap) - surfaces
analyzer/drift_detection.py's distinction between "everyone's sentiment moved
together" (an expected global event) and "this one source moved on its own,
unexplained by the global trend" (the actually-interesting editorial-stance signal).

GET /narrative/drift/{entity_id}  - LIVE computation for a single entity (cheap: one
    entity's weekly series, not the whole corpus) - always fresh, no dependency on the
    precomputed table.
GET /narrative/drift-feed         - reads the precomputed entity_drift_events table
    (database/run_migration_017.py, written by analyzer/drift_detection.py's weekly
    job) - cheap because it's just a query, not full-corpus recomputation.

Registered by the single app in server/extension_api.py (routes declare their full
/narrative/... paths, so no prefix).
"""

import logging
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from server.deps import get_db as get_session  # per-request session, closed after each request
from database.models import Entity, NewsSource
from analyzer.narrative_metrics import pettitt_test, residual_series

logger = logging.getLogger(__name__)
router = APIRouter()

SIGNIFICANCE = 0.05


def _global_series(session: Session, entity_id: int, dim: str):
    """Unweighted per-week average across sources - same definition as
    analyzer/drift_detection.py::_global_series (kept independent, not imported, since
    this endpoint queries live rather than as part of the scheduled job's session)."""
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
    weeks for this entity (pettitt_test's own floor)."""
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


class DriftPoint(BaseModel):
    source_id: Optional[int]
    source_name: Optional[str]  # None for the global row
    week_start: str  # ISO date
    statistic: float
    p_value: float
    mean_before: float
    mean_after: float


class EntityDriftResponse(BaseModel):
    entity_id: int
    entity_name: str
    dimension: str
    global_shift: Optional[DriftPoint]
    source_shifts: List[DriftPoint]  # only significant (p < 0.05), sorted by p_value asc


@router.get("/narrative/drift/{entity_id}", response_model=EntityDriftResponse)
async def get_entity_drift(
    entity_id: int,
    dimension: str = Query("moral", regex="^(power|moral)$"),
    session: Session = Depends(get_session),
):
    """Live changepoint detection for one entity: is there a global shift, and which
    sources (if any) shifted on their own beyond what the global trend explains?
    """
    entity = session.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    canonical_id = entity.canonical_id or entity.id

    weeks, global_values = _global_series(session, canonical_id, dimension)

    global_shift = None
    if len(global_values) >= 8:
        g_result = pettitt_test(global_values)
        if g_result is not None and g_result["p_value"] < SIGNIFICANCE:
            after_idx = g_result["changepoint_index"] + 1
            if after_idx < len(weeks):
                global_shift = DriftPoint(
                    source_id=None,
                    source_name=None,
                    week_start=weeks[after_idx].isoformat(),
                    statistic=round(g_result["statistic"], 4),
                    p_value=round(g_result["p_value"], 6),
                    mean_before=round(g_result["mean_before"], 4),
                    mean_after=round(g_result["mean_after"], 4),
                )

    source_shifts = []
    if len(global_values) >= 8:
        source_series = _source_series_by_source(session, canonical_id, dimension, weeks)
        if source_series:
            sources = session.query(NewsSource).filter(
                NewsSource.id.in_(source_series.keys())
            ).all()
            source_by_id = {s.id: s for s in sources}

            for source_id, series in source_series.items():
                resid = residual_series(series, global_values)
                s_result = pettitt_test(resid)
                if s_result is None or s_result["p_value"] >= SIGNIFICANCE:
                    continue
                after_idx = s_result["changepoint_index"] + 1
                if after_idx >= len(weeks):
                    continue
                source_shifts.append(DriftPoint(
                    source_id=source_id,
                    source_name=source_by_id[source_id].name if source_id in source_by_id else None,
                    week_start=weeks[after_idx].isoformat(),
                    statistic=round(s_result["statistic"], 4),
                    p_value=round(s_result["p_value"], 6),
                    mean_before=round(s_result["mean_before"], 4),
                    mean_after=round(s_result["mean_after"], 4),
                ))
    source_shifts.sort(key=lambda p: p.p_value)

    return EntityDriftResponse(
        entity_id=canonical_id,
        entity_name=entity.name,
        dimension=dimension,
        global_shift=global_shift,
        source_shifts=source_shifts,
    )


class DriftFeedEntry(BaseModel):
    entity_id: int
    entity_name: str
    source_id: Optional[int]
    source_name: Optional[str]
    dimension: str
    week_start: str
    statistic: float
    p_value: float
    mean_before: float
    mean_after: float


class DriftFeedResponse(BaseModel):
    dimension: str
    events: List[DriftFeedEntry]


@router.get("/narrative/drift-feed", response_model=DriftFeedResponse)
async def get_drift_feed(
    dimension: str = Query("moral", regex="^(power|moral)$"),
    limit: int = Query(20, ge=1, le=100),
    scope: str = Query("all", regex="^(all|global|source)$"),
    session: Session = Depends(get_session),
):
    """Precomputed drift feed (analyzer/drift_detection.py's weekly job output),
    ordered by significance. scope=global -> corpus-wide shifts only; scope=source ->
    source-specific (residual) shifts only; scope=all -> both.
    """
    scope_clause = ""
    if scope == "global":
        scope_clause = "AND ede.source_id IS NULL"
    elif scope == "source":
        scope_clause = "AND ede.source_id IS NOT NULL"

    rows = session.execute(text(f"""
        SELECT ede.entity_id, e.name AS entity_name, ede.source_id, ns.name AS source_name,
               ede.dimension, ede.week_start, ede.statistic, ede.p_value,
               ede.mean_before, ede.mean_after
        FROM entity_drift_events ede
        JOIN entities e ON e.id = ede.entity_id
        LEFT JOIN news_sources ns ON ns.id = ede.source_id
        WHERE ede.dimension = :dimension
        {scope_clause}
        ORDER BY ede.p_value ASC
        LIMIT :limit
    """), {"dimension": dimension, "limit": limit}).fetchall()

    events = [
        DriftFeedEntry(
            entity_id=r.entity_id,
            entity_name=r.entity_name,
            source_id=r.source_id,
            source_name=r.source_name,
            dimension=r.dimension,
            week_start=r.week_start.isoformat(),
            statistic=round(r.statistic, 4),
            p_value=round(r.p_value, 6),
            mean_before=round(r.mean_before, 4),
            mean_after=round(r.mean_after, 4),
        )
        for r in rows
    ]
    return DriftFeedResponse(dimension=dimension, events=events)
