"""
Entity-relatedness endpoints - serves analyzer/entity_embeddings.py's learned
co-occurrence and sentiment-profile vectors (database/run_migration_016.py::
entity_embeddings) as nearest-neighbor lookups.

Deliberately not a hand-curated hierarchy: "related" here means "close in a vector fit
from co-occurrence counts or sentiment profiles across the corpus," not an asserted
taxonomy - see analyzer/entity_embeddings.py's module docstring for why co-occurrence and
sentiment-profile are kept as two separate vectors rather than blended into one.

Registered by the single app in server/extension_api.py (routes declare their full
/narrative/... paths, so no prefix).
"""

import logging
from typing import List

import numpy as np
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from server.deps import get_db as get_session  # per-request session, closed after each request
from database.models import Entity

logger = logging.getLogger(__name__)
router = APIRouter()


class RelatedEntity(BaseModel):
    entity_id: int
    entity_name: str
    similarity: float


class RelatedEntitiesResponse(BaseModel):
    entity_id: int
    entity_name: str
    vector: str
    neighbors: List[RelatedEntity]


def _cosine_similarities(target: np.ndarray, others: np.ndarray) -> np.ndarray:
    """Cosine similarity between one vector and a matrix of others, zero-vector-safe."""
    target_norm = np.linalg.norm(target)
    if target_norm == 0:
        return np.zeros(others.shape[0])
    other_norms = np.linalg.norm(others, axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        sims = (others @ target) / (other_norms * target_norm)
    return np.nan_to_num(sims, nan=-1.0)


@router.get("/narrative/related/{entity_id}", response_model=RelatedEntitiesResponse)
async def get_related_entities(
    entity_id: int,
    vector: str = Query("cooccurrence", regex="^(cooccurrence|sentiment)$"),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    """Nearest neighbors of one entity in an embedding fit weekly by
    analyzer/entity_embeddings.py::run_entity_embedding_job.

    vector="cooccurrence" answers "what does this get talked about alongside" (topical);
    vector="sentiment" answers "what gets talked about the same way, by the same sources,
    at the same times" (rhetorical/ideological). Kept as two separate lookups rather than
    one blended vector because they answer different questions.

    An entity below the job's min_mentions threshold, or one that existed before the job
    last ran, has no row in entity_embeddings - that's "not enough data yet," not an
    error, so this returns an empty neighbors list rather than a 404.
    """
    entity = session.query(Entity).filter(Entity.id == entity_id).first()
    resolved_id = (entity.canonical_id or entity.id) if entity else entity_id
    entity_name = entity.name if entity else str(entity_id)
    if entity and entity.canonical_id:
        canonical = session.query(Entity).filter(Entity.id == entity.canonical_id).first()
        if canonical:
            entity_name = canonical.name

    column = "cooccurrence_vec" if vector == "cooccurrence" else "sentiment_vec"

    target_row = session.execute(text(f"""
        SELECT {column} AS vec FROM entity_embeddings WHERE entity_id = :entity_id
    """), {"entity_id": resolved_id}).fetchone()

    if not target_row or target_row.vec is None:
        return RelatedEntitiesResponse(
            entity_id=resolved_id, entity_name=entity_name, vector=vector, neighbors=[],
        )

    target_vec = np.array(target_row.vec, dtype=float)

    all_rows = session.execute(text(f"""
        SELECT entity_id, {column} AS vec FROM entity_embeddings WHERE entity_id != :entity_id
    """), {"entity_id": resolved_id}).fetchall()

    if not all_rows:
        return RelatedEntitiesResponse(
            entity_id=resolved_id, entity_name=entity_name, vector=vector, neighbors=[],
        )

    other_ids = [r.entity_id for r in all_rows]
    other_vecs = np.array([r.vec for r in all_rows], dtype=float)
    sims = _cosine_similarities(target_vec, other_vecs)

    order = np.argsort(-sims)[:limit]
    top_ids = [other_ids[i] for i in order]
    names = {e.id: e.name for e in session.query(Entity).filter(Entity.id.in_(top_ids)).all()}

    neighbors = [
        RelatedEntity(
            entity_id=other_ids[i],
            entity_name=names.get(other_ids[i], str(other_ids[i])),
            similarity=round(float(sims[i]), 4),
        )
        for i in order
    ]
    return RelatedEntitiesResponse(
        entity_id=resolved_id, entity_name=entity_name, vector=vector, neighbors=neighbors,
    )
