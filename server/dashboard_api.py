"""
Dashboard API Server Module

This module provides the FastAPI server implementation for the frontend dashboard API.
It includes all the endpoints needed by the dashboard to display news sentiment analysis data,
entity tracking, and statistical comparisons.
"""

import os
import sys
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dashboard_api")

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import database models and utilities
from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention, NewsSource

# Try to import the statistics router
try:
    from frontend.api.statistical_endpoints import router as stats_router
    has_stats_router = True
except ImportError:
    # If the stats router is not available, create a dummy router
    from fastapi import APIRouter
    stats_router = APIRouter()
    has_stats_router = False

# Import intelligence system
try:
    from intelligence.api_endpoints import router as intelligence_router
    has_intelligence_router = True
except ImportError:
    from fastapi import APIRouter
    intelligence_router = APIRouter()
    has_intelligence_router = False

# Initialize FastAPI app
app = FastAPI(
    title="News Bias Analyzer Dashboard API",
    description="API for the news bias analyzer dashboard",
    version="0.1.0"
)

# Configure CORS based on environment
def get_cors_origins():
    """Get allowed CORS origins based on environment"""
    environment = os.getenv("APP_ENV", "development")
    
    if environment == "production":
        # Production: only allow specific domains
        return [
            "https://jsv.github.io",  # Replace with your GitHub username
            "https://your-custom-domain.com",  # Replace with your custom domain if any
            "https://api.news-bias-analyzer.example.com"  # Your production API domain
        ]
    elif environment == "staging":
        # Staging: allow staging domains
        return [
            "https://staging.news-bias-analyzer.example.com",
            "https://api-staging.news-bias-analyzer.example.com"
        ]
    else:
        # Development: allow all localhost origins
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:4173",  # Vite preview
            "http://127.0.0.1:4173"
        ]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
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
    return {"message": "News Bias Analyzer Dashboard API"}

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
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

# Entity details endpoint
@app.get("/entities/{entity_id}", response_model=Dict[str, Any])
def get_entity(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific entity."""
    # Get entity data
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")
    
    # Count mentions
    mention_count = db.query(func.count(EntityMention.id)).filter(
        EntityMention.entity_id == entity_id
    ).scalar()
    
    # Get sources mentioning this entity
    sources_query = db.query(
        NewsSource.id,
        NewsSource.name,
        func.count(EntityMention.id).label("mention_count")
    ).join(
        NewsArticle, NewsSource.id == NewsArticle.source_id
    ).join(
        EntityMention, NewsArticle.id == EntityMention.article_id
    ).filter(
        EntityMention.entity_id == entity_id
    ).group_by(
        NewsSource.id,
        NewsSource.name
    ).order_by(
        func.count(EntityMention.id).desc()
    ).limit(10)
    
    sources = [{
        "id": source.id,
        "name": source.name,
        "mention_count": source.mention_count
    } for source in sources_query.all()]
    
    # Get sentiment averages
    sentiment_avg = db.query(
        func.avg(EntityMention.power_score).label("avg_power"),
        func.avg(EntityMention.moral_score).label("avg_moral")
    ).filter(
        EntityMention.entity_id == entity_id
    ).first()
    
    return {
        "id": entity.id,
        "name": entity.name,
        "type": entity.entity_type,
        "mention_count": mention_count,
        "top_sources": sources,
        "sentiment": {
            "power_score": float(sentiment_avg.avg_power) if sentiment_avg.avg_power else 0,
            "moral_score": float(sentiment_avg.avg_moral) if sentiment_avg.avg_moral else 0
        }
    }

# Entity sentiment endpoint
@app.get("/entities/{entity_id}/sentiment", response_model=List[Dict[str, Any]])
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

# Source details endpoint
@app.get("/sources/{source_id}", response_model=Dict[str, Any])
def get_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific news source."""
    # Get source data
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source with ID {source_id} not found")
    
    # Count articles
    article_count = db.query(func.count(NewsArticle.id)).filter(
        NewsArticle.source_id == source_id
    ).scalar()
    
    # Get most mentioned entities from this source
    entities_query = db.query(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.count(EntityMention.id).label("mention_count")
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id
    ).join(
        NewsArticle, EntityMention.article_id == NewsArticle.id
    ).filter(
        NewsArticle.source_id == source_id
    ).group_by(
        Entity.id,
        Entity.name,
        Entity.entity_type
    ).order_by(
        func.count(EntityMention.id).desc()
    ).limit(10)
    
    entities = [{
        "id": entity.id,
        "name": entity.name,
        "type": entity.entity_type,
        "mention_count": entity.mention_count
    } for entity in entities_query.all()]
    
    # Get average sentiment
    sentiment_avg = db.query(
        func.avg(EntityMention.power_score).label("avg_power"),
        func.avg(EntityMention.moral_score).label("avg_moral")
    ).join(
        NewsArticle, EntityMention.article_id == NewsArticle.id
    ).filter(
        NewsArticle.source_id == source_id
    ).first()
    
    return {
        "id": source.id,
        "name": source.name,
        "country": source.country,
        "language": source.language,
        "article_count": article_count,
        "top_entities": entities,
        "sentiment": {
            "power_score": float(sentiment_avg.avg_power) if sentiment_avg.avg_power else 0,
            "moral_score": float(sentiment_avg.avg_moral) if sentiment_avg.avg_moral else 0
        }
    }

# Source sentiment endpoint
@app.get("/sources/{source_id}/sentiment", response_model=Dict[str, Any])
def get_source_sentiment(
    source_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Get sentiment data for a specific news source."""
    # Check if source exists
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source with ID {source_id} not found")
    
    # Set date range
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=90)
    
    # Get time series data
    timeseries_query = db.query(
        func.date_trunc('day', NewsArticle.publish_date).label("date"),
        func.avg(EntityMention.power_score).label("avg_power"),
        func.avg(EntityMention.moral_score).label("avg_moral")
    ).join(
        EntityMention, NewsArticle.id == EntityMention.article_id
    ).filter(
        NewsArticle.source_id == source_id,
        NewsArticle.publish_date.between(start_date, end_date)
    ).group_by(
        func.date_trunc('day', NewsArticle.publish_date)
    ).order_by(
        func.date_trunc('day', NewsArticle.publish_date)
    )
    
    timeseries = [{
        "date": result.date,
        "power_score": float(result.avg_power) if result.avg_power else 0,
        "moral_score": float(result.avg_moral) if result.avg_moral else 0
    } for result in timeseries_query.all()]
    
    # Get entity breakdown
    entity_query = db.query(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.avg(EntityMention.power_score).label("avg_power"),
        func.avg(EntityMention.moral_score).label("avg_moral"),
        func.count(EntityMention.id).label("mention_count")
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id
    ).join(
        NewsArticle, EntityMention.article_id == NewsArticle.id
    ).filter(
        NewsArticle.source_id == source_id,
        NewsArticle.publish_date.between(start_date, end_date)
    ).group_by(
        Entity.id,
        Entity.name,
        Entity.entity_type
    ).order_by(
        func.count(EntityMention.id).desc()
    ).limit(20)
    
    entities = [{
        "id": entity.id,
        "name": entity.name,
        "type": entity.entity_type,
        "power_score": float(entity.avg_power) if entity.avg_power else 0,
        "moral_score": float(entity.avg_moral) if entity.avg_moral else 0,
        "mention_count": entity.mention_count
    } for entity in entity_query.all()]
    
    return {
        "source": {
            "id": source.id,
            "name": source.name,
            "country": source.country
        },
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "timeseries": timeseries,
        "entities": entities
    }

# Stats endpoints for dashboard
@app.get("/stats/trending_entities", response_model=List[Dict[str, Any]])
def get_trending_entities(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get trending entities based on recent mention frequency."""
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Query for entities with most mentions in time period
    trending_query = db.query(
        Entity.id,
        Entity.name,
        Entity.entity_type,
        func.count(EntityMention.id).label("mention_count"),
        func.avg(EntityMention.power_score).label("avg_power"),
        func.avg(EntityMention.moral_score).label("avg_moral")
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id
    ).join(
        NewsArticle, EntityMention.article_id == NewsArticle.id
    ).filter(
        EntityMention.created_at >= start_date,
        EntityMention.power_score.isnot(None),
        EntityMention.moral_score.isnot(None)
    ).group_by(
        Entity.id,
        Entity.name,
        Entity.entity_type
    ).order_by(
        func.count(EntityMention.id).desc()
    ).limit(limit)
    
    results = trending_query.all()
    
    return [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type,
            "mention_count": entity.mention_count,
            "power_score": float(entity.avg_power) if entity.avg_power else 0,
            "moral_score": float(entity.avg_moral) if entity.avg_moral else 0
        }
        for entity in results
    ]

@app.get("/stats/historical_sentiment", response_model=Dict[str, Any])
def get_historical_sentiment(
    entity_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get historical sentiment data for a specific entity."""
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

# Include routers if available
if has_stats_router:
    app.include_router(stats_router)

if has_intelligence_router:
    app.include_router(intelligence_router)

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

# Enable CORS with environment-aware settings
def get_cors_origins():
    """Get allowed CORS origins based on environment."""
    environment = os.getenv("APP_ENV", "development")
    
    if environment == "development":
        return [
            "http://localhost:3000",  # Vite dev server
            "http://localhost:4173",  # Vite preview server
            "http://127.0.0.1:3000",
            "http://127.0.0.1:4173",
        ]
    elif environment == "staging":
        return [
            "https://staging.news-bias-analyzer.example.com",
            "https://*.github.io",    # GitHub Pages staging
        ]
    elif environment == "production":
        return [
            "https://news-bias-analyzer.example.com",
            "https://jsv.github.io", # GitHub Pages (replace with actual username)
        ]
    else:
        # Fallback to development settings
        return [
            "http://localhost:3000",
        ]

cors_origins = get_cors_origins()
logger.info(f"Dashboard CORS configured for origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Run with: uvicorn server.dashboard_api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)