"""
Similarity Endpoints Module

This module provides API endpoints for retrieving similar articles and clustering visualizations
for the browser extension.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import logging
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import database utilities
from database.db import get_session
from database.models import NewsArticle, Entity, EntityMention, NewsSource
# Import clustering module
from clustering.similarity_api import SimilarityAPI

logger = logging.getLogger(__name__)
router = APIRouter()

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