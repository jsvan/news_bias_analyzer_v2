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
from sqlalchemy import func
import requests
from urllib.parse import urlparse

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

# Article analysis endpoint
@app.post("/analyze")
async def analyze_article(request: ArticleAnalysisRequest):
    """
    Analyze article content for bias and sentiment using OpenAI.
    
    This endpoint calls the OpenAI API to perform entity extraction and sentiment analysis.
    It extracts named entities from the article content and analyzes how they are portrayed
    in terms of power and moral dimensions.
    """
    logger.info(f"Analyzing article: {request.title} ({request.url})")
    print(f"\n==== ANALYZING ARTICLE: {request.title} ====")
    print(f"URL: {request.url}")
    print(f"Source: {request.source}")
    print(f"Content length: {len(request.text)} characters")
    
    try:
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
        
        # Call the OpenAI analyzer
        print("Calling OpenAI for analysis...")
        analysis_result = analyzer.analyze_article(article_data)
        
        # Extract entities from the analysis result
        entities = analysis_result.get('entities', [])
        print(f"OpenAI found {len(entities)} entities in the article")
        
        # Format entities for the response
        formatted_entities = []
        for entity in entities:
            formatted_entity = {
                "name": entity.get('entity', ''),
                "type": entity.get('entity_type', ''),
                "power_score": entity.get('power_score', 0),
                "moral_score": entity.get('moral_score', 0),
                "national_significance": 0.3,  # Placeholder
                "global_significance": 0.2,    # Placeholder
                "mentions": entity.get('mentions', [])
            }
            formatted_entities.append(formatted_entity)
        
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
            "newly_analyzed": True
        }
        
        # Print the entities for debugging
        print("\nAnalysis response contains the following entities:")
        for entity in formatted_entities:
            print(f"  - {entity['name']} ({entity['type']})")
            print(f"    Power: {entity['power_score']}, Moral: {entity['moral_score']}")
            print(f"    Mentions: {len(entity.get('mentions', []))}")
        
        logger.info(f"Analysis completed for {request.url}")
        return api_response
    
    except Exception as e:
        logger.error(f"Error analyzing article: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# Include routers if available
if has_article_router:
    app.include_router(article_router, prefix="/articles", tags=["Articles"])
if has_stats_router:
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