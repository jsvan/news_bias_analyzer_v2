"""
Entity/source detail endpoints ported from the retired server/dashboard_api.py.

The frontend (frontend/services/api.ts) always calls port 8000 (the consolidated
app), but these four routes used to live only in dashboard_api.py on port 8001 -
so getEntityById/getSourceById & friends were silent 404s. Porting them here was
part of the server consolidation (docs/STATE_OF_PROJECT_2026.md, "Known warts" 1
and 3).

Note the app module also declares /entities, /entities/search and /sources.
Those are matched before this router's /entities/{entity_id} because the app's
own routes are declared first.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from server.deps import get_db
from database.models import Entity, EntityMention, NewsArticle, NewsSource

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/entities/{entity_id}", response_model=Dict[str, Any])
def get_entity(entity_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific entity."""
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")

    mention_count = db.query(func.count(EntityMention.id)).filter(
        EntityMention.entity_id == entity_id
    ).scalar()

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


@router.get("/entities/{entity_id}/sentiment", response_model=List[Dict[str, Any]])
def get_entity_sentiment_series(
    entity_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    source_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get sentiment data for a specific entity over time."""
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")

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

    if start_date:
        query = query.filter(NewsArticle.publish_date >= start_date)
    if end_date:
        query = query.filter(NewsArticle.publish_date <= end_date)
    if source_id:
        query = query.filter(NewsArticle.source_id == source_id)

    results = query.order_by(NewsArticle.publish_date).all()

    return [
        {
            "power_score": result.power_score,
            "moral_score": result.moral_score,
            "date": result.publish_date,
            "source": result.source_name
        }
        for result in results
    ]


@router.get("/sources/{source_id}", response_model=Dict[str, Any])
def get_source(source_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific news source."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source with ID {source_id} not found")

    article_count = db.query(func.count(NewsArticle.id)).filter(
        NewsArticle.source_id == source_id
    ).scalar()

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


@router.get("/sources/{source_id}/sentiment", response_model=Dict[str, Any])
def get_source_sentiment(
    source_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Get sentiment data for a specific news source."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source with ID {source_id} not found")

    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=90)

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
