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
from sqlalchemy import bindparam, func, text
from pydantic import BaseModel

from server.deps import get_db as get_session  # per-request session, closed after each request
from server.deps import first_solid_week, resolve_entity_group
from database.models import Entity, EntityMention, NewsArticle, NewsSource
from analyzer.narrative_metrics import (
    contested_ranking, archetype, trajectory, salience_asymmetry,
    sentiment_histogram, js_divergence,
)
from analyzer.entity_resolution import SYMBOL_WATCHLIST
from clustering.source_similarity import (
    compute_source_map, compute_global_agenda, latest_week,
)

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


class ContestedSphere(BaseModel):
    country: str
    n: int
    # 8-bin probability histogram over the clipped -2..2 score range —
    # the paired sparkline the front line draws per row.
    hist: List[float]


class ContestedEntity(BaseModel):
    entity_name: str
    divergence: float
    # The two spheres whose histograms produced the divergence (it's a MAX
    # pairwise JSD — naming the pair is the row's whole story). sphere_a is
    # the friendlier reading (higher mean score).
    sphere_a: Optional[ContestedSphere] = None
    sphere_b: Optional[ContestedSphere] = None


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

    def worst_pair(name: str):
        """Re-find the argmax country pair behind the kernel's max-JSD number.

        A bare divergence tells the reader nothing about WHO disagrees — the
        row wants "USA vs Russia" and both histograms. Same bins and floor as
        the kernel, so the pair always reproduces the ranked divergence.
        """
        spheres = {c: s for c, s in sphere_scores.get(name, {}).items()
                   if len(s) >= MIN_MENTIONS_PER_SPHERE}
        if len(spheres) < 2:
            return None, None
        hists = {c: sentiment_histogram(s) for c, s in spheres.items()}
        countries = list(hists)
        best = None
        for i, ca in enumerate(countries):
            for cb in countries[i + 1:]:
                d = js_divergence(hists[ca], hists[cb])
                if best is None or d > best[0]:
                    best = (d, ca, cb)
        _, ca, cb = best
        # sphere_a = the friendlier reading, so rows read "a likes it, b doesn't".
        if sum(spheres[ca]) / len(spheres[ca]) < sum(spheres[cb]) / len(spheres[cb]):
            ca, cb = cb, ca
        mk = lambda c: ContestedSphere(country=c, n=len(spheres[c]),
                                       hist=[round(float(h), 4) for h in hists[c]])
        return mk(ca), mk(cb)

    entities = []
    for name, div in ranked[:limit]:
        sphere_a, sphere_b = worst_pair(name)
        entities.append(ContestedEntity(entity_name=name, divergence=round(div, 4),
                                        sphere_a=sphere_a, sphere_b=sphere_b))
    return ContestedRankingResponse(days=days, dimension=dimension,
                                    entities=entities)


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


class SourceScatterPoint(BaseModel):
    source_id: int
    source_name: str
    country: Optional[str]
    power_score: float
    moral_score: float
    mention_count: int


class SourceScatterWindow(BaseModel):
    start: Optional[str]
    end: Optional[str]
    sources: List[SourceScatterPoint]


class EntitySourceScatterResponse(BaseModel):
    entity_id: int
    entity_name: str
    weeks: int
    current: SourceScatterWindow
    previous: SourceScatterWindow


# Matches get_trending_entities' per-source floor AND the EntityInfoPlate copy
# ("fewer than 3 scored mentions") — change all three together or the UI lies.
MIN_SOURCE_SCATTER_MENTIONS = 3

@router.get("/narrative/entity/{entity_id}/source-scatter",
            response_model=EntitySourceScatterResponse)
async def get_entity_source_scatter(
    entity_id: int,
    weeks: int = Query(4, ge=0, le=26),
    session: Session = Depends(get_session),
):
    """Every source's reading of ONE entity: mention-weighted mean power/moral per
    source over the trailing `weeks`-week window (`current`), plus the adjacent
    window before it (`previous`) so the frontend can draw each paper's drift
    against its own month-ago position — the transpose of /similarity/pair
    (two sources x many entities -> many sources x one entity), on the same
    mv_source_entity_week cells (canonical entity ids, publish-date weeks).
    weeks=0 means all time: `current` spans every scored week and `previous`
    stays empty (no adjacent window to drift from) — the frontend's default
    averages-only view.
    """
    def window(start, end, points):
        return SourceScatterWindow(
            start=start.isoformat() if start else None,
            end=end.isoformat() if end else None,
            sources=points,
        )

    entity = session.query(Entity).filter(Entity.id == entity_id).first()
    week = latest_week(session) if entity else None
    if not entity or week is None:
        return EntitySourceScatterResponse(
            entity_id=entity_id, entity_name=entity.name if entity else "unknown",
            weeks=weeks, current=window(None, None, []), previous=window(None, None, []),
        )

    if weeks == 0:
        # All time: window from the entity's first SOLID week (deps.py::
        # first_solid_week — skips the junk-dated prefix that read "coverage
        # since 2017"). prev_first == cur_first keeps the query below valid and
        # puts every row in the is_current bucket (week_start >= cur_first is
        # always true).
        cur_first = first_solid_week(session, entity.canonical_id or entity.id) or week
        prev_first = cur_first
    else:
        cur_first = week - timedelta(weeks=weeks - 1)
        prev_first = cur_first - timedelta(weeks=weeks)
    rows = session.execute(text("""
        SELECT m.source_id, s.name AS source_name, s.country,
               (m.week_start >= :cur_first) AS is_current,
               SUM(m.mean_power * m.n) / SUM(m.n) AS power_score,
               SUM(m.mean_moral * m.n) / SUM(m.n) AS moral_score,
               SUM(m.n) AS mention_count
        FROM mv_source_entity_week m
        JOIN news_sources s ON s.id = m.source_id
        WHERE m.entity_id = :entity_id
          AND m.week_start BETWEEN :prev_first AND :week
        GROUP BY m.source_id, s.name, s.country, (m.week_start >= :cur_first)
        HAVING SUM(m.n) >= :min_mentions
        ORDER BY SUM(m.n) DESC
    """), {"entity_id": entity.canonical_id or entity.id, "week": week,
           "cur_first": cur_first, "prev_first": prev_first,
           "min_mentions": MIN_SOURCE_SCATTER_MENTIONS}).fetchall()

    buckets = {True: [], False: []}
    for r in rows:
        if r.power_score is None or r.moral_score is None:
            continue  # a week whose mentions all lacked one dimension's score
        buckets[r.is_current].append(SourceScatterPoint(
            source_id=r.source_id, source_name=r.source_name, country=r.country,
            power_score=round(float(r.power_score), 3),
            moral_score=round(float(r.moral_score), 3),
            mention_count=int(r.mention_count),
        ))
    return EntitySourceScatterResponse(
        entity_id=entity_id, entity_name=entity.name, weeks=weeks,
        current=window(cur_first, week + timedelta(days=6), buckets[True]),
        previous=(window(prev_first, cur_first - timedelta(days=1), buckets[False])
                  if weeks else window(None, None, [])),
    )


class ReceiptRow(BaseModel):
    title: Optional[str]
    url: str
    date: Optional[str]  # publish date (YYYY-MM-DD)
    power_score: Optional[float]
    moral_score: Optional[float]
    # Matched sentence from the article, present only for mentions ingested
    # before the 2026-08-14 schema change dropped quote extraction.
    sentence: Optional[str] = None


class EntityReceiptsResponse(BaseModel):
    entity_id: int
    entity_name: str
    days: int
    per_source: int
    sources: Dict[int, List[ReceiptRow]]


# A quote longer than this is a paragraph the model pasted, not a sentence —
# truncate so one receipt can't dominate the payload.
MAX_RECEIPT_SENTENCE = 300


def _first_quote(mentions_json) -> Optional[str]:
    """First non-empty matched sentence from a mention's quote array.

    Pre-2026-08-14 rows carry [{text, context}, ...]; later rows carry [].
    Some stored strings contain literal NUL escapes (they break ::jsonb casts
    and would trip Postgres if ever written back) — strip them here.
    """
    for m in mentions_json or []:
        quote = (m.get("text") or "") if isinstance(m, dict) else ""
        quote = quote.replace("\x00", "").strip()
        if quote:
            if len(quote) > MAX_RECEIPT_SENTENCE:
                quote = quote[:MAX_RECEIPT_SENTENCE - 1].rstrip() + "…"
            return quote
    return None


@router.get("/narrative/entity/{entity_id}/receipts",
            response_model=EntityReceiptsResponse)
async def get_entity_receipts(
    entity_id: int,
    days: int = Query(365, ge=7, le=730),
    per_source: int = Query(5, ge=1, le=20),
    session: Session = Depends(get_session),
):
    """The evidence behind the dots: each source's most recent scored mentions
    of ONE entity — headline, link, publish date, both scores, and the matched
    sentence when the ingestion-era schema captured one. Keyed by source_id so
    the frontend can open a receipts drawer for any dot (or flatten across
    sources for an unfiltered "recent examples" view). Raw entity_mentions,
    not mv_source_entity_week — receipts are rows, not aggregates — so the
    alias group must be resolved here (the MV pre-resolves, this table doesn't).
    Windowed on publish_date (not EntityMention.created_at: backfilled or
    re-analyzed articles would otherwise surface as "recent").
    """
    entity, group_ids = resolve_entity_group(session, entity_id)
    if not entity:
        return EntityReceiptsResponse(entity_id=entity_id, entity_name="unknown",
                                      days=days, per_source=per_source, sources={})
    start = most_recent_activity(session) - timedelta(days=days)

    # DISTINCT ON collapses alias rows: one article mentioning two spellings of
    # the same canonical entity is one receipt, not two.
    rows = session.execute(text("""
        SELECT source_id, title, url, publish_date, power_score, moral_score, mentions
        FROM (
            SELECT a.source_id, a.title, a.url, a.publish_date,
                   em.power_score, em.moral_score, em.mentions,
                   ROW_NUMBER() OVER (
                       PARTITION BY a.source_id
                       ORDER BY a.publish_date DESC, em.id DESC
                   ) AS rn
            FROM (
                SELECT DISTINCT ON (article_id)
                       article_id, id, power_score, moral_score, mentions
                FROM entity_mentions
                WHERE entity_id IN :group_ids
                ORDER BY article_id, id
            ) em
            JOIN news_articles a ON a.id = em.article_id
            WHERE a.publish_date >= :start
              AND a.source_id IS NOT NULL
              AND (em.power_score IS NOT NULL OR em.moral_score IS NOT NULL)
        ) ranked
        WHERE rn <= :per_source
        ORDER BY source_id, rn
    """).bindparams(bindparam("group_ids", expanding=True)),
        {"group_ids": group_ids, "start": start, "per_source": per_source},
    ).fetchall()

    sources: Dict[int, List[ReceiptRow]] = {}
    for r in rows:
        sources.setdefault(r.source_id, []).append(ReceiptRow(
            title=r.title,
            url=r.url,
            date=r.publish_date.date().isoformat() if r.publish_date else None,
            power_score=round(float(r.power_score), 3) if r.power_score is not None else None,
            moral_score=round(float(r.moral_score), 3) if r.moral_score is not None else None,
            sentence=_first_quote(r.mentions),
        ))
    return EntityReceiptsResponse(entity_id=entity.id, entity_name=entity.name,
                                  days=days, per_source=per_source, sources=sources)


class SymbolRow(BaseModel):
    name: str
    entity_id: Optional[int] = None
    mention_count: int = 0
    countries: int = 0
    mean_power: Optional[float] = None
    mean_moral: Optional[float] = None
    # Max pairwise JS divergence between countries' moral histograms — the
    # same contestation measure as "the front line". None until at least two
    # countries clear the per-sphere mention floor.
    divergence: Optional[float] = None


class SymbolsResponse(BaseModel):
    tracked_since: str
    days: int
    symbols: List[SymbolRow]


# The date the symbol watchlist went into the extraction prompt
# (analyzer/entity_resolution.py SYMBOL_WATCHLIST, SYMBOL_INJECTION env).
# Concept-mention volume before this date is incidental, not tracked.
SYMBOLS_TRACKED_SINCE = "2026-09-06"


@router.get("/narrative/symbols", response_model=SymbolsResponse)
async def get_symbols(
    days: int = Query(365, ge=7, le=730),
    session: Session = Depends(get_session),
):
    """The symbol watchlist, ranked by contestation: concept entities the press
    fights over ("The West", "Sovereignty", "Democracy"), each with its scored
    mention volume, country breadth, mean scores, and cross-country divergence.
    Every watchlist symbol is returned — including ones with no mentions yet —
    so the page can show what is tracked, not just what has data.
    """
    start = most_recent_activity(session) - timedelta(days=days)
    names = {n.lower(): n for n in SYMBOL_WATCHLIST}

    rows = session.execute(text("""
        SELECT lower(e_can.name) AS lname, e_can.id AS entity_id,
               s.country, em.power_score, em.moral_score
        FROM entity_mentions em
        JOIN entities e ON e.id = em.entity_id
        JOIN entities e_can ON e_can.id = COALESCE(e.canonical_id, e.id)
        JOIN news_articles a ON a.id = em.article_id
        JOIN news_sources s ON s.id = a.source_id
        WHERE lower(e_can.name) IN :names
          AND a.publish_date >= :start
    """).bindparams(bindparam("names", expanding=True)),
        {"names": list(names), "start": start}).fetchall()

    stats: Dict[str, Dict[str, Any]] = {}
    sphere_scores: Dict[str, Dict[str, List[float]]] = {}
    for r in rows:
        display = names[r.lname]
        st = stats.setdefault(display, {"entity_id": r.entity_id, "n": 0,
                                        "power": [], "moral": [],
                                        "countries": set()})
        st["n"] += 1
        if r.power_score is not None:
            st["power"].append(float(r.power_score))
        if r.moral_score is not None:
            st["moral"].append(float(r.moral_score))
        if r.country:
            st["countries"].add(r.country)
            if r.moral_score is not None:
                sphere_scores.setdefault(display, {}).setdefault(
                    r.country, []).append(float(r.moral_score))

    divergence = {name: round(div, 4) for name, div in
                  contested_ranking(sphere_scores,
                                    min_mentions=MIN_MENTIONS_PER_SPHERE)}

    symbols = []
    for display in SYMBOL_WATCHLIST:
        st = stats.get(display)
        mean = lambda v: round(sum(v) / len(v), 3) if v else None
        symbols.append(SymbolRow(
            name=display,
            entity_id=st["entity_id"] if st else None,
            mention_count=st["n"] if st else 0,
            countries=len(st["countries"]) if st else 0,
            mean_power=mean(st["power"]) if st else None,
            mean_moral=mean(st["moral"]) if st else None,
            divergence=divergence.get(display),
        ))
    symbols.sort(key=lambda s: (s.divergence is None, -(s.divergence or 0),
                                -s.mention_count))
    return SymbolsResponse(tracked_since=SYMBOLS_TRACKED_SINCE, days=days,
                           symbols=symbols)


class SourceMapPoint(BaseModel):
    source_id: int
    source_name: str
    country: Optional[str]
    x: float
    y: float


class AxisCorrelate(BaseModel):
    entity_id: int
    name: str
    r: float
    sources: int


class MapAxis(BaseModel):
    axis: int
    positive: List[AxisCorrelate]
    negative: List[AxisCorrelate]


class SourceMapResponse(BaseModel):
    window_start: Optional[str]
    window_end: Optional[str]
    dimension: str
    min_country_breadth: int
    stress: float
    sources: List[SourceMapPoint]
    # Post-hoc axis anatomy (property fitting): entities whose scores move
    # with position along each axis - descriptive correlates, not labels.
    axes: List[MapAxis] = []


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
