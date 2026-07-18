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
from analyzer.source_similarity import pairwise_pearson, cluster_by_correlation

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
            week_start = self.session.execute(text(
                "SELECT MAX(week_start) FROM mv_source_entity_week"
            )).scalar()
            if week_start is None:
                logger.warning("mv_source_entity_week is empty - nothing to compute")
                return {"week_start": None, "sources": 0, "pairs_stored": 0, "clusters": 0}

        first_week = week_start - timedelta(weeks=weeks - 1)
        col = "mean_moral" if dimension == "moral" else "mean_power"
        # Mention-weighted mean over the window's weeks, canonical entities.
        rows = self.session.execute(text(f"""
            SELECT source_id, entity_id,
                   SUM({col} * n) / SUM(n) AS score
            FROM mv_source_entity_week
            WHERE week_start BETWEEN :first_week AND :week
            GROUP BY source_id, entity_id
            HAVING SUM(n) >= :min_cell
        """), {"first_week": first_week, "week": week_start,
               "min_cell": MIN_CELL_MENTIONS}).fetchall()

        source_ids = sorted({r.source_id for r in rows})
        entity_ids = sorted({r.entity_id for r in rows})
        logger.info(f"Week {week_start}: {len(source_ids)} sources x "
                    f"{len(entity_ids)} entities ({len(rows)} cells)")
        if len(source_ids) < 2:
            logger.warning("Fewer than 2 active sources - nothing to compare")
            return {"week_start": str(week_start), "sources": len(source_ids),
                    "pairs_stored": 0, "clusters": 0}

        s_index = {sid: i for i, sid in enumerate(source_ids)}
        e_index = {eid: i for i, eid in enumerate(entity_ids)}
        matrix = np.full((len(source_ids), len(entity_ids)), np.nan)
        for r in rows:
            matrix[s_index[r.source_id], e_index[r.entity_id]] = float(r.score)

        corr, common = pairwise_pearson(matrix, min_common=MIN_COMMON_ENTITIES)
        pairs_stored = self._store_matrix(source_ids, corr, common, first_week, week_start)

        labels = cluster_by_correlation(corr, threshold=CLUSTER_THRESHOLD)
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
