from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import Article, Source, ArticleEntity, EntityMention
from processors.openai_processor import analyze_article_with_openai

# Set up logging
logger = logging.getLogger(__name__)

"""
Article Endpoints Module

This module provides API endpoints for article analysis and retrieval. It serves as the interface
between the frontend (browser extension and dashboard) and the sentiment analysis system.

Key functionality:
- Article analysis using OpenAI-powered sentiment extraction
- Cached article retrieval to prevent redundant processing
- Entity and sentiment data formatting for frontend consumption

Dependencies:
- FastAPI for API routing and request handling
- SQLAlchemy for database interactions
- OpenAI processor for sentiment analysis
"""

router = APIRouter()

class ArticleRequest(BaseModel):
    """Request model for article analysis.
    
    Attributes:
        url: The canonical URL of the article
        title: The article headline/title
        text: The full text content of the article
        source: The publication name/source of the article
        publish_date: ISO format date string when article was published (optional)
        force_reanalysis: Flag to force re-analysis even if cached analysis exists (optional)
    """
    url: str
    title: str
    text: str
    source: str
    publish_date: Optional[str] = None
    force_reanalysis: Optional[bool] = False

class ArticleAnalysisResponse(BaseModel):
    """Response model for article analysis results.
    
    Attributes:
        id: Database ID of the article (if stored)
        url: The canonical URL of the article
        title: The article headline/title
        source: The publication name/source of the article
        source_name: Normalized source name from database (if available)
        publish_date: ISO format date string when article was published
        composite_score: Dictionary containing statistical metrics about the overall sentiment pattern
                        (includes percentile and p-value measurements)
        entities: List of entities detected in the article with their sentiment scores
                 Each entity includes: name, type, power_score, moral_score, and mentions
        newly_analyzed: Flag indicating if this is a fresh analysis or retrieved from cache
    """
    id: Optional[str] = None
    url: str
    title: str
    source: str
    source_name: Optional[str] = None
    publish_date: Optional[str] = None
    composite_score: dict
    entities: list
    newly_analyzed: bool = True

@router.post("/analyze/article", response_model=ArticleAnalysisResponse)
async def analyze_article(request: ArticleRequest, session: AsyncSession = Depends(get_session)):
    """
    Analyze an article for sentiment bias and entity extraction.
    
    This endpoint processes articles to identify entities (people, organizations, countries) 
    and analyzes how they are portrayed along power and moral dimensions. It implements
    a caching strategy to avoid redundant processing of the same article.
    
    The analysis follows these steps:
    1. Check if the article already exists in the database (by URL)
    2. If found and force_reanalysis=False, return the cached analysis
    3. Otherwise, send the article to OpenAI for processing
    4. Store the analysis results in the database for future requests
    5. Return the analysis with entity sentiment scores
    
    Args:
        request: ArticleRequest model containing article data
        session: Database session for querying and storing results
        
    Returns:
        ArticleAnalysisResponse with sentiment analysis results
        
    Raises:
        HTTPException: For database errors or analysis failures
    """
    try:
        # Check if article already exists in database by normalized URL
        existing_article = await session.query(Article).filter(Article.url == request.url).first()
        
        if existing_article and not request.force_reanalysis:
            logger.info(f"Article found in database: {request.url}")
            
            # Get the associated entities and mentions
            entities = await session.query(ArticleEntity).filter(
                ArticleEntity.article_id == existing_article.id
            ).all()
            
            # Format the response
            entity_data = []
            for entity in entities:
                # Get mentions for this entity
                mentions = await session.query(EntityMention).filter(
                    EntityMention.entity_id == entity.id
                ).all()
                
                mention_data = [
                    {"text": mention.text, "context": mention.context}
                    for mention in mentions
                ]
                
                entity_data.append({
                    "name": entity.entity_name,
                    "type": entity.entity_type,
                    "power_score": entity.power_score,
                    "moral_score": entity.moral_score,
                    "national_significance": entity.national_significance,
                    "global_significance": entity.global_significance,
                    "mentions": mention_data
                })
            
            # Get source name
            source_name = None
            if existing_article.source_id:
                source = await session.query(Source).filter(
                    Source.id == existing_article.source_id
                ).first()
                if source:
                    source_name = source.name
            
            # Return the existing analysis
            return ArticleAnalysisResponse(
                id=existing_article.id,
                url=existing_article.url,
                title=existing_article.title,
                source=existing_article.source_name or request.source,
                source_name=source_name,
                publish_date=existing_article.publish_date.isoformat() if existing_article.publish_date else None,
                composite_score={
                    "percentile": existing_article.composite_percentile,
                    "p_value": existing_article.composite_p_value
                },
                entities=entity_data,
                newly_analyzed=False  # Indicate this is from the database
            )
        
        # If we get here, either the article doesn't exist or we're forcing reanalysis
        logger.info(f"Performing new analysis for: {request.url}")
        
        # Call OpenAI to analyze the article
        analysis_result = await analyze_article_with_openai(
            url=request.url,
            title=request.title,
            content=request.text,
            source=request.source,
            publish_date=request.publish_date
        )
        
        # Store the analysis in the database (in a real implementation)
        # This would create/update Article, ArticleEntity, and EntityMention records
        
        # For now, we'll just return the analysis result directly
        return ArticleAnalysisResponse(
            url=request.url,
            title=request.title,
            source=request.source,
            publish_date=request.publish_date,
            composite_score=analysis_result.composite_score,
            entities=analysis_result.entities,
            newly_analyzed=True  # Indicate this is a fresh analysis
        )
        
    except SQLAlchemyError as e:
        logger.error(f"Database error during article analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error analyzing article: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing article: {str(e)}")