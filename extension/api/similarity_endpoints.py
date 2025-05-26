"""
Similarity Endpoints Module

This module provides API endpoints for retrieving similar articles and clustering visualizations
for the browser extension.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import math
import random
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
        source_article = await session.query(NewsArticle).filter(
            NewsArticle.url == article_url
        ).first()
        
        if not source_article:
            # For testing, we'll return mock data
            # In production, you might want to return an error or empty list
            return generate_mock_similar_articles(article_url, threshold, max_results)
        
        # In a real implementation, you would:
        # 1. Query for articles with similar entities or content
        # 2. Apply semantic similarity algorithms
        # 3. Filter by threshold and limit
        
        # For now, return mock data
        return generate_mock_similar_articles(article_url, threshold, max_results)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find similar articles: {str(e)}")


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
        # In a real implementation, you would:
        # 1. Get similar articles
        # 2. Process them to create clustering visualization data
        # 3. Generate position coordinates
        
        # For now, return mock data
        return generate_mock_cluster_data(article_url, cluster_count)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate cluster data: {str(e)}")


# Helper function to generate mock similar articles
def generate_mock_similar_articles(article_url, threshold, max_count):
    """Generate mock similar articles for testing."""
    result = []
    
    # Source domains for mock data
    source_domains = [
        'nytimes.com',
        'washingtonpost.com',
        'cnn.com',
        'foxnews.com',
        'bbc.com',
        'reuters.com',
        'apnews.com',
        'nbcnews.com',
        'politico.com'
    ]
    
    # Extract a fake title from the URL
    url_parts = article_url.split('/')
    base_title = url_parts[-1].replace('-', ' ').replace('_', ' ').title() if len(url_parts) > 0 else "Article"
    
    # Current date for mock publish dates
    current_date = datetime.now()
    
    # Create mock articles with random similarity
    for i in range(max_count):
        # Random similarity score above threshold
        similarity = threshold + (random.random() * (1 - threshold))
        
        # Random date within past 30 days
        random_days_ago = random.randint(0, 30)
        date = current_date - timedelta(days=random_days_ago)
        
        # Select random source
        source = random.choice(source_domains)
        
        # Create a mock article
        result.append({
            "id": f"article_{i}",
            "url": f"https://{source}/article-{i}",
            "title": f"Similar article about {base_title}",
            "source": source,
            "publish_date": date.isoformat(),
            "similarity": similarity,
            "cluster": random.randint(0, 2)  # Random cluster for visualization
        })
    
    # Sort by similarity (highest first)
    return sorted(result, key=lambda x: x["similarity"], reverse=True)


# Helper function to generate mock cluster visualization data
def generate_mock_cluster_data(article_url, cluster_count):
    """Generate mock cluster visualization data for testing."""
    # Generate similar articles first
    similar_articles = generate_mock_similar_articles(article_url, 0.5, 20)
    
    # Create nodes array with the source article and similar articles
    nodes = [
        {
            "id": "source",
            "label": "Current Article",
            "url": article_url,
            "type": "source",
            "cluster": -1  # Special cluster for source
        }
    ]
    
    # Add similar articles as nodes
    for article in similar_articles:
        nodes.append({
            "id": article["id"],
            "label": article["title"],
            "url": article["url"],
            "source": article["source"],
            "publish_date": article["publish_date"],
            "type": "article",
            "cluster": article["cluster"]
        })
    
    # Calculate positions for visualization (simple 2D embedding)
    # In a real system, this would use t-SNE, UMAP, or another dimensionality reduction technique
    center_x, center_y = 175, 125  # Center of visualization
    
    # Source article at center
    nodes[0]["x"] = center_x
    nodes[0]["y"] = center_y
    
    # Position similar articles around the source based on similarity and cluster
    for i, node in enumerate(nodes[1:], 1):
        similarity = similar_articles[i-1]["similarity"]
        cluster = node["cluster"]
        
        # Calculate distance based on similarity (less similar = farther away)
        distance = 150 * (1 - similarity)
        
        # Calculate angle based on cluster (similar clusters are positioned closer together)
        base_angle = (2 * math.pi * cluster) / cluster_count
        angle_variation = random.random() * math.pi / 4  # Small random variation
        angle = base_angle + angle_variation
        
        # Set position
        node["x"] = center_x + distance * math.cos(angle)
        node["y"] = center_y + distance * math.sin(angle)
    
    # Create links between source and each similar article
    links = []
    for i, node in enumerate(nodes[1:], 1):
        similarity = similar_articles[i-1]["similarity"]
        links.append({
            "source": "source",
            "target": node["id"],
            "weight": similarity,
            "value": similarity
        })
    
    # Add some links between similar articles in the same cluster
    for i in range(1, len(nodes)):
        for j in range(i+1, len(nodes)):
            if (nodes[i]["cluster"] == nodes[j]["cluster"] and 
                random.random() < 0.3):  # 30% chance of link between same cluster
                links.append({
                    "source": nodes[i]["id"],
                    "target": nodes[j]["id"],
                    "weight": 0.5 * random.random(),
                    "value": 0.5 * random.random()
                })
    
    return {
        "nodes": nodes,
        "links": links
    }


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