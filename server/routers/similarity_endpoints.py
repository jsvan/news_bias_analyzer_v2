"""
Similarity Endpoints Module

This module provides API endpoints for retrieving similar articles and clustering visualizations
for the browser extension.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
import logging
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import database utilities
from server.deps import get_db as get_session  # per-request session, closed after each request
from database.models import NewsArticle, Entity, EntityMention, NewsSource
# Import clustering module
from clustering.similarity_api import SimilarityAPI

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Weekly similarity matrix (clustering/source_similarity.py's output) ---

class MatrixSource(BaseModel):
    source_id: int
    name: str
    country: Optional[str] = None
    cluster: Optional[str] = None
    is_centroid: bool = False


class MatrixPair(BaseModel):
    source_id_1: int
    source_id_2: int
    score: float
    common_entities: int


class SimilarityMatrixResponse(BaseModel):
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    sources: List[MatrixSource]
    pairs: List[MatrixPair]


class NeighborEntry(BaseModel):
    source_id: int
    name: str
    country: Optional[str] = None
    score: float
    common_entities: int


class SourceNeighborsResponse(BaseModel):
    source_id: int
    source_name: str
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    nearest: List[NeighborEntry]
    farthest: List[NeighborEntry]


@router.get("/matrix", response_model=SimilarityMatrixResponse)
async def get_similarity_matrix(session: Session = Depends(get_session)):
    """The latest stored source-similarity matrix plus cluster assignments.

    Pearson correlation of mean moral scores over common entities
    (analyzer/source_similarity.py kernels, computed weekly by
    clustering/source_similarity.py). Pairs below the 10-common-entities
    floor are absent - unknown, not zero. Sources close in correlation-space
    see the world alike; /narrative/source-map is these same correlations
    drawn in 2D (weighted MDS).
    """
    latest = session.execute(text(
        "SELECT MAX(time_window_end) FROM source_similarity_matrix"
    )).scalar()
    if latest is None:
        return SimilarityMatrixResponse(sources=[], pairs=[])

    pairs = session.execute(text("""
        SELECT source_id_1, source_id_2, similarity_score, common_entities,
               time_window_start
        FROM source_similarity_matrix
        WHERE time_window_end = :end
    """), {"end": latest}).fetchall()
    window_start = pairs[0].time_window_start if pairs else None

    source_ids = sorted({r.source_id_1 for r in pairs} | {r.source_id_2 for r in pairs})
    clusters = {r.source_id: r for r in session.execute(text("""
        SELECT source_id, cluster_id, is_centroid
        FROM source_clusters
        WHERE assigned_date = (SELECT MAX(assigned_date) FROM source_clusters)
    """)).fetchall()}
    names = {s.id: s for s in session.query(NewsSource).filter(NewsSource.id.in_(source_ids)).all()}

    return SimilarityMatrixResponse(
        window_start=window_start.date().isoformat() if window_start else None,
        window_end=latest.date().isoformat(),
        sources=[MatrixSource(
            source_id=sid,
            name=names[sid].name if sid in names else str(sid),
            country=names[sid].country if sid in names else None,
            cluster=clusters[sid].cluster_id if sid in clusters else None,
            is_centroid=bool(clusters[sid].is_centroid) if sid in clusters else False,
        ) for sid in source_ids],
        pairs=[MatrixPair(
            source_id_1=r.source_id_1, source_id_2=r.source_id_2,
            score=round(float(r.similarity_score), 4),
            common_entities=r.common_entities,
        ) for r in pairs],
    )


@router.get("/sources/{source_id}/neighbors", response_model=SourceNeighborsResponse)
async def get_source_neighbors(
    source_id: int,
    limit: int = Query(5, ge=1, le=20),
    session: Session = Depends(get_session)
):
    """A source's nearest and farthest neighbors in the latest similarity matrix."""
    source = session.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    latest = session.execute(text(
        "SELECT MAX(time_window_end) FROM source_similarity_matrix"
    )).scalar()
    if latest is None:
        return SourceNeighborsResponse(source_id=source_id, source_name=source.name,
                                       nearest=[], farthest=[])

    rows = session.execute(text("""
        SELECT CASE WHEN source_id_1 = :sid THEN source_id_2 ELSE source_id_1 END AS other_id,
               similarity_score, common_entities, time_window_start
        FROM source_similarity_matrix
        WHERE time_window_end = :end
          AND (source_id_1 = :sid OR source_id_2 = :sid)
        ORDER BY similarity_score DESC
    """), {"sid": source_id, "end": latest}).fetchall()

    other_ids = [r.other_id for r in rows]
    names = {s.id: s for s in session.query(NewsSource).filter(NewsSource.id.in_(other_ids)).all()}

    def entry(r):
        s = names.get(r.other_id)
        return NeighborEntry(source_id=r.other_id,
                             name=s.name if s else str(r.other_id),
                             country=s.country if s else None,
                             score=round(float(r.similarity_score), 4),
                             common_entities=r.common_entities)

    return SourceNeighborsResponse(
        source_id=source_id,
        source_name=source.name,
        window_start=rows[0].time_window_start.date().isoformat() if rows else None,
        window_end=latest.date().isoformat(),
        nearest=[entry(r) for r in rows[:limit]],
        farthest=[entry(r) for r in rows[-limit:]][::-1] if len(rows) > limit else [],
    )

@router.get("/articles/similar", response_model=List[Dict[str, Any]])
async def get_similar_articles(
    article_url: str,
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    max_results: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session)
):
    """
    Get articles similar to the specified article.
    
    This endpoint finds semantically similar articles based on content and entity similarity.
    
    Args:
        article_url: The URL of the article to find similar articles for
        threshold: Minimum similarity score (0-1) for inclusion in results
        max_results: Maximum number of similar articles to return
        
    Returns:
        List of similar articles with similarity scores
    """
    try:
        # Query for the source article
        source_article = session.query(NewsArticle).filter(
            NewsArticle.url == article_url
        ).first()
        
        if not source_article:
            raise HTTPException(
                status_code=404, 
                detail=f"Article not found in database: {article_url}. Article similarity requires the article to be analyzed first."
            )
        
        # TODO: Implement real article similarity algorithm
        # This would involve:
        # 1. Query for articles with similar entities or content
        # 2. Apply semantic similarity algorithms (cosine similarity on embeddings)
        # 3. Filter by threshold and limit results
        
        raise HTTPException(
            status_code=501, 
            detail="Article similarity feature not yet implemented. Real semantic similarity algorithm needed."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error in get_similar_articles: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/articles/cluster", response_model=Dict[str, Any])
async def get_article_clusters(
    article_url: str,
    cluster_count: int = Query(3, ge=1, le=10),
    session: Session = Depends(get_session)
):
    """
    Get clustering visualization data for an article and its similar articles.
    
    This endpoint provides data for visualizing the relationship between an article
    and other similar articles in content space.
    
    Args:
        article_url: The URL of the central article
        cluster_count: Number of clusters to form
        
    Returns:
        Dictionary with nodes and links for visualization
    """
    try:
        # Query for the source article to ensure it exists
        source_article = session.query(NewsArticle).filter(
            NewsArticle.url == article_url
        ).first()
        
        if not source_article:
            raise HTTPException(
                status_code=404, 
                detail=f"Article not found in database: {article_url}. Article clustering requires the article to be analyzed first."
            )
        
        # TODO: Implement real article clustering algorithm
        # This would involve:
        # 1. Get similar articles using semantic similarity
        # 2. Apply clustering algorithms (k-means, hierarchical clustering)
        # 3. Generate 2D coordinates using dimensionality reduction (t-SNE, UMAP)
        # 4. Create nodes and links for force-directed visualization
        
        raise HTTPException(
            status_code=501, 
            detail="Article clustering feature not yet implemented. Real clustering and dimensionality reduction algorithms needed."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error in get_article_clusters: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")




# NEW ENDPOINTS USING CLUSTERING MODULE

@router.get("/sources/{source_id}/similar")
async def get_similar_sources(
    source_id: int,
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session)
):
    """
    Get sources most similar to the specified source based on sentiment patterns.
    
    Returns sources with high Pearson correlation on common entities.
    """
    try:
        similarity_api = SimilarityAPI(session)
        similar_sources = similarity_api.get_source_similarities(source_id, limit)
        
        if not similar_sources:
            # Return empty list if no similarities computed yet
            return []
            
        return similar_sources
        
    except Exception as e:
        logger.error(f"Error getting similar sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get similar sources: {str(e)}")


@router.get("/sources/{source_id}/drift")
async def get_source_drift(
    source_id: int,
    weeks: int = Query(4, ge=1, le=12),
    session: Session = Depends(get_session)
):
    """
    Get sentiment drift analysis for a source over recent weeks.
    
    Shows how the source's coverage of entities has changed over time.
    """
    try:
        similarity_api = SimilarityAPI(session)
        drift_data = similarity_api.get_source_drift(source_id, weeks)
        
        return drift_data
        
    except Exception as e:
        logger.error(f"Error getting source drift: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get source drift: {str(e)}")


@router.get("/entities/volatile")
async def get_volatile_entities(
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session)
):
    """
    Get entities with highest volatility scores.
    
    These are the current "hot topics" where sources disagree most.
    """
    try:
        similarity_api = SimilarityAPI(session)
        volatile_entities = similarity_api.get_volatile_entities(limit)
        
        return volatile_entities
        
    except Exception as e:
        logger.error(f"Error getting volatile entities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get volatile entities: {str(e)}")


@router.get("/sources/clusters")
async def get_source_clusters(
    country: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Get hierarchical clustering data for news sources.
    
    Shows how sources group together based on similar coverage patterns.
    """
    try:
        similarity_api = SimilarityAPI(session)
        cluster_data = similarity_api.get_source_clusters(country)
        
        return cluster_data
        
    except Exception as e:
        logger.error(f"Error getting source clusters: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get source clusters: {str(e)}")


@router.get("/articles/{article_id}/source-comparison")
async def get_article_source_comparison(
    article_id: str,
    session: Session = Depends(get_session)
):
    """
    Get alternative source perspectives for entities in this article.
    
    Shows how similar sources cover the same entities differently.
    """
    try:
        similarity_api = SimilarityAPI(session)
        comparison_data = similarity_api.get_article_source_comparison(article_id)
        
        return comparison_data
        
    except Exception as e:
        logger.error(f"Error getting source comparison: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get source comparison: {str(e)}")


@router.get("/sources/by-name/{source_name}")
async def get_source_by_name(
    source_name: str,
    session: Session = Depends(get_session)
):
    """
    Get source ID and info by name (helper endpoint).
    """
    try:
        source = session.query(NewsSource).filter(
            NewsSource.name.ilike(f"%{source_name}%")
        ).first()
        
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
            
        return {
            "id": source.id,
            "name": source.name,
            "country": source.country,
            "base_url": source.base_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding source: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find source: {str(e)}")