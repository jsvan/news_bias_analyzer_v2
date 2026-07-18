"""
Lead-lag and synchrony endpoints - wires the last two analyzer/narrative_metrics.py
kernels (lagged_correlation, synchrony_score) into live queries, following
drift_endpoints.py's structure (mv_source_entity_week, min-coverage floors,
honest nulls when the data is too thin).

GET /narrative/lead-lag   - which sources' sentiment *changes* lead or lag the
    global mean's changes (positive lag = source leads). Significance by
    permutation test inside the kernel.
GET /narrative/synchrony  - which clusters of sources move together: the
    "coordinated pivot" fingerprint. Uses the latest source_clusters assignment
    (clustering/source_similarity.py's weekly job); organic coverage scores low,
    a cluster pivoting in unison scores high.

Registered by the single app in server/extension_api.py (routes declare their
full /narrative/... paths, so no prefix).
"""

import logging
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from server.deps import get_db as get_session  # per-request session, closed after each request
from database.models import NewsSource
from analyzer.narrative_metrics import lagged_correlation, synchrony_score

logger = logging.getLogger(__name__)
router = APIRouter()

# A source needs this many observed weeks in the window for a lead-lag verdict
# (the kernel needs >= 5 overlapping *changes* at every tested lag).
MIN_WEEKS = 10


def _weekly_source_series(session: Session, dim: str, weeks_back: int):
    """(weeks, {source_id: aligned series}, global series) of mention-weighted
    weekly mean sentiment per source, over the trailing `weeks_back` weeks that
    actually have data."""
    col = f"mean_{dim}"
    rows = session.execute(text(f"""
        SELECT source_id, week_start,
               SUM({col} * n) / SUM(n) AS val
        FROM mv_source_entity_week
        WHERE week_start >= (
            SELECT MAX(week_start) FROM mv_source_entity_week
        ) - (:weeks_back || ' weeks')::interval
        GROUP BY source_id, week_start
    """), {"weeks_back": weeks_back}).fetchall()

    weeks = sorted({r.week_start for r in rows})
    week_index = {w: i for i, w in enumerate(weeks)}
    by_source = {}
    for r in rows:
        by_source.setdefault(r.source_id, np.full(len(weeks), np.nan))[
            week_index[r.week_start]] = float(r.val)

    if not weeks:
        return weeks, {}, np.array([])
    # Global series: unweighted mean across sources per week (each source one
    # vote, matching drift_endpoints' global-series definition).
    stacked = np.vstack(list(by_source.values())) if by_source else np.empty((0, len(weeks)))
    with np.errstate(invalid="ignore"):
        global_series = np.nanmean(stacked, axis=0)
    return weeks, by_source, global_series


class LeadLagEntry(BaseModel):
    source_id: int
    source_name: str
    country: Optional[str] = None
    best_lag_weeks: int  # positive = this source LEADS the global mean
    correlation: float
    p_value: float
    weeks_observed: int


class LeadLagResponse(BaseModel):
    dimension: str
    weeks_window: int
    entries: List[LeadLagEntry]  # sorted by p_value ascending; all reported, judge by p


@router.get("/narrative/lead-lag", response_model=LeadLagResponse)
async def get_lead_lag(
    dimension: str = Query("moral", regex="^(power|moral)$"),
    weeks: int = Query(52, ge=10, le=104),
    max_lag: int = Query(4, ge=1, le=8),
    session: Session = Depends(get_session),
):
    """Which sources' weekly sentiment changes lead or lag the global mean's.

    analyzer/narrative_metrics.py::lagged_correlation on each source's weekly
    mean-sentiment series vs the all-source global series. Positive
    best_lag_weeks = the source moves BEFORE the global mean. All computed
    entries are returned with their permutation p-values - filtering is the
    reader's judgment, not the endpoint's.
    """
    _, by_source, global_series = _weekly_source_series(session, dimension, weeks)

    entries = []
    names = {s.id: s for s in session.query(NewsSource).filter(
        NewsSource.id.in_(by_source.keys())).all()}
    for source_id, series in by_source.items():
        observed = int(np.sum(~np.isnan(series)))
        if observed < MIN_WEEKS:
            continue
        result = lagged_correlation(series, global_series, max_lag=max_lag)
        if result is None:
            continue
        best_lag, best_corr, p_value = result
        s = names.get(source_id)
        entries.append(LeadLagEntry(
            source_id=source_id,
            source_name=s.name if s else str(source_id),
            country=s.country if s else None,
            best_lag_weeks=int(best_lag),
            correlation=round(float(best_corr), 4),
            p_value=round(float(p_value), 4),
            weeks_observed=observed,
        ))
    entries.sort(key=lambda e: e.p_value)
    return LeadLagResponse(dimension=dimension, weeks_window=weeks, entries=entries)


class SynchronyCluster(BaseModel):
    cluster_id: str
    size: int
    synchrony: float  # |mean pairwise correlation of change series|, in [0, 1]
    measured_pairs: int  # pairs with >= 5 overlapping change-weeks behind the score
    members: List[str]


class SynchronyResponse(BaseModel):
    dimension: str
    weeks_window: int
    assigned_date: Optional[str] = None  # which weekly clustering this used
    baseline_all_sources: Optional[float] = None  # same score over every source
    clusters: List[SynchronyCluster]  # sorted by synchrony desc


@router.get("/narrative/synchrony", response_model=SynchronyResponse)
async def get_synchrony(
    dimension: str = Query("moral", regex="^(power|moral)$"),
    weeks: int = Query(52, ge=10, le=104),
    session: Session = Depends(get_session),
):
    """Coordination fingerprint per source cluster: do the members' weekly
    sentiment changes move in unison?

    analyzer/narrative_metrics.py::synchrony_score over each cluster from the
    latest weekly assignment (source_clusters). Compare each cluster to
    baseline_all_sources: a cluster only means something if it beats what all
    sources do together anyway (a global news event synchronizes everyone).
    """
    _, by_source, _ = _weekly_source_series(session, dimension, weeks)

    latest = session.execute(text(
        "SELECT MAX(assigned_date) FROM source_clusters")).scalar()
    cluster_rows = session.execute(text("""
        SELECT sc.source_id, sc.cluster_id, ns.name
        FROM source_clusters sc JOIN news_sources ns ON ns.id = sc.source_id
        WHERE sc.assigned_date = :d
    """), {"d": latest}).fetchall() if latest else []

    def change_matrix(source_ids):
        series = [by_source[sid] for sid in source_ids if sid in by_source]
        if len(series) < 2:
            return None
        return np.diff(np.vstack(series), axis=1)

    groups = {}
    for r in cluster_rows:
        groups.setdefault(r.cluster_id, []).append(r)

    def measurable_pairs(m):
        """Pairs the kernel will actually correlate (>= 5 overlapping changes)."""
        count = 0
        for i in range(m.shape[0]):
            for j in range(i + 1, m.shape[0]):
                if np.sum(~(np.isnan(m[i]) | np.isnan(m[j]))) >= 5:
                    count += 1
        return count

    clusters = []
    for cluster_id, members in groups.items():
        if len(members) < 2:
            continue
        m = change_matrix([r.source_id for r in members])
        if m is None:
            continue
        pairs = measurable_pairs(m)
        if pairs == 0:
            # Too little overlapping history: unknown, not "organic" - a bare
            # 0.0 here would read as a finding.
            continue
        clusters.append(SynchronyCluster(
            cluster_id=cluster_id,
            size=len(members),
            synchrony=round(synchrony_score(m), 4),
            measured_pairs=pairs,
            members=[r.name for r in members],
        ))
    clusters.sort(key=lambda c: -c.synchrony)

    all_matrix = change_matrix(list(by_source.keys()))
    baseline = round(synchrony_score(all_matrix), 4) if all_matrix is not None else None

    return SynchronyResponse(
        dimension=dimension,
        weeks_window=weeks,
        assigned_date=latest.isoformat() if latest else None,
        baseline_all_sources=baseline,
        clusters=clusters,
    )
