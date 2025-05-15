from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np

from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention, NewsSource
from analysis.statistical_models import SentimentDistribution, HierarchicalSentimentModel

# Router for statistical analysis endpoints
router = APIRouter(prefix="/stats", tags=["statistics"])

# Get hierarchical sentiment model configured with data from DB
def get_hierarchical_model(db: Session) -> HierarchicalSentimentModel:
    """
    Create and initialize hierarchical sentiment model with data from database.
    
    This is cached for performance in a production environment.
    """
    # For real application, this would be cached
    model = HierarchicalSentimentModel()
    
    # Get the last 90 days of data
    cutoff_date = datetime.utcnow() - timedelta(days=90)
    
    # Get entity mentions
    mentions = db.query(
        Entity.name,
        Entity.entity_type,
        EntityMention.power_score,
        EntityMention.moral_score,
        NewsSource.name.label("source_name"),
        NewsSource.country
    ).join(
        EntityMention, Entity.id == EntityMention.entity_id
    ).join(
        NewsArticle, EntityMention.article_id == NewsArticle.id
    ).join(
        NewsSource, NewsArticle.source_id == NewsSource.id
    ).filter(
        NewsArticle.publish_date >= cutoff_date
    ).all()
    
    # Load data into model
    for mention in mentions:
        model.add_entity_observation(
            entity_name=mention.name,
            entity_type=mention.entity_type,
            power_score=mention.power_score,
            moral_score=mention.moral_score,
            source=mention.source_name,
            country=mention.country
        )
    
    return model


@router.post("/analyze_article", response_model=Dict[str, Any])
async def analyze_article_sentiment(
    article_data: Dict[str, Any],
    db: Session = Depends(get_hierarchical_model)
):
    """
    Analyze an article's sentiment patterns against global and national distributions.
    
    The article_data should contain:
    - source: name of the news source
    - country: country of the news source
    - entities: list of entity objects with name, type, power_score, moral_score
    """
    model = get_hierarchical_model(db)
    
    source = article_data.get("source", "unknown")
    country = article_data.get("country", "unknown")
    entities = article_data.get("entities", [])
    
    if not entities:
        raise HTTPException(status_code=400, detail="No entities provided for analysis")
    
    # Analyze each entity
    entity_results = []
    for entity in entities:
        result = model.analyze_entity_sentiment(
            entity_name=entity["name"],
            entity_type=entity["type"],
            power_score=entity["power_score"],
            moral_score=entity["moral_score"],
            source=source,
            country=country
        )
        entity_results.append(result)
    
    # Calculate composite score
    composite_score = model.calculate_composite_score(entity_results)
    
    return {
        "article": {
            "source": source,
            "country": country,
            "title": article_data.get("title", ""),
            "url": article_data.get("url", "")
        },
        "entities": entity_results,
        "composite_score": composite_score
    }


@router.get("/entity_distribution/{entity_id}", response_model=Dict[str, Any])
async def get_entity_distribution(
    entity_id: int,
    country: Optional[str] = None,
    source_id: Optional[int] = None,
    db: Session = Depends(get_hierarchical_model)
):
    """
    Get the sentiment distribution data for a specific entity.
    
    This endpoint returns the distribution parameters and visualization data
    for the entity's sentiment across different reference groups.
    """
    # Get entity from database
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity with ID {entity_id} not found")
    
    model = get_hierarchical_model(db)
    
    # Get source country if source_id is provided
    source_country = None
    source_name = None
    if source_id:
        source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
        if source:
            source_country = source.country
            source_name = source.name
    
    # Get global distribution
    global_dist = model.get_entity_global_distribution(entity.name, entity.entity_type)
    
    # Get national distribution if country is provided
    national_dist = None
    if country:
        national_dist = model.get_entity_national_distribution(
            entity.name, entity.entity_type, country
        )
    
    # Get source distribution if source_id is provided
    source_dist = None
    if source_id and source_name and source_country:
        source_dist = model.get_entity_source_distribution(
            entity.name, entity.entity_type, source_name, source_country
        )
    
    # Prepare response
    result = {
        "entity": {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type
        },
        "distributions": {}
    }
    
    # Add global distribution
    if global_dist:
        result["distributions"]["global"] = {
            "power": {
                "mean": global_dist.power_mean,
                "std": global_dist.power_std,
                "count": global_dist.count,
                "pdf": global_dist.get_pdf_data("power")
            },
            "moral": {
                "mean": global_dist.moral_mean,
                "std": global_dist.moral_std,
                "count": global_dist.count,
                "pdf": global_dist.get_pdf_data("moral")
            }
        }
    
    # Add national distribution
    if national_dist:
        result["distributions"]["national"] = {
            "country": country,
            "power": {
                "mean": national_dist.power_mean,
                "std": national_dist.power_std,
                "count": national_dist.count,
                "pdf": national_dist.get_pdf_data("power")
            },
            "moral": {
                "mean": national_dist.moral_mean,
                "std": national_dist.moral_std,
                "count": national_dist.count,
                "pdf": national_dist.get_pdf_data("moral")
            }
        }
    
    # Add source distribution
    if source_dist:
        result["distributions"]["source"] = {
            "source_id": source_id,
            "source_name": source_name,
            "power": {
                "mean": source_dist.power_mean,
                "std": source_dist.power_std,
                "count": source_dist.count,
                "pdf": source_dist.get_pdf_data("power")
            },
            "moral": {
                "mean": source_dist.moral_mean,
                "std": source_dist.moral_std,
                "count": source_dist.count,
                "pdf": source_dist.get_pdf_data("moral")
            }
        }
    
    return result


@router.get("/bias_distribution", response_model=Dict[str, Any])
async def get_bias_distribution(
    country: Optional[str] = None,
    db: Session = Depends(get_hierarchical_model)
):
    """
    Get the overall bias distribution across news sources.
    
    This endpoint returns a visualization of how different news sources 
    tend to portray entities on average, allowing users to see which 
    sources are outliers in their sentiment patterns.
    """
    # This would integrate with the hierarchical model to provide
    # a visualization of the bias distribution across sources
    
    # For now, return a placeholder
    return {
        "message": "Bias distribution analysis endpoint (placeholder)"
    }