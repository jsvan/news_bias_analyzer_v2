"""
Extension API Server Module

This module provides the FastAPI server implementation for the browser extension API.
It includes all the endpoints needed by the extension to analyze articles and retrieve
sentiment analysis data.
"""

import os
import sys
import logging
import time
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, Body, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Float, text
import requests
from urllib.parse import urlparse
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("extension_api")

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import database models and utilities
from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention, NewsSource, Topic, Quote, QuoteTopic, PublicFigure

# Import any existing routers
try:
    from extension.api.article_endpoints import router as article_router
    has_article_router = True
except ImportError:
    # If the extension router is not available, create a dummy router
    from fastapi import APIRouter
    article_router = APIRouter()
    has_article_router = False

try:
    from extension.api.statistical_endpoints import router as stats_router
    has_stats_router = True
except ImportError:
    # If the stats router is not available, create a dummy router
    from fastapi import APIRouter
    stats_router = APIRouter()
    has_stats_router = False

try:
    from extension.api.similarity_endpoints import router as similarity_router
    has_similarity_router = True
except ImportError:
    # If the similarity router is not available, create a dummy router
    from fastapi import APIRouter
    similarity_router = APIRouter()
    has_similarity_router = False

# Initialize FastAPI app
app = FastAPI(
    title="News Bias Analyzer Extension API",
    description="API for the news bias analyzer browser extension",
    version="0.1.0"
)

# Database connection
database_url = os.getenv("DATABASE_URL", "postgresql://newsbias:newsbias@localhost:5432/news_bias")
db_manager = DatabaseManager(database_url)

# Dependency to get database session
def get_db():
    db = db_manager.get_session()
    try:
        yield db
    finally:
        db.close()

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "News Bias Analyzer Extension API"}

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint for monitoring and the browser extension."""
    db_connected = True
    try:
        # Quick test of database connection
        with db_manager.engine.connect() as conn:
            conn.execute("SELECT 1")
    except Exception:
        db_connected = False

    return {
        "status": "healthy",
        "database": "connected" if db_connected else "disconnected",
        "timestamp": datetime.utcnow().isoformat()
    }

# Entity endpoints
@app.get("/entities", response_model=List[Dict[str, Any]])
def get_entities(
    entity_type: Optional[str] = None,
    search: Optional[str] = Query(None, description="Search entities by name"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get list of entities, optionally filtered by type and search term, ordered by mention count."""
    # Join with EntityMention to get mention counts and order by them
    query = db.query(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.count(EntityMention.id).label("mention_count")
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id, isouter=True
    ).group_by(
        Entity.id, Entity.name, Entity.entity_type
    )
    
    if entity_type:
        query = query.filter(Entity.entity_type == entity_type)
    
    if search:
        # Case-insensitive search
        query = query.filter(func.lower(Entity.name).like(f"%{search.lower()}%"))
    
    # Order by mention count descending, then by name
    entities = query.order_by(
        func.count(EntityMention.id).desc(),
        Entity.name
    ).limit(limit).all()
    
    return [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type,
            "mention_count": entity.mention_count or 0
        }
        for entity in entities
    ]

@app.get("/entities/search", response_model=List[Dict[str, Any]])
def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search entities for autocomplete functionality."""
    # Search by name with mention count ordering
    query = db.query(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.count(EntityMention.id).label("mention_count")
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id, isouter=True
    ).filter(
        func.lower(Entity.name).like(f"%{q.lower()}%")
    ).group_by(
        Entity.id, Entity.name, Entity.entity_type
    ).order_by(
        func.count(EntityMention.id).desc(),
        Entity.name
    ).limit(limit)
    
    results = query.all()
    
    return [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type,
            "mention_count": entity.mention_count or 0
        }
        for entity in results
    ]

# Entity sentiment endpoint
@app.get("/entity/{entity_id}/sentiment", response_model=List[Dict[str, Any]])
def get_entity_sentiment(
    entity_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    source_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get sentiment data for a specific entity over time."""
    # Check if entity exists
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")
    
    # Build query for entity mentions
    query = db.query(
        EntityMention.power_score,
        EntityMention.moral_score,
        NewsArticle.publish_date,
        NewsSource.name.label("source_name")
    ).join(
        NewsArticle, EntityMention.article_id == NewsArticle.id
    ).join(
        NewsSource, NewsArticle.source_id == NewsSource.id
    ).filter(
        EntityMention.entity_id == entity_id
    )
    
    # Apply filters
    if start_date:
        query = query.filter(NewsArticle.publish_date >= start_date)
    
    if end_date:
        query = query.filter(NewsArticle.publish_date <= end_date)
    
    if source_id:
        query = query.filter(NewsArticle.source_id == source_id)
    
    # Order by date
    query = query.order_by(NewsArticle.publish_date)
    
    # Execute query
    results = query.all()
    
    return [
        {
            "power_score": result.power_score,
            "moral_score": result.moral_score,
            "date": result.publish_date,
            "source": result.source_name
        }
        for result in results
    ]

# News Sources endpoint
@app.get("/sources", response_model=List[Dict[str, Any]])
def get_sources(db: Session = Depends(get_db)):
    """Get all news sources."""
    sources = db.query(NewsSource).all()
    
    return [
        {
            "id": source.id,
            "name": source.name,
            "country": source.country,
            "language": source.language
        }
        for source in sources
    ]

# Trends endpoint
@app.get("/trends", response_model=Dict[str, Any])
def get_sentiment_trends(
    entity_ids: List[int] = Query(None),
    entity_types: List[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get sentiment trends over time for specified entities or entity types."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Base query
    query = db.query(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.avg(EntityMention.power_score).label("avg_power"),
        func.avg(EntityMention.moral_score).label("avg_moral"),
        func.date_trunc('day', NewsArticle.publish_date).label("date")
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id
    ).join(
        NewsArticle, EntityMention.article_id == NewsArticle.id
    ).filter(
        NewsArticle.publish_date.between(start_date, end_date)
    )
    
    # Apply filters
    if entity_ids:
        query = query.filter(Entity.id.in_(entity_ids))
    
    if entity_types:
        query = query.filter(Entity.entity_type.in_(entity_types))
    
    # Group by entity and date
    query = query.group_by(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.date_trunc('day', NewsArticle.publish_date)
    ).order_by(
        Entity.name,
        func.date_trunc('day', NewsArticle.publish_date)
    )
    
    # Execute query
    results = query.all()
    
    # Format response
    trends = {}
    for result in results:
        entity_id = result.id
        
        if entity_id not in trends:
            trends[entity_id] = {
                "id": entity_id,
                "name": result.name,
                "type": result.entity_type,
                "data": []
            }
        
        trends[entity_id]["data"].append({
            "date": result.date,
            "power_score": float(result.avg_power),
            "moral_score": float(result.avg_moral)
        })
    
    return {"trends": list(trends.values())}

# Statistical endpoints are now handled by the statistical_endpoints router

# Entity tracking endpoint is now handled by the statistical_endpoints router

# Define content extraction request/response models
class ExtractionRequest(BaseModel):
    url: str
    
class ExtractionResponse(BaseModel):
    url: str
    title: Optional[str] = None
    text: Optional[str] = None
    publish_date: Optional[str] = None
    source: Optional[str] = None
    
# Content extraction endpoint
@app.post("/extract", response_model=ExtractionResponse)
async def extract_content(request: ExtractionRequest):
    """
    Extract article content from a URL.
    This endpoint uses a simple extraction approach to get the title, text, and other metadata.
    """
    url = request.url
    logger.info(f"Extracting content from URL: {url}")
    
    try:
        # Try to extract a source name from the URL
        parsed_url = urlparse(url)
        hostname = parsed_url.netloc.lower()
        if hostname.startswith('www.'):
            hostname = hostname[4:]
            
        # Map common domains to source names
        source_mapping = {
            'nytimes.com': 'New York Times',
            'washingtonpost.com': 'Washington Post',
            'wsj.com': 'Wall Street Journal',
            'cnn.com': 'CNN',
            'foxnews.com': 'Fox News',
            'bbc.com': 'BBC',
            'bbc.co.uk': 'BBC',
            'reuters.com': 'Reuters',
            'bloomberg.com': 'Bloomberg',
            'economist.com': 'The Economist',
            'theguardian.com': 'The Guardian',
            'ft.com': 'Financial Times',
            'apnews.com': 'Associated Press',
            'npr.org': 'NPR',
            'cnbc.com': 'CNBC',
            'politico.com': 'Politico',
            'thehill.com': 'The Hill',
            'buzzfeednews.com': 'BuzzFeed News',
            'vox.com': 'Vox',
            'huffpost.com': 'HuffPost',
            'usatoday.com': 'USA Today',
            'latimes.com': 'Los Angeles Times',
            'chicagotribune.com': 'Chicago Tribune',
            'nypost.com': 'New York Post',
            'newsweek.com': 'Newsweek',
            'time.com': 'Time'
        }
        
        # Get source name or use domain name if not in mapping
        source_name = None
        for domain, name in source_mapping.items():
            if domain in hostname:
                source_name = name
                break
                
        if not source_name:
            # Use the domain name with first letter capitalized
            domain_parts = hostname.split('.')
            if len(domain_parts) >= 2:
                source_name = domain_parts[-2].capitalize()
            else:
                source_name = hostname.capitalize()
        
        # Use trafilatura for proper content extraction
        try:
            import trafilatura
            
            logger.info("Using trafilatura for content extraction")
            
            # Download the HTML
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                raise Exception("Failed to download content")
            
            # Extract article content
            extracted = trafilatura.extract(downloaded, include_formatting=False, include_comments=False,
                                          output_format='txt', favor_precision=True)
            
            if not extracted:
                raise Exception("Failed to extract article content")
            
            text = extracted
            
            # Also extract metadata
            metadata = trafilatura.extract_metadata(downloaded)
            title = metadata.title if metadata else None
            publish_date = metadata.date if metadata else None
            
            logger.info(f"Trafilatura extraction successful: {len(text)} characters")
            
        except (ImportError, Exception) as e:
            logger.warning(f"Trafilatura extraction failed ({type(e).__name__}: {str(e)}), falling back to BeautifulSoup")
            # Fall back to basic extraction
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Use BeautifulSoup for better extraction
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "aside", "footer", "header"]):
                script.decompose()
            
            # Try to find article content
            article = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
            if article:
                text = article.get_text()
            else:
                text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Extract title
            title_tag = soup.find('title')
            title = title_tag.string if title_tag else None
            
            # Extract publish date
            publish_date = None
            time_tag = soup.find('time', {'datetime': True})
            if time_tag:
                publish_date = time_tag.get('datetime')
            
        # Limit text length for response
        if len(text) > 15000:
            text = text[:15000] + '...'
                
        logger.info(f"Content extracted successfully from {url}")
        
        return ExtractionResponse(
            url=url,
            title=title,
            text=text,
            publish_date=publish_date,
            source=source_name
        )
        
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {str(e)}")
        # Return a response with empty content but still valid
        return ExtractionResponse(
            url=url,
            title=None,
            text=f"Error extracting content: {str(e)}",
            publish_date=None,
            source=source_name if 'source_name' in locals() else None
        )

# Article analysis request model
class ArticleAnalysisRequest(BaseModel):
    url: str
    title: str
    text: str
    source: str
    publish_date: Optional[str] = None
    force_reanalysis: Optional[bool] = False

# Endpoint to retrieve analysis by URL
@app.get("/analysis/by-url", response_model=Dict[str, Any])
async def get_analysis_by_url(
    url: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve existing analysis for an article by URL.
    
    This endpoint checks if an article has already been analyzed and returns the results.
    The extension uses this to auto-populate the analysis when a user visits a previously
    analyzed page.
    """
    try:
        # Convert URL to MD5 hash for lookup (same method used by scraper)
        import hashlib
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        
        # Look up the article in the database
        article = db.query(NewsArticle).filter(NewsArticle.id == url_hash).first()
        
        if not article or article.analysis_status != "completed":
            # Article not found or analysis not complete
            return {
                "url": url,
                "exists": False,
                "message": "Article not found or not yet analyzed"
            }
        
        # Get all entity mentions for this article
        entity_mentions = db.query(
            Entity, 
            EntityMention
        ).join(
            EntityMention, 
            Entity.id == EntityMention.entity_id
        ).filter(
            EntityMention.article_id == article.id
        ).all()
        
        if not entity_mentions:
            return {
                "url": url,
                "exists": True,
                "title": article.title,
                "source": article.source.name if article.source else "Unknown",
                "publish_date": article.publish_date,
                "entities": [],
                "message": "No entities found in analysis"
            }
        
        # Format entities for response
        formatted_entities = []
        unique_entities = {}
        
        for entity, mention in entity_mentions:
            entity_id = entity.id
            
            # Initialize entity data if not seen yet
            if entity_id not in unique_entities:
                unique_entities[entity_id] = {
                    "name": entity.name,
                    "type": entity.entity_type,
                    "power_score": mention.power_score,
                    "moral_score": mention.moral_score,
                    "mentions": []
                }
            
            # Add mention data if available
            if mention.mentions:
                unique_entities[entity_id]["mentions"].extend(mention.mentions)
        
        # Convert to list
        formatted_entities = list(unique_entities.values())
        
        # Calculate percentile based on Hotelling T² score
        composite_percentile = 50  # Default if no T² score
        if hasattr(article, 'hotelling_t2_score') and article.hotelling_t2_score is not None:
            # Get percentile rank for this article's T² score in past week
            percentile_query = text("""
                WITH weekly_articles AS (
                    SELECT id, hotelling_t2_score
                    FROM news_articles  
                    WHERE processed_at > NOW() - INTERVAL '7 days'
                      AND hotelling_t2_score IS NOT NULL
                )
                SELECT 
                    PERCENT_RANK() OVER (ORDER BY hotelling_t2_score) * 100 as percentile
                FROM weekly_articles
                WHERE id = :article_id
            """)
            
            result = db.execute(percentile_query, {"article_id": article.id}).fetchone()
            if result:
                composite_percentile = round(result.percentile, 1)
        
        # Create response
        response = {
            "url": url,
            "exists": True,
            "title": article.title,
            "source": article.source.name if article.source else "Unknown",
            "publish_date": article.publish_date,
            "entities": formatted_entities,
            "analysis_date": article.processed_at,
            "from_database": True,
            "composite_score": {
                "percentile": composite_percentile,
                "interpretation": f"More extreme than {composite_percentile:.0f}% of articles this week"
            }
        }
        
        return response
    
    except Exception as e:
        logger.error(f"Error retrieving analysis for URL {url}: {str(e)}")
        return {
            "url": url,
            "exists": False,
            "error": str(e),
            "message": "Error retrieving analysis"
        }

# Article analysis endpoint
@app.post("/analyze")
async def analyze_article(request: ArticleAnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyze article content for bias and sentiment using OpenAI.
    
    This endpoint calls the OpenAI API to perform entity extraction and sentiment analysis.
    It extracts named entities from the article content and analyzes how they are portrayed
    in terms of power and moral dimensions. Analysis results are saved to the database.
    """
    # Validate required fields
    if not request.url or not request.title or not request.text or not request.source:
        logger.error("Missing required fields in analyze request")
        missing_fields = []
        if not request.url: missing_fields.append("url")
        if not request.title: missing_fields.append("title")
        if not request.text: missing_fields.append("text")
        if not request.source: missing_fields.append("source")
        
        error_message = f"Missing required fields: {', '.join(missing_fields)}"
        logger.error(error_message)
        raise HTTPException(status_code=422, detail=error_message)
    logger.info(f"Analyzing article: {request.title} ({request.url})")
    logger.info(f"Force reanalysis: {request.force_reanalysis}")
    print(f"\n==== ANALYZING ARTICLE: {request.title} ====")
    print(f"URL: {request.url}")
    print(f"Source: {request.source}")
    print(f"Force reanalysis: {request.force_reanalysis}")
    print(f"Content length: {len(request.text)} characters")
    
    try:
        # Check if this URL already exists in the database
        import hashlib
        url_hash = hashlib.md5(request.url.encode('utf-8')).hexdigest()
        
        # Look up article in database
        article = db.query(NewsArticle).filter(NewsArticle.id == url_hash).first()
        
        # If article exists, check if we should re-analyze
        if article and article.analysis_status == "completed" and not request.force_reanalysis:
            # Get existing entity mentions
            logger.info(f"Found existing article in database, skipping analysis. Force reanalysis={request.force_reanalysis}")
            entity_mentions = db.query(
                Entity, 
                EntityMention
            ).join(
                EntityMention, 
                Entity.id == EntityMention.entity_id
            ).filter(
                EntityMention.article_id == article.id
            ).all()
            
            if entity_mentions:
                logger.info(f"Using existing analysis for {request.url} ({len(entity_mentions)} entity mentions)")
                
                # Format entities for response
                formatted_entities = []
                unique_entities = {}
                
                for entity, mention in entity_mentions:
                    entity_id = entity.id
                    
                    # Initialize entity data if not seen yet
                    if entity_id not in unique_entities:
                        unique_entities[entity_id] = {
                            "name": entity.name,
                            "type": entity.entity_type,
                            "power_score": float(mention.power_score) if mention.power_score else 0,
                            "moral_score": float(mention.moral_score) if mention.moral_score else 0,
                            "mentions": []
                        }
                    
                    # Add mention data if available
                    if mention.mentions:
                        unique_entities[entity_id]["mentions"].extend(mention.mentions)
                
                # Convert to list
                formatted_entities = list(unique_entities.values())
                
                # Calculate percentile based on Hotelling T² score
                composite_percentile = 50  # Default if no T² score
                if hasattr(article, 'hotelling_t2_score') and article.hotelling_t2_score is not None:
                    # Get percentile rank for this article's T² score in past week
                    percentile_query = text("""
                        WITH weekly_articles AS (
                            SELECT id, hotelling_t2_score
                            FROM news_articles  
                            WHERE processed_at > NOW() - INTERVAL '7 days'
                              AND hotelling_t2_score IS NOT NULL
                        )
                        SELECT 
                            PERCENT_RANK() OVER (ORDER BY hotelling_t2_score) * 100 as percentile
                        FROM weekly_articles
                        WHERE id = :article_id
                    """)
                    
                    result = db.execute(percentile_query, {"article_id": article.id}).fetchone()
                    if result:
                        composite_percentile = round(result.percentile, 1)
                
                # Create response
                api_response = {
                    "url": request.url,
                    "title": article.title,
                    "source": article.source.name if article.source else request.source,
                    "publish_date": article.publish_date,
                    "composite_score": {
                        "percentile": composite_percentile,
                        "interpretation": f"More extreme than {composite_percentile:.0f}% of articles this week"
                    },
                    "entities": formatted_entities,
                    "newly_analyzed": False,
                    "from_database": True
                }
                
                return api_response
        
        # Import the OpenAI integration
        from analyzer.openai_integration import SentimentAnalyzer
        
        print("Initializing OpenAI analyzer...")
        analyzer = SentimentAnalyzer()
        
        # Format article for analysis
        article_data = {
            "url": request.url,
            "title": request.title,
            "text": request.text,
            "source": request.source,
            "publish_date": request.publish_date
        }
        
        # Ensure we have a news source record
        source = None
        if request.source:
            # Look up source by name
            source = db.query(NewsSource).filter(func.lower(NewsSource.name) == func.lower(request.source)).first()
            
            # Create source if it doesn't exist
            if not source:
                source = NewsSource(
                    name=request.source,
                    base_url=urlparse(request.url).netloc,
                    country="Unknown",
                    language="en"
                )
                db.add(source)
                db.flush()  # Get the ID without committing
        
        # Create or update article record
        if not article:
            # Create new article record
            article = NewsArticle(
                id=url_hash,
                url=request.url,
                title=request.title,
                text=request.text,
                publish_date=request.publish_date or datetime.utcnow(),
                source_id=source.id if source else None,
                analysis_status="in_progress",
                last_analysis_attempt=datetime.utcnow()
            )
            db.add(article)
        else:
            # Update existing article
            article.title = request.title
            article.text = request.text
            article.publish_date = request.publish_date or article.publish_date or datetime.utcnow()
            article.source_id = source.id if source else article.source_id
            article.analysis_status = "in_progress"
            article.last_analysis_attempt = datetime.utcnow()
        
        db.flush()  # Make sure article has an ID
                
        # Call the OpenAI analyzer
        print("Calling OpenAI for analysis...")
        analysis_result = analyzer.analyze_article(article_data)
        
        # Update source country if LLM provided one
        llm_source_country = analysis_result.get('source_country')
        if llm_source_country and source and (source.country == "Unknown" or source.country is None):
            print(f"LLM determined source country: {llm_source_country}")
            source.country = llm_source_country
            logger.info(f"Updated source '{source.name}' country from Unknown to '{llm_source_country}'")
        
        # Extract entities from the analysis result
        entities = analysis_result.get('entities', [])
        print(f"OpenAI found {len(entities)} entities in the article")
        
        # Store entities and mentions in the database
        formatted_entities = []
        for entity_data in entities:
            entity_name = entity_data.get('entity', '')
            entity_type = entity_data.get('entity_type', '')
            
            if not entity_name:
                continue  # Skip entities with no name
            
            # Look up entity in database or create it
            entity = db.query(Entity).filter(
                func.lower(Entity.name) == func.lower(entity_name),
                Entity.entity_type == entity_type
            ).first()
            
            if not entity:
                entity = Entity(
                    name=entity_name,
                    entity_type=entity_type,
                    created_at=datetime.utcnow()
                )
                db.add(entity)
                db.flush()  # Get the ID without committing
            
            # Create entity mention
            mention = EntityMention(
                entity_id=entity.id,
                article_id=article.id,
                power_score=entity_data.get('power_score', 0),
                moral_score=entity_data.get('moral_score', 0),
                mentions=entity_data.get('mentions', []),
                created_at=article.publish_date or article.scraped_at
            )
            db.add(mention)
            
            # Format for response
            formatted_entity = {
                "name": entity_name,
                "type": entity_type,
                "power_score": entity_data.get('power_score', 0),
                "moral_score": entity_data.get('moral_score', 0),
                "national_significance": 0.3,  # Placeholder
                "global_significance": 0.2,    # Placeholder
                "mentions": entity_data.get('mentions', [])
            }
            formatted_entities.append(formatted_entity)
        
        # Update article status to completed
        article.analysis_status = "completed"
        article.processed_at = datetime.utcnow()
        
        # Commit all changes to database
        db.commit()
        
        # Calculate T² score for the new article
        # Note: This is a temporary calculation until the batch analyzer computes it
        composite_percentile = 50  # Default, will be computed by batch analyzer
        
        # Create response
        api_response = {
            "url": request.url,
            "title": request.title,
            "source": request.source,
            "publish_date": request.publish_date,
            "composite_score": {
                "percentile": composite_percentile,
                "interpretation": f"Analysis in progress - check back for extremeness score"
            },
            "entities": formatted_entities,
            "newly_analyzed": True,
            "saved_to_database": True
        }
        
        # Print the entities for debugging
        print("\nAnalysis response contains the following entities:")
        for entity in formatted_entities:
            print(f"  - {entity['name']} ({entity['type']})")
            print(f"    Power: {entity['power_score']}, Moral: {entity['moral_score']}")
            print(f"    Mentions: {len(entity.get('mentions', []))}")
        
        logger.info(f"Analysis completed and saved for {request.url}")
        return api_response
    
    except Exception as e:
        logger.error(f"Error analyzing article: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# Trending entities endpoint for dashboard
@app.get("/stats/trending_entities", response_model=List[Dict[str, Any]])
async def get_trending_entities(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get trending entities with their sentiment scores.
    These are entities that have been mentioned frequently in the recent past.
    """
    try:
        # Get date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Query for trending entities based on mention count
        trending_query = db.query(
            Entity.id,
            Entity.name,
            Entity.entity_type,
            func.count(EntityMention.id).label('mention_count'),
            func.avg(EntityMention.power_score).label('avg_power'),
            func.avg(EntityMention.moral_score).label('avg_moral')
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            NewsArticle.publish_date >= start_date
        ).group_by(
            Entity.id, Entity.name, Entity.entity_type
        ).order_by(
            func.count(EntityMention.id).desc()
        ).limit(limit).all()
        
        # Format the results
        result = []
        for entity in trending_query:
            # Calculate global percentile (simplified)
            # In a real implementation, this would involve more sophisticated statistical analysis
            global_percentile = 50  # Default to median
            
            # Get mentions count from all time for comparison
            all_time_count = db.query(func.count(EntityMention.id)).filter(
                EntityMention.entity_id == entity.id
            ).scalar() or 0
            
            # Add to results
            result.append({
                'entity': entity.name,
                'type': entity.entity_type,
                'power_score': float(entity.avg_power) if entity.avg_power else 0,
                'moral_score': float(entity.avg_moral) if entity.avg_moral else 0,
                'global_percentile': global_percentile,
                'mention_count': entity.mention_count,
                'all_time_mentions': all_time_count
            })
        
        return result
    except Exception as e:
        logger.error(f"Error fetching trending entities: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending entities: {str(e)}")

# Entity distribution endpoint for dashboard
@app.get("/stats/entity_distribution/{entity_id}", response_model=Dict[str, Any])
async def get_entity_distribution(
    entity_id: int,
    country: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Get sentiment distribution data for a specific entity."""
    try:
        # Check if entity exists
        entity = db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")
        
        # Get entity mentions for the last 90 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)
        
        # Base query for entity mentions
        query = db.query(
            EntityMention.power_score,
            EntityMention.moral_score,
            NewsSource.name.label("source_name"),
            NewsSource.country
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).join(
            NewsSource, NewsArticle.source_id == NewsSource.id
        ).filter(
            EntityMention.entity_id == entity_id,
            NewsArticle.publish_date >= start_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )
        
        # Apply filters
        if country:
            query = query.filter(NewsSource.country == country)
        if source_id:
            query = query.filter(NewsSource.id == source_id)
        
        # Execute query
        mentions = query.all()
        
        if not mentions:
            return {
                "entity": {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.entity_type
                },
                "distributions": {},
                "message": "No sentiment data found for this entity"
            }
        
        # Calculate statistics
        power_scores = [m.power_score for m in mentions]
        moral_scores = [m.moral_score for m in mentions]
        
        import numpy as np
        
        power_mean = np.mean(power_scores)
        power_std = np.std(power_scores)
        moral_mean = np.mean(moral_scores)
        moral_std = np.std(moral_scores)
        
        # Generate PDF data points for visualization (simple histogram approach)
        try:
            from scipy import stats
            power_range = np.linspace(min(power_scores) - power_std, max(power_scores) + power_std, 100)
            moral_range = np.linspace(min(moral_scores) - moral_std, max(moral_scores) + moral_std, 100)
            power_pdf = stats.norm.pdf(power_range, power_mean, power_std)
            moral_pdf = stats.norm.pdf(moral_range, moral_mean, moral_std)
        except ImportError:
            # Fallback to simple histogram if scipy not available
            power_range = np.linspace(min(power_scores), max(power_scores), 50)
            moral_range = np.linspace(min(moral_scores), max(moral_scores), 50)
            power_pdf = np.histogram(power_scores, bins=50, density=True)[0]
            moral_pdf = np.histogram(moral_scores, bins=50, density=True)[0]
        
        # Format response
        result = {
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type
            },
            "distributions": {
                "global": {
                    "power": {
                        "mean": float(power_mean),
                        "std": float(power_std),
                        "count": len(mentions),
                        "pdf": [{"x": float(x), "y": float(y)} for x, y in zip(power_range, power_pdf)]
                    },
                    "moral": {
                        "mean": float(moral_mean),
                        "std": float(moral_std),
                        "count": len(mentions),
                        "pdf": [{"x": float(x), "y": float(y)} for x, y in zip(moral_range, moral_pdf)]
                    }
                }
            }
        }
        
        # Add country-specific distribution if country filter was applied
        if country:
            result["distributions"]["national"] = {
                "country": country,
                "power": result["distributions"]["global"]["power"],
                "moral": result["distributions"]["global"]["moral"]
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching entity distribution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch entity distribution: {str(e)}")

# Historical sentiment endpoint for dashboard
@app.get("/stats/historical_sentiment", response_model=Dict[str, Any])
async def get_historical_sentiment(
    entity_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get historical sentiment data for a specific entity."""
    try:
        # Check if entity exists
        entity = db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get daily sentiment averages
        daily_sentiment = db.query(
            func.date(EntityMention.created_at).label("date"),
            func.avg(EntityMention.power_score).label("avg_power"),
            func.avg(EntityMention.moral_score).label("avg_moral"),
            func.count(EntityMention.id).label("mention_count")
        ).filter(
            EntityMention.entity_id == entity_id,
            EntityMention.created_at >= start_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).group_by(
            func.date(EntityMention.created_at)
        ).order_by(
            func.date(EntityMention.created_at)
        ).all()
        
        # Get overall stats for the period
        overall_stats = db.query(
            func.avg(EntityMention.power_score).label("avg_power"),
            func.avg(EntityMention.moral_score).label("avg_moral"),
            func.count(EntityMention.id).label("total_mentions")
        ).filter(
            EntityMention.entity_id == entity_id,
            EntityMention.created_at >= start_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).first()
        
        return {
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type
            },
            "date_range": {
                "start": start_date.date().isoformat(),
                "end": end_date.date().isoformat(),
                "days": days
            },
            "daily_data": [
                {
                    "date": result.date.isoformat(),
                    "power_score": float(result.avg_power) if result.avg_power else 0,
                    "moral_score": float(result.avg_moral) if result.avg_moral else 0,
                    "mention_count": result.mention_count
                }
                for result in daily_sentiment
            ],
            "summary": {
                "avg_power_score": float(overall_stats.avg_power) if overall_stats.avg_power else 0,
                "avg_moral_score": float(overall_stats.avg_moral) if overall_stats.avg_moral else 0,
                "total_mentions": overall_stats.total_mentions or 0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching historical sentiment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical sentiment: {str(e)}")

# Source-specific historical sentiment endpoint
@app.get("/stats/source_historical_sentiment", response_model=Dict[str, Any])
async def get_source_historical_sentiment(
    entity_id: int,
    days: int = Query(30, ge=1, le=365),
    countries: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """Get historical sentiment data for a specific entity broken down by news source."""
    try:
        logger.info(f"Source historical sentiment request: entity_id={entity_id}, days={days}, countries={countries}")
        # Check if entity exists
        entity = db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Base query for source-specific daily sentiment averages
        query = db.query(
            func.date(EntityMention.created_at).label("date"),
            NewsSource.name.label("source_name"),
            NewsSource.country,
            NewsSource.id.label("source_id"),
            func.avg(EntityMention.power_score).label("avg_power"),
            func.avg(EntityMention.moral_score).label("avg_moral"),
            func.count(EntityMention.id).label("mention_count")
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).join(
            NewsSource, NewsArticle.source_id == NewsSource.id
        ).filter(
            EntityMention.entity_id == entity_id,
            EntityMention.created_at >= start_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )
        
        # Apply country filter if provided
        if countries:
            logger.info(f"Filtering by countries: {countries}")
            query = query.filter(NewsSource.country.in_(countries))
        
        # Group by date, source, and country
        query = query.group_by(
            func.date(EntityMention.created_at),
            NewsSource.name,
            NewsSource.country,
            NewsSource.id
        ).having(
            func.count(EntityMention.id) >= 3  # Only include sources with at least 3 mentions
        ).order_by(
            NewsSource.name,
            func.date(EntityMention.created_at)
        )
        
        # Execute query
        results = query.all()
        
        # Organize data by source
        source_data = {}
        for result in results:
            source_key = f"{result.source_name} ({result.country})"
            
            if source_key not in source_data:
                source_data[source_key] = {
                    "source_name": result.source_name,
                    "country": result.country,
                    "source_id": result.source_id,
                    "daily_data": []
                }
            
            source_data[source_key]["daily_data"].append({
                "date": result.date.isoformat(),
                "power_score": float(result.avg_power) if result.avg_power else 0,
                "moral_score": float(result.avg_moral) if result.avg_moral else 0,
                "mention_count": result.mention_count
            })
        
        # Calculate summary statistics for each source
        for source_key, data in source_data.items():
            if data["daily_data"]:
                power_scores = [d["power_score"] for d in data["daily_data"]]
                moral_scores = [d["moral_score"] for d in data["daily_data"]]
                total_mentions = sum(d["mention_count"] for d in data["daily_data"])
                
                data["summary"] = {
                    "avg_power_score": sum(power_scores) / len(power_scores),
                    "avg_moral_score": sum(moral_scores) / len(moral_scores),
                    "total_mentions": total_mentions,
                    "days_with_data": len(data["daily_data"])
                }
        
        # Limit to top 10 sources by total mentions to avoid cluttered visualization
        if len(source_data) > 10:
            logger.info(f"Limiting from {len(source_data)} sources to top 10 by mentions")
            sorted_sources = sorted(
                source_data.items(), 
                key=lambda x: x[1]["summary"]["total_mentions"] if x[1].get("summary") else 0, 
                reverse=True
            )
            source_data = dict(sorted_sources[:10])
            logger.info(f"Top sources: {list(source_data.keys())}")
        
        return {
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type
            },
            "date_range": {
                "start": start_date.date().isoformat(),
                "end": end_date.date().isoformat(),
                "days": days
            },
            "countries_filter": countries,
            "sources": source_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching source historical sentiment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch source historical sentiment: {str(e)}")

# Include routers if available
if has_article_router:
    app.include_router(article_router, prefix="/articles", tags=["Articles"])
if has_stats_router:
    # Import and reconfigure stats router with our database dependency
    try:
        # Import all the endpoint functions and models from the stats module
        from extension.api.statistical_endpoints import (
            get_sentiment_distribution, get_entity_tracking, get_available_countries_for_entity,
            get_global_entity_counts, get_similar_articles,
            SentimentDistributionResponse, EntityTrackingResponse, AvailableCountriesResponse,
            SimilarArticlesResponse
        )
        
        # Create a new router specifically for this app with our database dependency
        stats_router_local = APIRouter()
        
        # Re-register endpoints with our database dependency
        @stats_router_local.get("/sentiment/distribution", response_model=SentimentDistributionResponse)
        async def sentiment_distribution_endpoint(
            entity_name: str,
            dimension: str = Query("power", regex="^(power|moral)$"),
            country: Optional[str] = None,
            source_id: Optional[int] = None,
            session: Session = Depends(get_db)
        ):
            return await get_sentiment_distribution(entity_name, dimension, country, source_id, session)
        
        @stats_router_local.get("/entity/tracking", response_model=EntityTrackingResponse)
        async def entity_tracking_endpoint(
            entity_name: str,
            days: int = Query(30, ge=1, le=365),
            window_size: int = Query(7, ge=1, le=30),
            source_id: Optional[int] = Query(None, description="Optional source ID to filter mentions"),
            session: Session = Depends(get_db)
        ):
            return await get_entity_tracking(entity_name, days, window_size, source_id, session)
        
        @stats_router_local.get("/entity/available-countries", response_model=AvailableCountriesResponse)
        async def available_countries_endpoint(
            entity_name: str,
            dimension: str = Query("power", regex="^(power|moral)$"),
            min_mentions: int = Query(3, ge=1),
            session: Session = Depends(get_db)
        ):
            return await get_available_countries_for_entity(entity_name, dimension, min_mentions, session)
        
        @stats_router_local.get("/entity/global-counts")
        def global_counts_endpoint(session: Session = Depends(get_db)):
            return get_global_entity_counts(session)
        
        @stats_router_local.get("/article/{article_id}/similar", response_model=SimilarArticlesResponse)
        def similar_articles_endpoint(
            article_id: str,
            limit: int = Query(10, ge=1, le=50),
            days_window: int = Query(3, ge=1, le=7),
            min_entity_overlap: float = Query(0.3, ge=0.1, le=1.0),
            session: Session = Depends(get_db)
        ):
            return get_similar_articles(article_id, limit, days_window, min_entity_overlap, session)
        
        app.include_router(stats_router_local, prefix="/stats", tags=["Statistics"])
    except Exception as e:
        logger.error(f"Failed to configure stats router: {e}")
        # Fall back to original approach if imports fail
        app.include_router(stats_router, prefix="/stats", tags=["Statistics"])
if has_similarity_router:
    app.include_router(similarity_router, prefix="/similarity", tags=["Similarity"])

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log the request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    # Process the request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log the response
    logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")
    
    return response

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Run with: uvicorn server.extension_api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)