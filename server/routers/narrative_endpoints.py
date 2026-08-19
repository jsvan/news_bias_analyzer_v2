"""
Narrative statistics endpoints - wires analyzer/narrative_metrics.py's kernels
(written, self-tested, previously zero callers - see docs/ROADMAP_IDEAS_2026.md §1-§6)
into real queries against the live database.

contested_ranking/archetype need raw per-mention score arrays (for histograms/quadrant
placement), so they query entity_mentions directly rather than the pre-aggregated
mv_source_entity_week (database/run_migration_015.py) - that view backs the
aggregate-shaped consumers (source map, global agenda, weekly similarity).

"Sphere" = country of the source, the same country-as-information-sphere proxy the rest
of the dashboard already uses (CountryEntityPage, get_country_top_entities).
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from pydantic import BaseModel

from server.deps import get_db as get_session  # per-request session, closed after each request
from database.models import Entity, EntityMention, NewsArticle, NewsSource
from analyzer.narrative_metrics import (
    contested_ranking, archetype, trajectory, salience_asymmetry,
)
from clustering.source_similarity import compute_source_map, compute_global_agenda

logger = logging.getLogger(__name__)
router = APIRouter()

MIN_MENTIONS_PER_SPHERE = 10  # matches contested_ranking's own default


def most_recent_activity(session: Session) -> datetime:
    """Anchor for "days ago" windows: the last real scrape, not wall-clock now().

    Same fix as database/entity_pruning.py's sample-based threshold - if the pipeline
    goes dormant, calendar time keeps passing but no new data can arrive, so a
    datetime.now()-anchored window would silently return nothing forever once the gap
    exceeds the window size, even though the requested window's worth of real data exists.
    """
    ts = session.query(func.max(NewsArticle.scraped_at)).scalar()
    return ts or datetime.now()


def get_sphere_scores(session: Session, days: int, dimension: str,
                       entity_limit: int = 500) -> Dict[str, Dict[str, List[float]]]:
    """Raw score arrays per (entity, country) for the contested_ranking kernel.

    Limits to the entity_limit most-mentioned entities in the window first - without this,
    building histograms for the full long tail of entities would be wasted work (most of
    them never clear MIN_MENTIONS_PER_SPHERE in more than one sphere anyway).
    """
    score_field = EntityMention.power_score if dimension == "power" else EntityMention.moral_score
    start_date = most_recent_activity(session) - timedelta(days=days)

    top_entity_ids = [
        row.entity_id for row in session.query(EntityMention.entity_id).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            EntityMention.created_at >= start_date, score_field.isnot(None)
        ).group_by(EntityMention.entity_id)
        .order_by(func.count(EntityMention.id).desc())
        .limit(entity_limit).all()
    ]
    if not top_entity_ids:
        return {}

    rows = session.query(
        Entity.name, NewsSource.country, score_field
    ).join(
        EntityMention, EntityMention.entity_id == Entity.id
    ).join(
        NewsArticle, EntityMention.article_id == NewsArticle.id
    ).join(
        NewsSource, NewsArticle.source_id == NewsSource.id
    ).filter(
        EntityMention.entity_id.in_(top_entity_ids),
        EntityMention.created_at >= start_date,
        score_field.isnot(None),
        NewsSource.country.isnot(None),
    ).all()

    sphere_scores: Dict[str, Dict[str, List[float]]] = {}
    for name, country, score in rows:
        sphere_scores.setdefault(name, {}).setdefault(country, []).append(float(score))
    return sphere_scores


class ContestedEntity(BaseModel):
    entity_name: str
    divergence: float


class ContestedRankingResponse(BaseModel):
    days: int
    dimension: str
    entities: List[ContestedEntity]


@router.get("/narrative/contested", response_model=ContestedRankingResponse)
async def get_contested_ranking(
    days: int = Query(30, ge=7, le=365),
    dimension: str = Query("moral", regex="^(power|moral)$"),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """The "front line": entities with the sharpest cross-country sentiment disagreement.

    Divergence = max pairwise Jensen-Shannon divergence between any two countries'
    sentiment histograms for that entity (analyzer/narrative_metrics.py::contested_ranking).
    """
    sphere_scores = get_sphere_scores(session, days, dimension)
    ranked = contested_ranking(sphere_scores, min_mentions=MIN_MENTIONS_PER_SPHERE)
    return ContestedRankingResponse(
        days=days,
        dimension=dimension,
        entities=[ContestedEntity(entity_name=name, divergence=round(div, 4))
                  for name, div in ranked[:limit]],
    )


class ArchetypePoint(BaseModel):
    window_index: int
    power: float
    moral: float


class ArchetypeResponse(BaseModel):
    entity_id: int
    entity_name: str
    current_archetype: str
    power: float
    moral: float
    trajectory: Optional[List[ArchetypePoint]] = None


@router.get("/narrative/archetype/{entity_id}", response_model=ArchetypeResponse)
async def get_entity_archetype(
    entity_id: int,
    weeks: int = Query(12, ge=3, le=52),
    country: Optional[str] = Query(None, description="restrict to sources from this country"),
    session: Session = Depends(get_session),
):
    """Hero/villain/victim/nuisance quadrant + weekly trajectory for one entity,
    aggregated globally across sources (analyzer/narrative_metrics.py::archetype/trajectory),
    or across one country's sources when `country` is given (the frontend overlays
    country paths against the global one on the archetype quadrant).
    """
    entity = session.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        return ArchetypeResponse(entity_id=entity_id, entity_name="unknown",
                                  current_archetype="neutral", power=0.0, moral=0.0)

    canonical_id = entity.canonical_id or entity.id
    cutoff = (most_recent_activity(session) - timedelta(weeks=weeks)).date()

    country_clause = ""
    params = {"entity_id": canonical_id, "cutoff": cutoff}
    if country:
        country_clause = ("AND source_id IN "
                          "(SELECT id FROM news_sources WHERE country = :country)")
        params["country"] = country

    rows = session.execute(text(f"""
        SELECT week_start, AVG(mean_power) AS power, AVG(mean_moral) AS moral
        FROM mv_source_entity_week
        WHERE entity_id = :entity_id AND week_start >= :cutoff {country_clause}
        GROUP BY week_start ORDER BY week_start
    """), params).fetchall()

    points = [(i, float(r.power), float(r.moral)) for i, r in enumerate(rows)
              if r.power is not None and r.moral is not None]
    path = trajectory([p for _, p, _ in points], [m for _, _, m in points])

    current_power, current_moral = (points[-1][1], points[-1][2]) if points else (0.0, 0.0)
    return ArchetypeResponse(
        entity_id=entity_id,
        entity_name=entity.name,
        current_archetype=archetype(current_power, current_moral),
        power=round(current_power, 3),
        moral=round(current_moral, 3),
        trajectory=[ArchetypePoint(window_index=i, power=round(p, 3), moral=round(m, 3))
                    for i, p, m in path] if path else None,
    )


class SourceMapPoint(BaseModel):
    source_id: int
    source_name: str
    country: Optional[str]
    x: float
    y: float


class SourceMapResponse(BaseModel):
    window_start: Optional[str]
    window_end: Optional[str]
    dimension: str
    min_country_breadth: int
    stress: float
    sources: List[SourceMapPoint]


@router.get("/narrative/source-map", response_model=SourceMapResponse)
async def get_source_map(
    weeks: int = Query(4, ge=2, le=52),
    dimension: str = Query("moral", regex="^(power|moral)$"),
    session: Session = Depends(get_session),
):
    """Empirical "beyond left-right" source map: weighted MDS on the pairwise-complete
    Pearson matrix (clustering/source_similarity.py::compute_source_map) - the
    constellations' own correlations drawn in 2D, restricted to the internationally
    shared agenda. A source is placed only by entities others also scored, so narrow
    or local coverage never distorts its position.
    """
    return SourceMapResponse(**compute_source_map(session, weeks=weeks,
                                                  dimension=dimension))


class AgendaEntity(BaseModel):
    entity_id: int
    name: str
    type: Optional[str]
    countries: int
    sources: int
    mentions: int
    mean_moral: float
    mean_power: float


class GlobalAgendaResponse(BaseModel):
    window_start: Optional[str]
    window_end: Optional[str]
    weeks: int
    total_entities: int
    international_entities: int
    entities: List[AgendaEntity]


@router.get("/narrative/global-agenda", response_model=GlobalAgendaResponse)
async def get_global_agenda(
    weeks: int = Query(4, ge=2, le=52),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    """The internationally shared agenda: entities ranked by how many countries' sources
    covered them in the window (clustering/source_similarity.py::compute_global_agenda).
    The global-topic layer the source map is built on; everything below the breadth
    floor is some country's local conversation.
    """
    return GlobalAgendaResponse(**compute_global_agenda(session, weeks=weeks,
                                                        limit=limit))


class SalienceEntry(BaseModel):
    entity_name: str
    salience_asymmetry: float
    mentions_a: int
    mentions_b: int


@router.get("/narrative/salience", response_model=List[SalienceEntry])
async def get_salience_asymmetry(
    country_a: str,
    country_b: str,
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Selection-bias view: same entity, wildly different coverage *volume* between two
    countries' spheres (analyzer/narrative_metrics.py::salience_asymmetry) - the loud/silent
    signal, distinct from sentiment divergence (get_contested_ranking).
    """
    start_date = most_recent_activity(session) - timedelta(days=days)

    def counts_by_entity(country: str) -> Dict[str, int]:
        rows = session.query(Entity.name, func.count(EntityMention.id)).join(
            EntityMention, EntityMention.entity_id == Entity.id
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).join(
            NewsSource, NewsArticle.source_id == NewsSource.id
        ).filter(
            NewsSource.country == country, EntityMention.created_at >= start_date,
        ).group_by(Entity.name).all()
        return {name: n for name, n in rows}

    counts_a, counts_b = counts_by_entity(country_a), counts_by_entity(country_b)
    total_a, total_b = sum(counts_a.values()), sum(counts_b.values())
    if not total_a or not total_b:
        return []

    entries = []
    for name in set(counts_a) | set(counts_b):
        ca, cb = counts_a.get(name, 0), counts_b.get(name, 0)
        if ca + cb < MIN_MENTIONS_PER_SPHERE:
            continue
        entries.append(SalienceEntry(
            entity_name=name,
            salience_asymmetry=round(salience_asymmetry(ca, cb, total_a, total_b), 4),
            mentions_a=ca, mentions_b=cb,
        ))
    entries.sort(key=lambda e: abs(e.salience_asymmetry), reverse=True)
    return entries[:limit]
