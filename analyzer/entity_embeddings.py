"""
Phase 4: entity relatedness via learned embeddings (approved plan, entity-relatedness
milestone). Deliberately NOT a hand-curated hierarchy - "Trump relates to
Republicans/White House" is meant to emerge from two signals the data actually contains,
not be asserted here:

  1. co-occurrence: entities that get mentioned in the same articles a lot (PPMI-weighted,
     then compressed via TruncatedSVD) - a topical/associative signal.
  2. sentiment-profile: entities that get talked about the same way, by the same sources,
     in the same weeks (reuses analyzer/narrative_metrics.py::svd_source_map on an
     entity x (source, week) mean-moral matrix) - an ideological/rhetorical signal.

Both vectors are stored per entity (database/run_migration_016.py::entity_embeddings) so
a caller (extension/api/embeddings_endpoints.py) can ask "related by topic" or "related by
how they're talked about" separately - conflating them into one vector would blur both
signals into something neither captures cleanly.

Full rebuild every run (this codebase's existing convention for scheduled recomputation,
matching analyzer/hotelling_t2.py::update_weekly_statistics and mv_source_entity_week's
REFRESH pattern) - no attempt to diff/update individual rows.

Run weekly by the scheduler via run_entity_embedding_job(session). Standalone:
    python3 -m analyzer.entity_embeddings --dry-run   # sanity-check only, no DB write
    python3 -m analyzer.entity_embeddings              # real run, writes entity_embeddings
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from collections import defaultdict

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sqlalchemy import text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.narrative_metrics import svd_source_map

logger = logging.getLogger(__name__)


def _candidate_entities(session: Session, min_mentions: int) -> dict:
    """Entities with >= min_mentions total mentions, identity resolved through
    COALESCE(canonical_id, id) so a merged-away duplicate's mentions count toward its
    surviving canonical row rather than a dead id nobody will ever look up embeddings for.

    Returns {entity_id: mention_count}, canonical ids only.
    """
    rows = session.execute(text("""
        SELECT COALESCE(e.canonical_id, e.id) AS entity_id, COUNT(*) AS mention_count
        FROM entity_mentions em
        JOIN entities e ON em.entity_id = e.id
        GROUP BY COALESCE(e.canonical_id, e.id)
        HAVING COUNT(*) >= :min_mentions
    """), {"min_mentions": min_mentions}).fetchall()
    return {int(r.entity_id): int(r.mention_count) for r in rows}


def _cooccurrence_ppmi(session: Session, candidate_ids: list) -> np.ndarray:
    """Symmetric PPMI-weighted co-occurrence matrix, indexed in the same order as
    candidate_ids. The pairwise expansion (which articles' entity-sets turn into which
    (i, j) increments) happens in Python, not SQL, per the plan - it's a small in-memory
    blowup per article (num_entities choose 2), not worth a SQL self-join.
    """
    n = len(candidate_ids)
    index = {eid: i for i, eid in enumerate(candidate_ids)}

    rows = session.execute(text("""
        SELECT na.id AS article_id, COALESCE(e.canonical_id, e.id) AS entity_id
        FROM entity_mentions em
        JOIN news_articles na ON em.article_id = na.id
        JOIN entities e ON em.entity_id = e.id
        WHERE COALESCE(e.canonical_id, e.id) = ANY(:candidate_ids)
    """), {"candidate_ids": candidate_ids}).fetchall()

    article_entities = defaultdict(set)
    for r in rows:
        article_entities[r.article_id].add(int(r.entity_id))

    count = np.zeros((n, n), dtype=float)
    for entity_set in article_entities.values():
        ids = sorted(entity_set)
        for a in range(len(ids)):
            i = index[ids[a]]
            for b in range(a + 1, len(ids)):
                j = index[ids[b]]
                count[i, j] += 1
                count[j, i] += 1

    total = count.sum()
    if total == 0:
        return np.zeros((n, n), dtype=float)

    c_i = count.sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        expected = np.outer(c_i, c_i)
        pmi = np.log2((count * total) / expected)
    ppmi = np.where(count > 0, np.maximum(pmi, 0.0), 0.0)
    np.fill_diagonal(ppmi, 0.0)
    return ppmi


def _cooccurrence_embedding(ppmi: np.ndarray, n_components: int) -> np.ndarray:
    """TruncatedSVD of the PPMI matrix -> cooccurrence_vec per candidate entity.

    n_components must stay strictly below the matrix's feature count (n) for
    TruncatedSVD - guarded here rather than left to sklearn to raise on a small
    candidate set (few entities clearing min_mentions early in the pipeline's life,
    or on a thin test DB).
    """
    n = ppmi.shape[0]
    if n < 2:
        return np.zeros((n, 1))
    k = max(1, min(n_components, n - 1))
    svd = TruncatedSVD(n_components=k, random_state=0)
    return svd.fit_transform(ppmi)


def _sentiment_matrix(session: Session, candidate_ids: list) -> np.ndarray:
    """Entity x (source_id, week_start) mean-moral matrix, entities as rows (so
    svd_source_map's row_coords come out as one embedding per entity with no transpose
    needed). Columns are every distinct (source_id, week_start) pair seen for any
    candidate entity - most cells are NaN (a given source/week never covered a given
    entity), which svd_source_map handles by column-mean-filling after centering.
    """
    rows = session.execute(text("""
        SELECT source_id, entity_id, week_start, mean_moral
        FROM mv_source_entity_week
        WHERE entity_id = ANY(:candidate_ids) AND mean_moral IS NOT NULL
    """), {"candidate_ids": candidate_ids}).fetchall()

    columns = sorted({(r.source_id, r.week_start) for r in rows})
    col_index = {c: i for i, c in enumerate(columns)}
    row_index = {eid: i for i, eid in enumerate(candidate_ids)}

    matrix = np.full((len(candidate_ids), len(columns)), np.nan)
    for r in rows:
        matrix[row_index[int(r.entity_id)], col_index[(r.source_id, r.week_start)]] = float(r.mean_moral)
    return matrix


def _sentiment_embedding(matrix: np.ndarray, n_components: int):
    """svd_source_map(matrix, n_dims=k) with entities already as rows -> row_coords is
    directly the per-entity sentiment_vec (see module docstring). Guarded the same way
    as _cooccurrence_embedding: k can't exceed either matrix dimension.
    """
    rows, cols = matrix.shape
    if rows < 2 or cols < 1:
        return np.zeros((rows, 1)), np.array([0.0])
    k = max(1, min(n_components, rows, cols))
    row_coords, _col_loadings, evr = svd_source_map(matrix, n_dims=k)
    return row_coords, evr


def _write_embeddings(session: Session, candidate_ids: list, cooccurrence_vecs: np.ndarray,
                       sentiment_vecs: np.ndarray, mention_counts: dict) -> None:
    """Full rebuild: DELETE then bulk INSERT. See module docstring for why this codebase's
    convention is a full recompute rather than an upsert/diff."""
    session.execute(text("DELETE FROM entity_embeddings"))
    rows = [
        {
            "entity_id": eid,
            "cooccurrence_vec": cooccurrence_vecs[i].tolist(),
            "sentiment_vec": sentiment_vecs[i].tolist(),
            "mention_count": mention_counts[eid],
        }
        for i, eid in enumerate(candidate_ids)
    ]
    session.execute(text("""
        INSERT INTO entity_embeddings (entity_id, cooccurrence_vec, sentiment_vec, mention_count, updated_at)
        VALUES (:entity_id, :cooccurrence_vec, :sentiment_vec, :mention_count, NOW())
    """), rows)
    session.commit()
    logger.info(f"Wrote {len(rows)} entity_embeddings rows")


def run_entity_embedding_job(session: Session, min_mentions: int = 15, n_components: int = 24) -> int:
    """Weekly scheduled job: recompute co-occurrence + sentiment-profile embeddings for
    every entity with enough mentions to say anything about, and rewrite entity_embeddings.

    Returns the number of entities embedded (0 if there weren't enough candidates to
    build a meaningful matrix - not an error, just "not enough data yet").
    """
    candidates = _candidate_entities(session, min_mentions)
    candidate_ids = sorted(candidates.keys())
    if len(candidate_ids) < 2:
        logger.warning(
            f"Only {len(candidate_ids)} candidate entities (>= {min_mentions} mentions "
            "each) - not enough to embed relatedness, skipping."
        )
        return 0

    logger.info(f"Embedding {len(candidate_ids)} candidate entities (min_mentions={min_mentions})")

    ppmi = _cooccurrence_ppmi(session, candidate_ids)
    cooccurrence_vecs = _cooccurrence_embedding(ppmi, n_components)

    sentiment_matrix = _sentiment_matrix(session, candidate_ids)
    sentiment_vecs, sentiment_evr = _sentiment_embedding(sentiment_matrix, n_components)

    logger.info(f"Co-occurrence matrix: {ppmi.shape}, embedding dims: {cooccurrence_vecs.shape[1]}")
    logger.info(
        f"Sentiment matrix: {sentiment_matrix.shape}, embedding dims: {sentiment_vecs.shape[1]}, "
        f"explained variance ratio: {np.round(sentiment_evr, 4).tolist()}"
    )

    _write_embeddings(session, candidate_ids, cooccurrence_vecs, sentiment_vecs, candidates)
    return len(candidate_ids)


def _cosine_neighbors(vecs: np.ndarray, idx: int, top_k: int = 10):
    """Nearest neighbors of vecs[idx] by cosine similarity, excluding itself."""
    v = vecs[idx]
    vnorm = np.linalg.norm(v)
    if vnorm == 0:
        return []
    norms = np.linalg.norm(vecs, axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        sims = (vecs @ v) / (norms * vnorm)
    sims = np.nan_to_num(sims, nan=-1.0)
    order = [i for i in np.argsort(-sims) if i != idx][:top_k]
    return [(i, float(sims[i])) for i in order]


def main():
    parser = argparse.ArgumentParser(description="Weekly entity-relatedness embedding job")
    parser.add_argument("--dry-run", action="store_true",
                         help="Compute embeddings and print a nearest-neighbor sanity "
                              "check for the top-mentioned candidate entity, skip DB write")
    parser.add_argument("--min-mentions", type=int, default=15)
    parser.add_argument("--n-components", type=int, default=24)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    from dotenv import load_dotenv
    load_dotenv()
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Entity

    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        if args.dry_run:
            candidates = _candidate_entities(session, args.min_mentions)
            candidate_ids = sorted(candidates.keys())
            if len(candidate_ids) < 2:
                logger.warning("Not enough candidate entities for a dry run.")
                sys.exit(0)

            ppmi = _cooccurrence_ppmi(session, candidate_ids)
            cooccurrence_vecs = _cooccurrence_embedding(ppmi, args.n_components)
            sentiment_matrix = _sentiment_matrix(session, candidate_ids)
            sentiment_vecs, sentiment_evr = _sentiment_embedding(sentiment_matrix, args.n_components)

            logger.info(f"Candidates: {len(candidate_ids)}")
            logger.info(f"Co-occurrence matrix: {ppmi.shape}, embedding dims: {cooccurrence_vecs.shape[1]}")
            logger.info(f"Sentiment matrix: {sentiment_matrix.shape}, embedding dims: {sentiment_vecs.shape[1]}")
            logger.info(f"Sentiment SVD explained variance ratio: {np.round(sentiment_evr, 4).tolist()}")

            top_entity_id = max(candidates, key=candidates.get)
            top_idx = candidate_ids.index(top_entity_id)
            names = {e.id: e.name for e in
                     session.query(Entity).filter(Entity.id.in_(candidate_ids)).all()}

            neighbors = _cosine_neighbors(cooccurrence_vecs, top_idx, top_k=10)
            print(f"\nTop-mentioned candidate entity: "
                  f"{names.get(top_entity_id, top_entity_id)} "
                  f"(id={top_entity_id}, mentions={candidates[top_entity_id]})")
            print("Top 10 nearest neighbors (cosine similarity, cooccurrence_vec):")
            for i, sim in neighbors:
                nid = candidate_ids[i]
                print(f"  {names.get(nid, nid):40s}  sim={sim:.4f}  "
                      f"(id={nid}, mentions={candidates[nid]})")

            print("\n[dry run] skipping DB write.")
        else:
            n = run_entity_embedding_job(session, min_mentions=args.min_mentions,
                                          n_components=args.n_components)
            logger.info(f"Embedded {n} entities.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
