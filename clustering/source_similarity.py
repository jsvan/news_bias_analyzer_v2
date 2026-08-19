"""
Weekly source-similarity job: DB wiring around analyzer/source_similarity.py's
pure kernels (todo.txt items 1-5).

For the most recent week with data (or an explicit week), builds the
source x entity mean-sentiment matrix from mv_source_entity_week (canonical
entities via COALESCE(canonical_id, id), per-cell mention counts), computes the
pairwise-complete Pearson matrix with the min-10-common-entities floor, stores
it in source_similarity_matrix, clusters it, and stores assignments in
source_clusters.

Scheduled weekly by scheduler/job_scheduler.py (run_weekly_similarity). Run one
week by hand with:

    python -m clustering.source_similarity            # latest week with data
    python -m clustering.source_similarity 2025-08-18 # a specific week (Monday)
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from .base import BaseAnalyzer, log_timing
from analyzer.source_similarity import (
    pairwise_pearson, cluster_by_correlation, significance_weight, weighted_mds,
    dividing_entities,
)

logger = logging.getLogger(__name__)

# Pairs sharing fewer common entities than this get no correlation (the
# project's min_mentions=10 convention applied to common-entity counts).
MIN_COMMON_ENTITIES = 10
# A (source, entity) cell needs this many mentions across the window to count.
# 1, not higher: live weeks are dominated by single-mention cells (measured
# 2026-07-18: 6588 cells, only 869 with n>=2), and the pair-level
# MIN_COMMON_ENTITIES floor is the statistical gate that matters.
MIN_CELL_MENTIONS = 1
# Cluster members must correlate at least this much on average (average
# linkage cut at distance 1 - threshold).
CLUSTER_THRESHOLD = 0.5
# The map is built only on entities covered by sources from at least this many
# countries - the internationally shared agenda. Without it, three same-country
# papers qualify a local politician and same-country pairs are compared partly
# on local coverage no one else can see.
MIN_MAP_COUNTRY_BREADTH = 3
# A source needs at least this many known correlations to be placeable; with
# fewer, MDS would park it wherever the init happened to put it.
MIN_MAP_KNOWN_PAIRS = 3
# Dividing-lines entities must be covered by this many of the grouped sources:
# without the floor, a celebrity two sources scored at opposite extremes
# outranks the divides the whole press actually shares (measured 2026-08-19:
# Čeferin/Jared Leto/Bob Iger topped the raw F ranking).
MIN_DIVIDING_COVERAGE = 10


def latest_week(session: Session) -> Optional[date]:
    """Most recent mv_source_entity_week week (None if the view is empty)."""
    return session.execute(text(
        "SELECT MAX(week_start) FROM mv_source_entity_week"
    )).scalar()


def window_cells(session: Session, week_start: date, weeks: int, dimension: str):
    """Per-(source, entity) mention-weighted mean scores over a trailing window.

    The shared cell query behind the weekly matrix, the MDS map, and the global
    agenda: mv_source_entity_week (canonical entity ids) aggregated over the
    `weeks`-week window ending at `week_start`, one row per cell with its score
    and total mention count n.
    """
    first_week = week_start - timedelta(weeks=weeks - 1)
    col = "mean_moral" if dimension == "moral" else "mean_power"
    return session.execute(text(f"""
        SELECT source_id, entity_id,
               SUM({col} * n) / SUM(n) AS score,
               SUM(n) AS n
        FROM mv_source_entity_week
        WHERE week_start BETWEEN :first_week AND :week
        GROUP BY source_id, entity_id
        HAVING SUM(n) >= :min_cell
    """), {"first_week": first_week, "week": week_start,
           "min_cell": MIN_CELL_MENTIONS}).fetchall()


def _cell_matrix(rows):
    """(source_ids, entity_ids, matrix) from window_cells rows; NaN = no cell."""
    source_ids = sorted({r.source_id for r in rows})
    entity_ids = sorted({r.entity_id for r in rows})
    s_index = {sid: i for i, sid in enumerate(source_ids)}
    e_index = {eid: i for i, eid in enumerate(entity_ids)}
    matrix = np.full((len(source_ids), len(entity_ids)), np.nan)
    for r in rows:
        matrix[s_index[r.source_id], e_index[r.entity_id]] = float(r.score)
    return source_ids, entity_ids, matrix


def _window_dates(week_start: date, weeks: int):
    """ISO (start, end) date strings for a trailing window of ISO weeks."""
    first_week = week_start - timedelta(weeks=weeks - 1)
    return first_week.isoformat(), (week_start + timedelta(days=6)).isoformat()


class SourceSimilarityComputer(BaseAnalyzer):
    """Computes and stores the weekly pairwise source-similarity matrix."""

    @log_timing
    def compute_weekly_similarities(self,
                                    week_start: Optional[date] = None,
                                    dimension: str = "moral",
                                    weeks: int = 4) -> dict:
        """Compute, store, and cluster the similarity matrix for a trailing window.

        Runs weekly (the cadence), but correlates over a trailing `weeks`-week
        window ending at the target week - a single week of live scraping is
        too sparse for the 10-common-entities floor (measured 2026-07-18: one
        week kept 44 of 1275 possible pairs; four weeks keep an order of
        magnitude more).

        Args:
            week_start: Monday of the window's LAST week; defaults to the most
                recent week that has data (NOT the calendar week - the corpus
                can lag).
            dimension: "moral" (default, matches /narrative/source-map) or
                "power".
            weeks: trailing window length in ISO weeks.

        Returns a summary dict {week_start, sources, pairs_stored, clusters}.
        """
        self._refresh_matview()

        if week_start is None:
            week_start = latest_week(self.session)
            if week_start is None:
                logger.warning("mv_source_entity_week is empty - nothing to compute")
                return {"week_start": None, "sources": 0, "pairs_stored": 0, "clusters": 0}

        first_week = week_start - timedelta(weeks=weeks - 1)
        rows = window_cells(self.session, week_start, weeks, dimension)
        source_ids, entity_ids, matrix = _cell_matrix(rows)
        logger.info(f"Week {week_start}: {len(source_ids)} sources x "
                    f"{len(entity_ids)} entities ({len(rows)} cells)")
        if len(source_ids) < 2:
            logger.warning("Fewer than 2 active sources - nothing to compare")
            return {"week_start": str(week_start), "sources": len(source_ids),
                    "pairs_stored": 0, "clusters": 0}

        corr, common = pairwise_pearson(matrix, min_common=MIN_COMMON_ENTITIES)
        pairs_stored = self._store_matrix(source_ids, corr, common, first_week, week_start)

        # Cluster on significance-weighted r: a pair sharing 12 entities is a
        # noisier estimate than one sharing 300, and unweighted it can bridge
        # two clusters on a fluke. Stored/displayed r stays raw - it is always
        # shown with its shared-entity count.
        labels = cluster_by_correlation(corr * significance_weight(common),
                                        threshold=CLUSTER_THRESHOLD)
        n_clusters = self._store_clusters(source_ids, corr, labels, week_start, dimension)

        summary = {"week_start": str(week_start), "sources": len(source_ids),
                   "pairs_stored": pairs_stored, "clusters": n_clusters}
        logger.info(f"Weekly similarity complete: {summary}")
        return summary

    def _refresh_matview(self):
        """Refresh mv_source_entity_week so this week's mentions are included."""
        try:
            self.session.execute(text(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_source_entity_week"))
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.warning(f"Concurrent matview refresh failed ({e}); trying plain refresh")
            self.session.execute(text("REFRESH MATERIALIZED VIEW mv_source_entity_week"))
            self.session.commit()

    def _store_matrix(self, source_ids, corr, common, first_week, week_start) -> int:
        """Replace this window's rows in source_similarity_matrix. Returns rows stored."""
        window_start = datetime.combine(first_week, datetime.min.time())
        window_end = datetime.combine(week_start, datetime.min.time()) \
            + timedelta(days=6, hours=23, minutes=59, seconds=59)

        # Key the replacement on the window's END alone: a re-run with a
        # different trailing-window length must supersede, not coexist with,
        # earlier rows for the same target week.
        self.session.execute(text("""
            DELETE FROM source_similarity_matrix
            WHERE time_window_end = :end
        """), {"end": window_end})

        insert = text("""
            INSERT INTO source_similarity_matrix (
                source_id_1, source_id_2, similarity_score, common_entities,
                calculation_method, time_window_start, time_window_end, created_at
            ) VALUES (:s1, :s2, :score, :common, 'pearson_common', :start, :end, NOW())
        """)
        stored = 0
        n = len(source_ids)
        for i in range(n):
            for j in range(i + 1, n):
                if np.isnan(corr[i, j]):
                    continue
                self.session.execute(insert, {
                    "s1": source_ids[i], "s2": source_ids[j],
                    "score": float(corr[i, j]), "common": int(common[i, j]),
                    "start": window_start, "end": window_end,
                })
                stored += 1
        self.session.commit()
        logger.info(f"Stored {stored} similarity pairs for week {week_start}")
        return stored

    def _store_clusters(self, source_ids, corr, labels, week_start, dimension) -> int:
        """Replace this week's rows in source_clusters. Returns cluster count."""
        self.session.execute(text(
            "DELETE FROM source_clusters WHERE assigned_date = :d"
        ), {"d": week_start})

        insert = text("""
            INSERT INTO source_clusters (
                source_id, cluster_id, cluster_level, similarity_to_centroid,
                assigned_date, is_centroid, metadata
            ) VALUES (:sid, :cid, 1, :sim, :d, :centroid, :meta)
        """)
        c = np.asarray(corr, float)
        n_clusters = 0
        for label in sorted(set(labels)):
            members = [i for i, l in enumerate(labels) if l == label]
            n_clusters += 1
            # Mean correlation of each member to the rest of its cluster; the
            # best-connected member is the centroid. Singletons are their own
            # centroid with similarity 1.
            mean_corr = {}
            for i in members:
                others = [c[i, j] for j in members if j != i and not np.isnan(c[i, j])]
                mean_corr[i] = float(np.mean(others)) if others else 1.0
            centroid = max(members, key=lambda i: mean_corr[i])
            for i in members:
                self.session.execute(insert, {
                    "sid": source_ids[i],
                    "cid": f"{week_start}-C{label}",
                    "sim": round(mean_corr[i], 4),
                    "d": week_start,
                    "centroid": i == centroid,
                    "meta": json.dumps({"size": len(members), "dimension": dimension,
                                        "threshold": CLUSTER_THRESHOLD}),
                })
        self.session.commit()
        logger.info(f"Stored {n_clusters} clusters for week {week_start}")
        return n_clusters


def compute_source_map(session: Session, weeks: int = 4,
                       dimension: str = "moral") -> dict:
    """The source map: weighted MDS on the pairwise correlation matrix.

    One geometry with the constellations, not a second one: distances are
    1 - r from the same pairwise-complete Pearson kernel, over the same
    trailing window, so a source is placed only by how it scored entities
    others also scored. Two deliberate differences from the stored matrix:

    - Entities are restricted to the internationally shared agenda (covered by
      sources from >= MIN_MAP_COUNTRY_BREADTH countries), so same-country
      pairs aren't placed partly by local coverage no one else can see.
    - Pair weights are significance_weight(common): thin overlaps position a
      source weakly instead of equally.

    Sources with fewer than MIN_MAP_KNOWN_PAIRS known correlations are dropped
    (MDS would place them arbitrarily). Returns a JSON-ready dict; empty
    "sources" when there's too little overlapping coverage to place anyone.
    """
    empty = {"window_start": None, "window_end": None, "dimension": dimension,
             "min_country_breadth": MIN_MAP_COUNTRY_BREADTH, "stress": 0.0,
             "sources": []}
    week_start = latest_week(session)
    if week_start is None:
        return empty
    rows = window_cells(session, week_start, weeks, dimension)

    info = {r.id: r for r in session.execute(text(
        "SELECT id, name, country FROM news_sources"))}
    breadth: dict = {}
    for r in rows:
        country = info[r.source_id].country if r.source_id in info else None
        if country:
            breadth.setdefault(r.entity_id, set()).add(country)
    international = {eid for eid, cs in breadth.items()
                     if len(cs) >= MIN_MAP_COUNTRY_BREADTH}
    rows = [r for r in rows if r.entity_id in international]
    if not rows:
        return empty

    source_ids, entity_ids, matrix = _cell_matrix(rows)
    # Sources below the pair floor's own coverage can't clear it with anyone.
    keep = (~np.isnan(matrix)).sum(axis=1) >= MIN_COMMON_ENTITIES
    source_ids = [sid for sid, k in zip(source_ids, keep) if k]
    matrix = matrix[keep]
    if len(source_ids) < 3:
        return empty

    corr, common = pairwise_pearson(matrix, min_common=MIN_COMMON_ENTITIES)
    # Iteratively drop under-connected sources; each drop can orphan another.
    while True:
        known = np.isfinite(corr).sum(axis=1) - 1  # minus the diagonal
        keep = known >= MIN_MAP_KNOWN_PAIRS
        if keep.sum() < 3:
            return empty
        if keep.all():
            break
        source_ids = [sid for sid, k in zip(source_ids, keep) if k]
        corr, common = corr[np.ix_(keep, keep)], common[np.ix_(keep, keep)]

    coords, stress, _share = weighted_mds(1.0 - corr, significance_weight(common))
    window_start, window_end = _window_dates(week_start, weeks)
    logger.info(f"Source map: {len(source_ids)} sources on "
                f"{len(international)} international entities, stress {stress:.3f}")
    return {
        "window_start": window_start, "window_end": window_end,
        "dimension": dimension,
        "min_country_breadth": MIN_MAP_COUNTRY_BREADTH,
        "stress": round(float(stress), 4),
        "sources": [
            {"source_id": sid,
             "source_name": info[sid].name if sid in info else str(sid),
             "country": info[sid].country if sid in info else None,
             "x": round(float(coords[i, 0]), 4),
             "y": round(float(coords[i, 1]), 4)}
            for i, sid in enumerate(source_ids)
        ],
    }


def compute_global_agenda(session: Session, weeks: int = 4,
                          limit: int = 100) -> dict:
    """The internationally shared agenda: entities ranked by country breadth.

    Which entities does the world talk about together? Per entity over the
    trailing window: how many countries' sources covered it, how many papers,
    total mentions, and the mention-weighted mean scores. Ranked by breadth
    then volume - presidents and countries at the top, the local long tail at
    the bottom. The map's entity floor (MIN_MAP_COUNTRY_BREADTH) cuts this
    same list.
    """
    empty = {"window_start": None, "window_end": None, "weeks": weeks,
             "total_entities": 0, "international_entities": 0, "entities": []}
    week_start = latest_week(session)
    if week_start is None:
        return empty
    first_week = week_start - timedelta(weeks=weeks - 1)
    params = {"first_week": first_week, "week": week_start,
              "breadth": MIN_MAP_COUNTRY_BREADTH, "limit": limit}
    agg = """
        SELECT m.entity_id,
               COUNT(DISTINCT ns.country) AS countries,
               COUNT(DISTINCT m.source_id) AS sources,
               SUM(m.n) AS mentions,
               SUM(m.mean_moral * m.n) / SUM(m.n) AS mean_moral,
               SUM(m.mean_power * m.n) / SUM(m.n) AS mean_power
        FROM mv_source_entity_week m
        JOIN news_sources ns ON ns.id = m.source_id AND ns.country IS NOT NULL
        WHERE m.week_start BETWEEN :first_week AND :week
        GROUP BY m.entity_id
    """
    totals = session.execute(text(f"""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE countries >= :breadth) AS international
        FROM ({agg}) a
    """), params).one()
    rows = session.execute(text(f"""
        SELECT a.*, e.name, e.entity_type AS type
        FROM ({agg}) a JOIN entities e ON e.id = a.entity_id
        ORDER BY a.countries DESC, a.mentions DESC
        LIMIT :limit
    """), params).fetchall()

    window_start, window_end = _window_dates(week_start, weeks)
    return {
        "window_start": window_start, "window_end": window_end, "weeks": weeks,
        "total_entities": int(totals.total),
        "international_entities": int(totals.international),
        "entities": [
            {"entity_id": r.entity_id, "name": r.name, "type": r.type,
             "countries": int(r.countries), "sources": int(r.sources),
             "mentions": int(r.mentions),
             "mean_moral": round(float(r.mean_moral), 4),
             "mean_power": round(float(r.mean_power), 4)}
            for r in rows
        ],
    }


def compute_dividing_lines(session: Session, weeks: int = 4,
                           dimension: str = "moral", max_groups: int = 6,
                           limit: int = 20) -> dict:
    """What the constellations disagree about: per-group mean scores for the
    entities that best separate the top clusters (one-way F ranking,
    analyzer/source_similarity.py::dividing_entities).

    Groups are the latest stored clusters with >= 2 members, largest first,
    capped at max_groups - numbered to match the constellations panel, which
    orders the same way. Each returned entity carries per-group means and
    source counts aligned to the groups array (null / 0 where a group lacks
    the 2-source support floor).
    """
    empty = {"window_start": None, "window_end": None, "dimension": dimension,
             "groups": [], "entities": []}
    week_start = latest_week(session)
    if week_start is None:
        return empty
    rows = window_cells(session, week_start, weeks, dimension)
    if not rows:
        return empty
    source_ids, entity_ids, matrix = _cell_matrix(rows)

    assignments = session.execute(text("""
        SELECT source_id, cluster_id, is_centroid
        FROM source_clusters
        WHERE assigned_date = (SELECT MAX(assigned_date) FROM source_clusters)
    """)).fetchall()
    members: dict = {}
    centroid_of: dict = {}
    matrix_sources = set(source_ids)
    for a in assignments:
        if a.source_id in matrix_sources:
            members.setdefault(a.cluster_id, []).append(a.source_id)
            if a.is_centroid:
                centroid_of[a.cluster_id] = a.source_id
    top = sorted(((cid, srcs) for cid, srcs in members.items() if len(srcs) >= 2),
                 key=lambda kv: (-len(kv[1]), kv[0]))[:max_groups]
    if len(top) < 2:
        return empty

    group_of = {sid: gi for gi, (_cid, srcs) in enumerate(top) for sid in srcs}
    labels = [group_of.get(sid, -1) for sid in source_ids]

    # Only entities the grouped press broadly covers can be dividing lines -
    # the panel is about what the blocs share and still read differently.
    labeled = np.array([l >= 0 for l in labels])
    coverage = (~np.isnan(matrix[labeled])).sum(axis=0)
    keep_cols = np.where(coverage >= MIN_DIVIDING_COVERAGE)[0]
    matrix = matrix[:, keep_cols]
    entity_ids = [entity_ids[c] for c in keep_cols]

    ranked = dividing_entities(matrix, labels)[:limit]

    names = dict(session.execute(text(
        "SELECT id, name FROM entities WHERE id = ANY(:ids)"
    ), {"ids": [entity_ids[col] for col, _f, _msb, _m, _n in ranked]}).fetchall()) if ranked else {}
    source_names = {r.id: r.name for r in session.execute(text(
        "SELECT id, name FROM news_sources WHERE id = ANY(:ids)"
    ), {"ids": [centroid_of.get(cid, srcs[0]) for cid, srcs in top]})}

    window_start, window_end = _window_dates(week_start, weeks)
    return {
        "window_start": window_start, "window_end": window_end,
        "dimension": dimension,
        "groups": [
            {"cluster_id": cid, "label": f"Group {gi + 1}", "size": len(srcs),
             "centroid": source_names.get(centroid_of.get(cid, srcs[0]), "")}
            for gi, (cid, srcs) in enumerate(top)
        ],
        "entities": [
            {"entity_id": entity_ids[col],
             "name": names.get(entity_ids[col], str(entity_ids[col])),
             "f": round(f, 2),
             "spread": round(msb, 3),
             "means": [round(m[gi], 3) if gi in m else None
                       for gi in range(len(top))],
             "support": [n.get(gi, 0) for gi in range(len(top))]}
            for col, f, msb, m, n in ranked
        ],
    }


def compute_source_vectors(session: Session, weeks: int = 4,
                           dimension: str = "moral") -> dict:
    """Compact per-source entity score vectors for the static pair scatter.

    One file instead of n² pair files: every (source, entity) cell over the
    window for entities covered by >= 2 sources — exactly the cells that can
    ever appear in some pair's shared set (a single-source entity has no pair
    to be shared with). The client intersects two sources' vectors to draw
    any pair scatter offline. Scores rounded to 2dp (display precision).

    Shape: {window_start, window_end, dimension,
            entities: {id: name}, sources: {id: {entity_id: [score, n]}}}
    """
    empty = {"window_start": None, "window_end": None, "dimension": dimension,
             "entities": {}, "sources": {}}
    week_start = latest_week(session)
    if week_start is None:
        return empty
    rows = window_cells(session, week_start, weeks, dimension)

    cover: dict = {}
    for r in rows:
        cover[r.entity_id] = cover.get(r.entity_id, 0) + 1
    shared = {eid for eid, n in cover.items() if n >= 2}
    if not shared:
        return empty

    names = dict(session.execute(text(
        "SELECT id, name FROM entities WHERE id = ANY(:ids)"
    ), {"ids": list(shared)}).fetchall())

    vectors: dict = {}
    for r in rows:
        if r.entity_id in shared:
            vectors.setdefault(r.source_id, {})[r.entity_id] = [
                round(float(r.score), 2), int(r.n)]

    window_start, window_end = _window_dates(week_start, weeks)
    return {"window_start": window_start, "window_end": window_end,
            "dimension": dimension,
            "entities": {eid: names.get(eid, str(eid)) for eid in shared},
            "sources": vectors}


if __name__ == "__main__":
    import os
    import sys

    logging.basicConfig(level=logging.INFO)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.environ["DATABASE_URL"])
    session = sessionmaker(bind=engine)()
    week = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    try:
        print(SourceSimilarityComputer(session).compute_weekly_similarities(week))
    finally:
        session.close()
