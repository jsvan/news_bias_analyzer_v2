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
from functools import lru_cache

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, Body, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Float, text
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
from database.models import NewsArticle, Entity, EntityMention, NewsSource, Topic, Quote, QuoteTopic, PublicFigure

# Routers. Imports are deliberately NOT wrapped in try/except: a router that fails
# to import must fail the whole server loudly, not silently drop its routes (that
# pattern hid dead endpoints for months - see the retired extension/api/main.py).
from server.deps import get_db, resolve_entity_group
from server.routers.statistical_endpoints import router as stats_router
from server.routers.similarity_endpoints import router as similarity_router
from server.routers.narrative_endpoints import router as narrative_router
from server.routers.embeddings_endpoints import router as embeddings_router
from server.routers.drift_endpoints import router as drift_router
from server.routers.synchrony_endpoints import router as synchrony_router
from server.routers.dashboard_endpoints import router as dashboard_router

# Initialize FastAPI app
app = FastAPI(
    title="News Bias Analyzer Extension API",
    description="API for the news bias analyzer browser extension",
    version="0.1.0"
)

# Configure CORS based on environment
def get_cors_origins():
    """Get allowed CORS origins based on environment"""
    environment = os.getenv("APP_ENV", "development")
    
    if environment == "production":
        # Production: allow Chrome extension + GitHub Pages
        return [
            "chrome-extension://*",  # Chrome extension
            "moz-extension://*",     # Firefox extension  
            "https://jsvan.github.io",  # Your GitHub Pages URL
            "https://your-custom-domain.com",  # Replace with your custom domain if any
        ]
    elif environment == "staging":
        # Staging: allow staging domains + extensions
        return [
            "chrome-extension://*",
            "moz-extension://*",
            "https://staging.news-bias-analyzer.example.com"
        ]
    else:
        # Development: allow all localhost + extensions
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "chrome-extension://*",
            "moz-extension://*"
        ]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Database connection + per-request session dependency live in server/deps.py
# (shared with every router) - imported above.
from server.deps import db_manager

# Caching for entity autocomplete
POPULAR_ENTITIES_CACHE = {}
POPULAR_ENTITIES_CACHE_TIME = 0
POPULAR_ENTITIES_CACHE_TTL = 3600  # 1 hour
SEARCH_RESULTS_CACHE = {}
SEARCH_CACHE_TTL = 300  # 5 minutes

def get_popular_entities(db: Session, limit: int = 1000):
    """Get most popular entities with caching.

    Canonical rows only, with mention counts summed across every entity merged
    into them (Entity.canonical_id) - same resolution as get_entities."""
    global POPULAR_ENTITIES_CACHE, POPULAR_ENTITIES_CACHE_TIME

    current_time = time.time()
    if (current_time - POPULAR_ENTITIES_CACHE_TIME) > POPULAR_ENTITIES_CACHE_TTL:
        # Cache expired, refresh
        resolved_id = func.coalesce(Entity.canonical_id, Entity.id)
        mention_counts = db.query(
            resolved_id.label("resolved_id"),
            func.count(EntityMention.id).label("mention_count")
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id, isouter=True
        ).group_by(resolved_id).subquery()

        query = db.query(
            Entity.id,
            Entity.name,
            Entity.entity_type,
            func.coalesce(mention_counts.c.mention_count, 0).label("mention_count")
        ).outerjoin(
            mention_counts, Entity.id == mention_counts.c.resolved_id
        ).filter(
            Entity.canonical_id.is_(None)
        ).order_by(
            func.coalesce(mention_counts.c.mention_count, 0).desc(),
            Entity.name
        ).limit(limit)

        results = query.all()
        POPULAR_ENTITIES_CACHE = [
            {
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type,
                "mention_count": entity.mention_count or 0
            }
            for entity in results
        ]
        POPULAR_ENTITIES_CACHE_TIME = current_time
    
    return POPULAR_ENTITIES_CACHE

def _canonical_name_hits(db: Session, name_filter, exclude_ids, limit: int):
    """Canonical entities whose own name OR any merged alias's name matches
    name_filter, with mention counts summed across the whole merged group.

    Matching on alias rows too is deliberate: a search for "Zelenskyy" must
    surface "Volodymyr Zelensky" even though only the merged alias row carries
    that spelling."""
    resolved_id = func.coalesce(Entity.canonical_id, Entity.id)
    matched = db.query(
        resolved_id.label("resolved_id")
    ).filter(name_filter).distinct().subquery()

    counts = db.query(
        func.coalesce(Entity.canonical_id, Entity.id).label("resolved_id"),
        func.count(EntityMention.id).label("mention_count")
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id, isouter=True
    ).group_by(func.coalesce(Entity.canonical_id, Entity.id)).subquery()

    query = db.query(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.coalesce(counts.c.mention_count, 0).label("mention_count")
    ).join(
        matched, Entity.id == matched.c.resolved_id
    ).outerjoin(
        counts, Entity.id == counts.c.resolved_id
    )
    if exclude_ids:
        query = query.filter(~Entity.id.in_(exclude_ids))
    return query.order_by(
        func.coalesce(counts.c.mention_count, 0).desc(),
        Entity.name
    ).limit(limit).all()


def search_entities_tiered(db: Session, query_text: str, limit: int = 15):
    """Perform tiered search: prefix match -> word boundary -> contains."""
    query_lower = query_text.lower().strip()
    
    # Check cache first
    cache_key = f"{query_lower}:{limit}"
    current_time = time.time()
    
    if cache_key in SEARCH_RESULTS_CACHE:
        cached_result, cached_time = SEARCH_RESULTS_CACHE[cache_key]
        if (current_time - cached_time) < SEARCH_CACHE_TTL:
            return cached_result
    
    # If short query, search in popular entities cache first
    if len(query_lower) <= 3:
        popular_entities = get_popular_entities(db)
        filtered = [
            entity for entity in popular_entities
            if query_lower in entity["name"].lower()
        ][:limit]
        
        # Cache the result
        SEARCH_RESULTS_CACHE[cache_key] = (filtered, current_time)
        return filtered
    
    # For longer queries, use tiered database search. Each tier matches alias
    # rows too but returns canonical entities with group-wide counts.
    results = []

    # Tier 1: Prefix match (highest priority)
    if len(results) < limit:
        results.extend(_canonical_name_hits(
            db, func.lower(Entity.name).like(f"{query_lower}%"),
            [r.id for r in results], limit))

    # Tier 2: Word boundary match (if still need more results)
    if len(results) < limit:
        results.extend(_canonical_name_hits(
            db, func.lower(Entity.name).like(f"% {query_lower}%"),
            [r.id for r in results], limit - len(results)))

    # Tier 3: Contains match (if still need more results)
    if len(results) < limit:
        results.extend(_canonical_name_hits(
            db, func.lower(Entity.name).like(f"%{query_lower}%"),
            [r.id for r in results], limit - len(results)))
    
    # Format results
    formatted_results = [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type,
            "mention_count": entity.mention_count or 0
        }
        for entity in results[:limit]
    ]
    
    # Cache the result
    SEARCH_RESULTS_CACHE[cache_key] = (formatted_results, current_time)
    return formatted_results

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
            conn.execute(text("SELECT 1"))
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
    """Get list of entities, optionally filtered by type and search term, ordered by mention count.

    Mentions are counted across every entity merged into a canonical one
    (Entity.canonical_id, set by analyzer/entity_resolution.py's merge job), and only the
    canonical row (canonical_id IS NULL) is returned as a top-level entity - this is what
    stops e.g. two "United States" rows from both appearing in this list.
    """
    resolved_id = func.coalesce(Entity.canonical_id, Entity.id)
    mention_counts = db.query(
        resolved_id.label("resolved_id"),
        func.count(EntityMention.id).label("mention_count")
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id, isouter=True
    ).group_by(resolved_id).subquery()

    query = db.query(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.coalesce(mention_counts.c.mention_count, 0).label("mention_count")
    ).outerjoin(
        mention_counts, Entity.id == mention_counts.c.resolved_id
    ).filter(
        Entity.canonical_id.is_(None)
    )

    if entity_type:
        query = query.filter(Entity.entity_type == entity_type)

    if search:
        # Case-insensitive search
        query = query.filter(func.lower(Entity.name).like(f"%{search.lower()}%"))

    # Order by mention count descending, then by name
    entities = query.order_by(
        func.coalesce(mention_counts.c.mention_count, 0).desc(),
        Entity.name
    ).limit(limit).all()

    # Alias names merged into each canonical entity, so static-mode search
    # (client-side over this list) can match variant spellings too. Alias rows
    # that just repeat the canonical name (a merged loser the canonical was
    # later renamed to match) add nothing for search - drop them.
    canonical_names = {e.id: e.name.lower() for e in entities}
    aliases_by_canonical = {}
    if entities:
        alias_rows = db.query(Entity.canonical_id, Entity.name).filter(
            Entity.canonical_id.in_([e.id for e in entities]))
        for canonical_id, alias_name in alias_rows:
            if alias_name.lower() == canonical_names.get(canonical_id):
                continue
            bucket = aliases_by_canonical.setdefault(canonical_id, set())
            bucket.add(alias_name)

    return [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type,
            "mention_count": entity.mention_count or 0,
            **({"aliases": sorted(aliases_by_canonical[entity.id])}
               if entity.id in aliases_by_canonical else {})
        }
        for entity in entities
    ]

@app.get("/entities/search", response_model=List[Dict[str, Any]])
def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(15, ge=1, le=50, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """Fast entity search with tiered matching and caching."""
    try:
        return search_entities_tiered(db, q, limit)
    except Exception as e:
        logging.error(f"Error in entity search: {e}")
        # Fallback to simple search if tiered search fails. Canonical rows only
        # so merged aliases never show up as duplicate results; counts here are
        # per-row (not group-summed) - acceptable for an emergency path.
        query = db.query(
            Entity.id,
            Entity.name,
            Entity.entity_type,
            func.count(EntityMention.id).label("mention_count")
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id, isouter=True
        ).filter(
            func.lower(Entity.name).like(f"%{q.lower()}%"),
            Entity.canonical_id.is_(None)
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
    """Get sentiment data for a specific entity over time.

    Mentions are gathered across the whole merged group (Entity.canonical_id),
    so alias rows contribute to their canonical entity's series."""
    entity, group_ids = resolve_entity_group(db, entity_id)
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
        EntityMention.entity_id.in_(group_ids)
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
            "id": article.id,
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
                    "id": article.id,
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
            "id": article.id,
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
    days: Optional[int] = Query(None, ge=1, le=3650),
    country: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Most-mentioned entities with average power/moral scores. Omit days for all-time.

    Aggregates across merged entities via Entity.canonical_id (same resolution as
    /entities), so e.g. two "Donald Trump" rows surface as one canonical point.
    With country set, only mentions published by that country's sources count —
    the same numbers, seen from one national sphere. With source_id set, only that
    one newspaper's mentions count; single-paper averages over 1-2 mentions are
    noise (per-mention scores are integers on -2..2), so source-scoped rows need
    at least 3 mentions.
    """
    try:
        resolved_id = func.coalesce(Entity.canonical_id, Entity.id)
        agg = db.query(
            resolved_id.label('resolved_id'),
            func.count(EntityMention.id).label('mention_count'),
            func.avg(EntityMention.power_score).label('avg_power'),
            func.avg(EntityMention.moral_score).label('avg_moral')
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).filter(
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )

        if country or source_id:
            agg = agg.join(NewsArticle, EntityMention.article_id == NewsArticle.id)
            if source_id:
                agg = agg.filter(NewsArticle.source_id == source_id)
            if country:
                agg = agg.join(
                    NewsSource, NewsArticle.source_id == NewsSource.id
                ).filter(NewsSource.country == country)

        if days:
            agg = agg.filter(EntityMention.created_at >= datetime.utcnow() - timedelta(days=days))

        agg = agg.group_by(resolved_id)
        if source_id:
            agg = agg.having(func.count(EntityMention.id) >= 3)
        agg = agg.subquery()

        trending = db.query(
            Entity.id,
            Entity.name,
            Entity.entity_type,
            agg.c.mention_count,
            agg.c.avg_power,
            agg.c.avg_moral
        ).join(
            agg, Entity.id == agg.c.resolved_id
        ).order_by(
            agg.c.mention_count.desc()
        ).limit(limit).all()

        return [
            {
                'id': entity.id,
                'entity': entity.name,
                'type': entity.entity_type,
                'power_score': float(entity.avg_power) if entity.avg_power is not None else 0,
                'moral_score': float(entity.avg_moral) if entity.avg_moral is not None else 0,
                'mention_count': entity.mention_count,
            }
            for entity in trending
        ]
    except Exception as e:
        logger.error(f"Error fetching trending entities: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending entities: {str(e)}")

# Entity distribution endpoint for dashboard
@app.get("/stats/entity_distribution/{entity_id}", response_model=Dict[str, Any])
async def get_entity_distribution(
    entity_id: int,
    country: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
    days: Optional[int] = Query(None, ge=1, le=3650),
    layers: Optional[str] = Query(None, description="Comma-separated subset of global,national,source; omit for all applicable"),
    db: Session = Depends(get_db)
):
    """Get sentiment distribution data for a specific entity. Omit days for all-time.

    Mentions are gathered across the whole merged group (Entity.canonical_id) and
    the canonical row is reported as the entity, so alias ids fold into one view.

    `layers` restricts which layers are computed AND fetched: asking for only the
    national or source layer filters at the SQL level instead of pulling every
    mention of the entity to compute a global KDE nobody asked for. The snapshot
    exporter and per-layer gap-fill calls depend on this being cheap."""
    try:
        # isinstance guard: direct (non-HTTP) callers that omit layers pass the
        # FastAPI Query default object through, which is truthy but not a str.
        wanted = ({s.strip() for s in layers.split(",") if s.strip()}
                  if isinstance(layers, str) and layers else {"global", "national", "source"})
        unknown = wanted - {"global", "national", "source"}
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown layers: {sorted(unknown)}")

        entity, group_ids = resolve_entity_group(db, entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")

        # Calculate date range; no days param = all time
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days) if days else datetime(1970, 1, 1)

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
            EntityMention.entity_id.in_(group_ids),
            NewsArticle.publish_date >= start_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )

        # No filters by default: global is always ALL mentions, and national/source
        # are computed below as true subsets. (Previously a country/source filter
        # was applied to this base query, which silently turned "global" into the
        # subset, and "national" was returned as a reference to the same object.)
        # Exception: when the caller wants exactly one scoped layer and no global,
        # the subset IS the whole result set, so filter in SQL and skip the rest.
        scoped_only = "global" not in wanted and wanted in ({"national"}, {"source"})
        if scoped_only and wanted == {"national"} and country:
            query = query.filter(NewsSource.country == country)
        elif scoped_only and wanted == {"source"} and source_id:
            query = query.filter(NewsArticle.source_id == source_id)
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

        import numpy as np

        # Empirical density on a fixed grid so every layer shares an x-axis and
        # curves are directly comparable. Scores live on [-2, 2].
        GRID = np.linspace(-2.0, 2.0, 121)

        def empirical_pdf(scores):
            """KDE of the real scores - the actual shape (skew, lumps, multimodality),
            not an idealized normal drawn from mean/std. Histogram fallback when the
            sample is too small or degenerate for a bandwidth estimate."""
            arr = np.asarray(scores, dtype=float)
            try:
                from scipy.stats import gaussian_kde
                if len(arr) >= 5 and np.std(arr) > 1e-9:
                    return gaussian_kde(arr)(GRID)
            except ImportError:
                pass
            except Exception:
                pass  # singular matrix etc. - fall through to histogram
            hist, edges = np.histogram(arr, bins=20, range=(-2.0, 2.0), density=True)
            centers = (edges[:-1] + edges[1:]) / 2
            return np.interp(GRID, centers, hist, left=0.0, right=0.0)

        def layer_stats(subset):
            power = [m.power_score for m in subset]
            moral = [m.moral_score for m in subset]
            return {
                "power": {
                    "mean": float(np.mean(power)),
                    "std": float(np.std(power)),
                    "count": len(subset),
                    "pdf": {"x": [float(v) for v in GRID], "y": [float(v) for v in empirical_pdf(power)]},
                },
                "moral": {
                    "mean": float(np.mean(moral)),
                    "std": float(np.std(moral)),
                    "count": len(subset),
                    "pdf": {"x": [float(v) for v in GRID], "y": [float(v) for v in empirical_pdf(moral)]},
                },
            }

        result = {
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type
            },
            "distributions": {}
        }

        # The subset comprehensions are correct in the scoped_only case too —
        # every fetched mention already matches, so they're identity filters.
        if "global" in wanted:
            result["distributions"]["global"] = layer_stats(mentions)

        if "national" in wanted and country:
            national = [m for m in mentions if m.country == country]
            if national:
                result["distributions"]["national"] = {"country": country, **layer_stats(national)}

        if "source" in wanted and source_id:
            source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
            if source:
                subset = [m for m in mentions if m.source_name == source.name]
                if subset:
                    result["distributions"]["source"] = {"source_id": source.id, "source_name": source.name, **layer_stats(subset)}

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
    days: Optional[int] = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db)
):
    """Get historical sentiment data for a specific entity. Omit days for all-time.

    Mentions are gathered across the whole merged group (Entity.canonical_id) and
    the canonical row is reported as the entity, so alias ids fold into one view."""
    try:
        entity, group_ids = resolve_entity_group(db, entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")

        # Calculate date range; no days param = all time
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days) if days else datetime(1970, 1, 1)

        # Get daily sentiment averages
        daily_sentiment = db.query(
            func.date(EntityMention.created_at).label("date"),
            func.avg(EntityMention.power_score).label("avg_power"),
            func.avg(EntityMention.moral_score).label("avg_moral"),
            func.count(EntityMention.id).label("mention_count")
        ).filter(
            EntityMention.entity_id.in_(group_ids),
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
            EntityMention.entity_id.in_(group_ids),
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
    days: Optional[int] = Query(None, ge=1, le=3650),
    countries: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """Get historical sentiment data for a specific entity broken down by news source. Omit days for all-time.

    Mentions are gathered across the whole merged group (Entity.canonical_id) and
    the canonical row is reported as the entity, so alias ids fold into one view."""
    try:
        logger.info(f"Source historical sentiment request: entity_id={entity_id}, days={days}, countries={countries}")
        entity, group_ids = resolve_entity_group(db, entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")

        # Calculate date range; no days param = all time
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days) if days else datetime(1970, 1, 1)
        
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
            EntityMention.entity_id.in_(group_ids),
            EntityMention.created_at >= start_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )

        # Apply country filter if provided
        if countries:
            logger.info(f"Filtering by countries: {countries}")
            query = query.filter(NewsSource.country.in_(countries))
            
            # Group by date, source, and country (source-level data)
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
        else:
            # No country filter - aggregate by country
            logger.info("No country filter provided - aggregating by country")
            query = db.query(
                func.date(EntityMention.created_at).label("date"),
                NewsSource.country,
                func.avg(EntityMention.power_score).label("avg_power"),
                func.avg(EntityMention.moral_score).label("avg_moral"),
                func.count(EntityMention.id).label("mention_count")
            ).join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).join(
                NewsSource, NewsArticle.source_id == NewsSource.id
            ).filter(
                EntityMention.entity_id.in_(group_ids),
                EntityMention.created_at >= start_date,
                EntityMention.power_score.isnot(None),
                EntityMention.moral_score.isnot(None)
            ).group_by(
                func.date(EntityMention.created_at),
                NewsSource.country
            ).having(
                func.count(EntityMention.id) >= 3  # Only include countries with at least 3 mentions per day
            ).order_by(
                NewsSource.country,
                func.date(EntityMention.created_at)
            )
        
        # Execute query
        results = query.all()
        
        # Organize data by source or country
        source_data = {}
        for result in results:
            if countries:
                # Source-level data when countries are filtered
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
            else:
                # Country-level data when no countries are filtered
                country_key = result.country
                
                if country_key not in source_data:
                    source_data[country_key] = {
                        "source_name": result.country,  # Use country as source name
                        "country": result.country,
                        "source_id": None,  # No specific source ID for country aggregation
                        "daily_data": []
                    }
                
                source_data[country_key]["daily_data"].append({
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
        
        # Sort sources by total mentions for consistent ordering
        sorted_sources = sorted(
            source_data.items(), 
            key=lambda x: x[1]["summary"]["total_mentions"] if x[1].get("summary") else 0, 
            reverse=True
        )
        source_data = dict(sorted_sources)
        logger.info(f"Returning {len(source_data)} sources with data")
        
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

# Register routers. Each endpoint is declared in exactly one place (its router
# module); the wrapper re-declarations that used to shadow router signatures here
# are gone - all routers share server.deps.get_db.
app.include_router(stats_router, prefix="/stats", tags=["Statistics"])
app.include_router(similarity_router, prefix="/similarity", tags=["Similarity"])
# No prefix on the rest - routes declare their full paths (/narrative/..., etc.).
app.include_router(narrative_router, tags=["Narrative"])
app.include_router(embeddings_router, tags=["Narrative"])
app.include_router(drift_router, tags=["Narrative"])
app.include_router(synchrony_router, tags=["Narrative"])
app.include_router(dashboard_router, tags=["Dashboard"])

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

# Run with: uvicorn server.extension_api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)