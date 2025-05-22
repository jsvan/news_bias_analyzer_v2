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
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Float
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
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get list of entities, optionally filtered by type."""
    query = db.query(Entity)
    
    if entity_type:
        query = query.filter(Entity.entity_type == entity_type)
    
    entities = query.limit(limit).all()
    
    return [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type
        }
        for entity in entities
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
        
        # For a real implementation, we would use a proper extraction library here
        # such as trafilatura, newspaper3k, etc., but for demo purposes, we're creating
        # a simple placeholder response
        
        # Try to fetch the page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Extract title from HTML - very basic extraction
        html = response.text
        title = None
        if '<title>' in html and '</title>' in html:
            title_start = html.find('<title>') + 7
            title_end = html.find('</title>', title_start)
            title = html[title_start:title_end].strip()
            
        # Extract text - this is a very basic implementation
        # In a real system, use a proper HTML parser or extraction library
        text = html
        
        # Remove script tags and their content
        while '<script' in text and '</script>' in text:
            script_start = text.find('<script')
            script_end = text.find('</script>', script_start) + 9
            text = text[:script_start] + text[script_end:]
            
        # Remove style tags and their content
        while '<style' in text and '</style>' in text:
            style_start = text.find('<style')
            style_end = text.find('</style>', style_start) + 8
            text = text[:style_start] + text[style_end:]
            
        # Strip HTML tags - very basic, won't handle all cases
        # In a real implementation, use BeautifulSoup or another HTML parser
        text = text.replace('<', ' <').replace('>', '> ')
        import re
        text = re.sub(r'<[^>]+>', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Limit text length for response
        if len(text) > 15000:
            text = text[:15000] + '...'
            
        # Extract publish date - also very basic
        publish_date = None
        date_patterns = [
            r'datetime="([^"]+)"',
            r'pubdate="([^"]+)"',
            r'publishdate="([^"]+)"',
            r'date"? content="([^"]+)"',
            r'article:published_time" content="([^"]+)"'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                publish_date = match.group(1)
                break
                
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
        
        # Create response
        response = {
            "url": url,
            "exists": True,
            "title": article.title,
            "source": article.source.name if article.source else "Unknown",
            "publish_date": article.publish_date,
            "entities": formatted_entities,
            "analysis_date": article.processed_at,
            "from_database": True
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
    """
    Analyze article content for bias and sentiment using OpenAI.
    
    This endpoint calls the OpenAI API to perform entity extraction and sentiment analysis.
    It extracts named entities from the article content and analyzes how they are portrayed
    in terms of power and moral dimensions. Analysis results are saved to the database.
    """
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
                
                # Generate a simple composite score
                composite_percentile = 50  # Default to median
                composite_p_value = 0.5    # Default p-value
                
                # Create response
                api_response = {
                    "url": request.url,
                    "title": article.title,
                    "source": article.source.name if article.source else request.source,
                    "publish_date": article.publish_date,
                    "composite_score": {
                        "percentile": composite_percentile,
                        "p_value": composite_p_value
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
                created_at=datetime.utcnow()
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
        
        # Generate a simple composite score based on entity sentiment
        composite_percentile = 50  # Default to median
        composite_p_value = 0.5    # Default p-value
        
        # Create response
        api_response = {
            "url": request.url,
            "title": request.title,
            "source": request.source,
            "publish_date": request.publish_date,
            "composite_score": {
                "percentile": composite_percentile,
                "p_value": composite_p_value
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

# Include routers if available
if has_article_router:
    app.include_router(article_router, prefix="/articles", tags=["Articles"])
if has_stats_router:
    # Override the database dependency in the stats router
    from extension.api.statistical_endpoints import get_db_session
    app.dependency_overrides[get_db_session] = get_db
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