"""
Statistical Endpoints Module

This module provides API endpoints for retrieving statistical data and visualizations
for the browser extension, including sentiment distributions and entity tracking.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Float, desc, case, and_
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging
import random
import math

# Import database utilities  
# Note: get_session is provided by main.py as get_db dependency
from database.models import Entity, EntityMention, NewsArticle, NewsSource

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class SentimentDistributionResponse(BaseModel):
    entity_name: str
    entity_type: str
    current_value: float
    values: List[float]
    comparison_data: Optional[Dict[str, List[float]]] = None
    comparison_label: Optional[str] = None
    sample_size: int
    source_count: int
    available_sources: Optional[List[Dict[str, Any]]] = None
    has_data: bool


def get_db_session():
    """Database session dependency - will be overridden by main.py"""
    pass

@router.get("/sentiment/distribution", response_model=SentimentDistributionResponse)
async def get_sentiment_distribution(
    entity_name: str,
    dimension: str = Query("power", regex="^(power|moral)$"),
    country: Optional[str] = None,
    source_id: Optional[int] = None,
    session: Session = Depends(get_db_session)
):
    """
    Get sentiment distribution data for a specific entity.
    
    This endpoint provides distribution data for visualizing how an entity's sentiment
    compares to the global or country-specific distribution.
    
    Args:
        entity_name: The name of the entity
        dimension: Whether to get power or moral dimension data
        country: Optional country to filter data by
        
    Returns:
        Distribution data with current value and comparison data
    """
    try:
        # Get the entity by name - prioritize by mention count to get the most relevant entity
        entity = session.query(Entity).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).filter(
            func.lower(Entity.name) == func.lower(entity_name)
        ).group_by(
            Entity.id, Entity.name, Entity.entity_type
        ).order_by(
            func.count(EntityMention.id).desc()
        ).first()
        
        if not entity:
            # Try fuzzy matching if exact match fails - also prioritize by mention count
            entity = session.query(Entity).join(
                EntityMention, Entity.id == EntityMention.entity_id
            ).filter(
                func.lower(Entity.name).like(f"%{entity_name.lower()}%")
            ).group_by(
                Entity.id, Entity.name, Entity.entity_type
            ).order_by(
                func.count(EntityMention.id).desc()
            ).first()
            
            # Also check for common variations
            if not entity and entity_name.lower() == "united states":
                # Try common variations - prioritize by mention count
                for variant in ["USA", "US", "U.S.", "U.S.A.", "America"]:
                    entity = session.query(Entity).join(
                        EntityMention, Entity.id == EntityMention.entity_id
                    ).filter(
                        func.lower(Entity.name) == func.lower(variant)
                    ).group_by(
                        Entity.id, Entity.name, Entity.entity_type
                    ).order_by(
                        func.count(EntityMention.id).desc()
                    ).first()
                    if entity:
                        logger.info(f"Found entity under variant name: {entity.name}")
                        break
        
        if not entity:
            # Entity not found in database - log available entities for debugging
            similar_entities = session.query(Entity.name, func.count(EntityMention.id).label('count')).join(
                EntityMention, Entity.id == EntityMention.entity_id
            ).filter(
                func.lower(Entity.name).like(f"%{entity_name.lower()[:3]}%")
            ).group_by(Entity.name).order_by(func.count(EntityMention.id).desc()).limit(10).all()
            
            logger.error(f"Entity '{entity_name}' not found. Similar entities: {[f'{name} ({count})' for name, count in similar_entities]}")
            raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found in database")
        
        logger.info(f"🔍 Found entity: {entity.name} (ID: {entity.id}, Type: {entity.entity_type})")
        
        # Get all mentions of this entity
        score_field = EntityMention.power_score if dimension == "power" else EntityMention.moral_score
        
        # Query for all mentions of this entity with the selected dimension
        mentions_query = session.query(score_field).filter(
            EntityMention.entity_id == entity.id,
            score_field.isnot(None)  # Ensure we only get mentions with valid scores
        )
        
        # Count total mentions
        total_mentions = mentions_query.count()
        
        # If we don't have enough data, return error
        min_mentions_required = 3  # Lowered from 5 to be more permissive
        if total_mentions < min_mentions_required:
            logger.error(f"Insufficient data for entity '{entity_name}' ({total_mentions} mentions).")
            raise HTTPException(status_code=400, detail=f"Insufficient data for entity '{entity_name}'. Only {total_mentions} mentions found, need at least {min_mentions_required}.")
        
        # Get all score values  
        values = [float(score[0]) for score in mentions_query.all()]
        
        # Get the most recent mention score as the current value
        most_recent = session.query(score_field, EntityMention.created_at).filter(
            EntityMention.entity_id == entity.id,
            score_field.isnot(None)
        ).order_by(
            EntityMention.created_at.desc()
        ).first()
        
        current_value = most_recent[0] if most_recent else values[0]
        
        # Get comparison data if requested
        comparison_data = None
        comparison_label = None
        
        # 1. Get source-specific data if requested
        if source_id:
            # Get the source information
            source = session.query(NewsSource).filter(NewsSource.id == source_id).first()
            
            source_mentions = session.query(score_field).join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).filter(
                EntityMention.entity_id == entity.id,
                NewsArticle.source_id == source_id,
                score_field.isnot(None)
            ).all()
            
            if source and len(source_mentions) >= 3:
                comparison_data = {
                    source.name: [float(score[0]) for score in source_mentions]
                }
                comparison_label = source.name
        
        # 2. Get country data if requested and no source data available
        elif country:
            logger.info(f"🔍 Filtering for country: '{country}' (entity: {entity_name}, dimension: {dimension})")
            
            # Debug: Check what countries are available in the database
            available_countries = session.query(func.distinct(NewsSource.country)).all()
            available_country_list = [c[0] for c in available_countries if c[0] is not None]
            logger.info(f"📍 Available countries in database: {available_country_list}")
            
            # Debug: Check sources for this entity
            entity_sources = session.query(
                NewsSource.name, NewsSource.country, func.count(EntityMention.id).label('mention_count')
            ).join(
                NewsArticle, NewsSource.id == NewsArticle.source_id
            ).join(
                EntityMention, NewsArticle.id == EntityMention.article_id
            ).filter(
                EntityMention.entity_id == entity.id,
                score_field.isnot(None)
            ).group_by(NewsSource.id, NewsSource.name, NewsSource.country).all()
            
            logger.info(f"📊 Sources with {entity_name} mentions:")
            for source_name, source_country, count in entity_sources:
                logger.info(f"  - {source_name} ({source_country}): {count} mentions")
            
            # Join with NewsArticle and NewsSource to filter by country
            country_mentions = session.query(score_field).join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).join(
                NewsSource, NewsArticle.source_id == NewsSource.id
            ).filter(
                EntityMention.entity_id == entity.id,
                score_field.isnot(None),
                func.lower(NewsSource.country) == func.lower(country)
            ).all()
            
            logger.info(f"🎯 Query result: Found {len(country_mentions)} country-specific mentions for '{country}'")
            
            # Debug: Show first few values
            if country_mentions:
                sample_values = [float(score[0]) for score in country_mentions[:5]]
                logger.info(f"📊 Sample values: {sample_values}")
            
            # Only include country data if we have enough values
            if len(country_mentions) >= 3:
                comparison_values = [float(score[0]) for score in country_mentions]
                comparison_data = {
                    country: comparison_values
                }
                comparison_label = country
                logger.info(f"✅ Created comparison data for '{country}' with {len(country_mentions)} mentions")
                logger.info(f"📊 Value range: {min(comparison_values):.2f} to {max(comparison_values):.2f}")
            else:
                logger.warning(f"❌ Insufficient country data for '{country}': only {len(country_mentions)} mentions (need 3+)")
                # Still return some comparison data but with a warning
                if len(country_mentions) > 0:
                    comparison_values = [float(score[0]) for score in country_mentions]
                    comparison_data = {
                        f"{country} (limited data)": comparison_values
                    }
                    comparison_label = f"{country} (limited data)"
        
        # Get the count of distinct news sources for this entity
        source_count = session.query(func.count(func.distinct(NewsSource.id))).join(
            NewsArticle, NewsSource.id == NewsArticle.source_id
        ).join(
            EntityMention, NewsArticle.id == EntityMention.article_id
        ).filter(
            EntityMention.entity_id == entity.id
        ).scalar() or 0
        
        # Get available sources for this entity to offer as comparison options
        available_sources = session.query(
            NewsSource.id,
            NewsSource.name,
            func.count(EntityMention.id).label('mention_count')
        ).join(
            NewsArticle, NewsSource.id == NewsArticle.source_id
        ).join(
            EntityMention, NewsArticle.id == EntityMention.article_id
        ).filter(
            EntityMention.entity_id == entity.id,
            score_field.isnot(None)
        ).group_by(
            NewsSource.id, 
            NewsSource.name
        ).having(
            func.count(EntityMention.id) >= 3  # Only include sources with enough data
        ).order_by(
            func.count(EntityMention.id).desc()
        ).limit(10).all()  # Get top 10 sources
        
        sources_list = [
            {"id": source.id, "name": source.name, "count": source.mention_count}
            for source in available_sources
        ]
        
        return SentimentDistributionResponse(
            entity_name=entity.name,
            entity_type=entity.entity_type or "unknown",
            current_value=float(current_value),
            values=values,
            comparison_data=comparison_data,
            comparison_label=comparison_label,
            sample_size=total_mentions,
            source_count=source_count,
            available_sources=sources_list,
            has_data=True
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (404, 400, etc.)
        raise
    except Exception as e:
        logger.error(f"Failed to get sentiment distribution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


class EntityTrackingResponse(BaseModel):
    entity_name: str
    entity_type: str
    data: List[Dict[str, Any]]  # Contains date, power_score, moral_score, confidence intervals
    has_data: bool
    limited_data: bool
    sample_size: int
    source_count: int
    time_period: str
    is_mock_data: bool


@router.get("/entity/tracking", response_model=EntityTrackingResponse)
async def get_entity_tracking(
    entity_name: str,
    days: int = Query(30, ge=1, le=365),
    window_size: int = Query(7, ge=1, le=30),
    source_id: Optional[int] = Query(None, description="Optional source ID to filter mentions"),
    session: Session = Depends(get_db_session)
):
    """
    Get entity sentiment tracking data over time.
    
    This endpoint provides time series data for visualizing how sentiment toward
    an entity has changed over time, using a sliding window average.
    
    Args:
        entity_name: The name of the entity to track
        days: Number of days to look back
        window_size: Size of the sliding window in days for averaging
        
    Returns:
        Time series data with sentiment values
    """
    try:
        # Get date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get the entity by name
        entity = session.query(Entity).filter(
            func.lower(Entity.name) == func.lower(entity_name)
        ).first()
        
        if not entity:
            # Try fuzzy matching if exact match fails
            entity = session.query(Entity).filter(
                func.lower(Entity.name).like(f"%{entity_name.lower()}%")
            ).first()
        
        if not entity:
            # Entity not found in database
            logger.error(f"Entity '{entity_name}' not found in database.")
            raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found in database")
        
        # Get entity mentions over the time period
        mentions_query = session.query(
            EntityMention.created_at,
            EntityMention.power_score,
            EntityMention.moral_score
        ).filter(
            EntityMention.entity_id == entity.id,
            EntityMention.created_at >= start_date,
            EntityMention.created_at <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )
        
        # If source_id is provided, filter to that specific source
        if source_id is not None:
            mentions_query = mentions_query.join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).filter(
                NewsArticle.source_id == source_id
            )
        
        mentions = mentions_query.order_by(
            EntityMention.created_at
        ).all()
        
        # Get global averages and standard deviations for this entity over the same time period
        global_avg_query = session.query(
            func.date(EntityMention.created_at).label('date'),
            func.avg(EntityMention.power_score).label('global_power_avg'),
            func.avg(EntityMention.moral_score).label('global_moral_avg'),
            func.stddev(EntityMention.power_score).label('global_power_std'),
            func.stddev(EntityMention.moral_score).label('global_moral_std'),
            func.count(EntityMention.id).label('count')
        ).filter(
            EntityMention.entity_id == entity.id,
            EntityMention.created_at >= start_date,
            EntityMention.created_at <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).group_by(
            func.date(EntityMention.created_at)
        ).all()
        
        # Convert to dict for easy lookup
        global_avgs_by_date = {
            row.date: {
                'power': float(row.global_power_avg),
                'moral': float(row.global_moral_avg),
                'power_std': float(row.global_power_std) if row.global_power_std else 0,
                'moral_std': float(row.global_moral_std) if row.global_moral_std else 0,
                'count': row.count
            }
            for row in global_avg_query
        }
        
        # Get the count of distinct news sources for this entity
        source_count_query = session.query(func.count(func.distinct(NewsSource.id))).join(
            NewsArticle, NewsSource.id == NewsArticle.source_id
        ).join(
            EntityMention, NewsArticle.id == EntityMention.article_id
        ).filter(
            EntityMention.entity_id == entity.id,
            EntityMention.created_at >= start_date,
            EntityMention.created_at <= end_date
        )
        
        # If source_id is provided, it's just 1 source
        if source_id is not None:
            source_count = 1
        else:
            source_count = source_count_query.scalar() or 0
        
        # If we don't have enough data, return error
        if len(mentions) < 5:
            logger.error(f"Insufficient tracking data for entity '{entity_name}' ({len(mentions)} mentions).")
            raise HTTPException(status_code=400, detail=f"Insufficient tracking data for entity '{entity_name}'. Only {len(mentions)} mentions found, need at least 5.")
        
        # Implementation of sliding window average
        tracking_data = calculate_sliding_window_average(
            mentions, 
            start_date, 
            end_date, 
            window_size,
            global_avgs_by_date
        )
        
        return EntityTrackingResponse(
            entity_name=entity.name,
            entity_type=entity.entity_type or "unknown",
            data=tracking_data,
            has_data=len(tracking_data) > 0,
            limited_data=len(mentions) < 20,
            sample_size=len(mentions),
            source_count=source_count,
            time_period=f"{days} days",
            is_mock_data=False
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (404, 400, etc.)
        raise
    except Exception as e:
        logger.error(f"Failed to get entity tracking data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


class TopicClusterResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]


@router.get("/topics/cluster", response_model=TopicClusterResponse)
async def get_topic_clusters(
    article_url: Optional[str] = None,
    view_type: str = Query("topics", regex="^(topics|entities)$"),
    threshold: str = Query("medium", regex="^(weak|medium|strong)$"),
    session: Session = Depends(get_db_session)
):
    """
    Get topic and entity relationship cluster data.
    
    This endpoint provides data for visualizing how topics and entities are related
    within an article or across the database.
    
    Args:
        article_url: Optional URL to get clusters for a specific article
        view_type: Whether to cluster by topics or entities
        threshold: Minimum relationship strength to include
        
    Returns:
        Nodes and links for network visualization
    """
    try:
        # Topic clustering not yet implemented with real data
        raise HTTPException(status_code=501, detail="Topic clustering feature not yet implemented")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get topic clusters: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Helper functions for data processing

def calculate_sliding_window_average(mentions, start_date, end_date, window_size, global_avgs_by_date=None):
    """
    Calculate sliding window average for entity sentiment tracking.
    
    Args:
        mentions: List of entity mentions with created_at, power_score, moral_score
        start_date: Start date for the time series
        end_date: End date for the time series
        window_size: Size of the sliding window in days
        global_avgs_by_date: Optional dict mapping dates to global averages
        
    Returns:
        List of data points with averaged scores
    """
    # Convert to list of dictionaries for easier manipulation
    mention_data = [
        {
            "date": mention.created_at,
            "power_score": float(mention.power_score) if mention.power_score is not None else 0.0,
            "moral_score": float(mention.moral_score) if mention.moral_score is not None else 0.0
        }
        for mention in mentions
    ]
    
    # If we have too few data points, just return them directly
    if len(mention_data) <= window_size:
        return sorted(mention_data, key=lambda x: x["date"])
    
    # Create a range of dates from start to end date
    current_date = start_date
    result = []
    
    # For each day in the range, create a window and average the scores
    while current_date <= end_date:
        window_start = current_date - timedelta(days=window_size)
        
        # Get mentions within the window
        window_mentions = [
            m for m in mention_data
            if window_start <= m["date"] <= current_date
        ]
        
        # Only include days that have data
        if window_mentions:
            # Calculate average scores
            power_scores = [m["power_score"] for m in window_mentions]
            moral_scores = [m["moral_score"] for m in window_mentions]
            
            avg_power = sum(power_scores) / len(power_scores)
            avg_moral = sum(moral_scores) / len(moral_scores)
            
            data_point = {
                "date": current_date.isoformat(),
                "power_score": avg_power,
                "moral_score": avg_moral,
                "count": len(window_mentions)  # Include count for reference
            }
            
            # Add global averages and confidence intervals if available
            if global_avgs_by_date and current_date.date() in global_avgs_by_date:
                global_avg = global_avgs_by_date[current_date.date()]
                data_point["global_power_avg"] = global_avg['power']
                data_point["global_moral_avg"] = global_avg['moral']
                
                # Calculate confidence intervals for global averages
                if global_avg['count'] > 1:
                    # 95% confidence interval = mean ± 1.96 * (std / sqrt(n))
                    power_ci = 1.96 * (global_avg['power_std'] / (global_avg['count'] ** 0.5))
                    moral_ci = 1.96 * (global_avg['moral_std'] / (global_avg['count'] ** 0.5))
                    
                    data_point["global_power_ci_lower"] = global_avg['power'] - power_ci
                    data_point["global_power_ci_upper"] = global_avg['power'] + power_ci
                    data_point["global_moral_ci_lower"] = global_avg['moral'] - moral_ci
                    data_point["global_moral_ci_upper"] = global_avg['moral'] + moral_ci
            
            result.append(data_point)
        
        # Move to next day
        current_date += timedelta(days=1)
    
    # If we have too many points, sample them to reduce data size
    if len(result) > 30:
        # Use step size to reduce points while maintaining overall trend
        step = len(result) // 30 + 1
        result = result[::step]
    
    return result


# No mock data - all responses come from real database data