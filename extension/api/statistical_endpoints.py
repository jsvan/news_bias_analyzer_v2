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
from database.db import get_session
from database.models import Entity, EntityMention, NewsArticle, NewsSource

# Import entity mapping utilities
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.entity_mapper import entity_mapper, normalize_entity_name, find_entity_variants

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


def find_entity_variants_in_db(entity_name: str, session: Session) -> List[Entity]:
    """
    Find all variants of an entity in the database using the entity mapper
    
    Args:
        entity_name: The entity name to search for
        session: Database session
        
    Returns:
        List of Entity objects that are variants of the same entity
    """
    try:
        if session is None:
            logger.error(f"Database session is None for entity '{entity_name}'")
            return []
            
        # Normalize the target entity name
        normalized_name = normalize_entity_name(entity_name)
        
        # Get all entities from database
        all_entities = session.query(Entity).all()
        
        # Convert to dict format for entity mapper
        entity_dicts = []
        for entity in all_entities:
            entity_dicts.append({
                'name': entity.name,
                'type': entity.entity_type,
                'id': entity.id,
                'entity_obj': entity  # Keep reference to original object
            })
        
        # Find variants using entity mapper
        variants = find_entity_variants(normalized_name, entity_dicts)
        
        # Extract the original Entity objects
        variant_entities = [v['entity_obj'] for v in variants]
        
        logger.info(f"🔍 Found {len(variant_entities)} entities for '{entity_name}', using '{normalized_name}' as representative")
        
        # Log the entities found
        for entity in variant_entities[:10]:  # Log first 10
            logger.info(f"  - {entity.name} ({entity.entity_type})")
        if len(variant_entities) > 10:
            logger.info(f"  ... and {len(variant_entities) - 10} more")
            
        return variant_entities
        
    except Exception as e:
        logger.error(f"Error finding entity variants for '{entity_name}': {str(e)}")
        return []

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

class AvailableCountriesResponse(BaseModel):
    entity_name: str
    countries: List[Dict[str, Any]]  # [{"code": "USA", "name": "United States", "sample_size": 123}]


# Database session dependency is now imported from database.db

@router.get("/sentiment/distribution", response_model=SentimentDistributionResponse)
async def get_sentiment_distribution(
    entity_name: str,
    dimension: str = Query("power", regex="^(power|moral)$"),
    country: Optional[str] = None,
    source_id: Optional[int] = None,
    half_life_days: float = Query(14.0, ge=1.0, le=365.0, description="Half-life for temporal weighting in days"),
    session: Session = Depends(get_session)
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
        # Create flexible entity matching patterns for common entities
        def get_entity_patterns(name):
            name_lower = name.lower().strip()
            patterns = [name_lower]  # Always include exact match
            
            if name_lower == "trump" or name_lower == "donald trump":
                patterns.extend(["trump", "donald trump", "president trump", "donald j. trump", "mr trump", "mr. trump"])
            elif name_lower == "russia":
                patterns.extend(["russia", "russian federation"])
            elif name_lower == "united states" or name_lower == "usa":
                patterns.extend(["united states", "usa", "us", "america"])
            elif name_lower == "china":
                patterns.extend(["china", "chinese"])
            elif name_lower == "iran":
                patterns.extend(["iran", "iranian"])
            elif name_lower == "putin" or name_lower == "vladimir putin":
                patterns.extend(["putin", "vladimir putin", "president putin"])
            elif name_lower == "ukraine":
                patterns.extend(["ukraine", "ukrainian"])
            elif name_lower == "biden" or name_lower == "joe biden":
                patterns.extend(["biden", "joe biden", "president biden"])
            
            return patterns
        
        # Get all matching entity IDs
        entity_patterns = get_entity_patterns(entity_name)
        entity_ids = []
        
        for pattern in entity_patterns:
            # Find entities that match this pattern
            matching_entities = session.query(Entity.id).filter(
                func.lower(Entity.name).like(f"%{pattern}%")
            ).all()
            entity_ids.extend([e.id for e in matching_entities])
        
        # Remove duplicates
        entity_ids = list(set(entity_ids))
        
        if not entity_ids:
            logger.error(f"No entities found for '{entity_name}' with patterns: {entity_patterns}")
            raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found in database")
        
        # Get a representative entity for metadata (pick the one with most mentions)
        representative_entity = session.query(Entity).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).filter(
            Entity.id.in_(entity_ids)
        ).group_by(
            Entity.id, Entity.name, Entity.entity_type
        ).order_by(
            func.count(EntityMention.id).desc()
        ).first()
        
        logger.info(f"🔍 Found {len(entity_ids)} entities for '{entity_name}', using '{representative_entity.name}' as representative")
        
        # Get all mentions of this entity
        score_field = EntityMention.power_score if dimension == "power" else EntityMention.moral_score
        
        # Query for all mentions across ALL matching entities with the selected dimension
        # Include created_at for temporal weighting
        mentions_query = session.query(score_field, EntityMention.created_at).filter(
            EntityMention.entity_id.in_(entity_ids),
            score_field.isnot(None)  # Ensure we only get mentions with valid scores
        )
        
        # Count total mentions
        total_mentions = mentions_query.count()
        
        # If we don't have enough data, return error
        min_mentions_required = 3  # Lowered from 5 to be more permissive
        if total_mentions < min_mentions_required:
            logger.error(f"Insufficient data for entity '{entity_name}' ({total_mentions} mentions across {len(entity_ids)} entity variants).")
            raise HTTPException(status_code=400, detail=f"Insufficient data for entity '{entity_name}'. Only {total_mentions} mentions found, need at least {min_mentions_required}.")
        
        # Get all score values with timestamps for temporal weighting
        mention_data = mentions_query.all()
        current_time = datetime.now()
        
        # Apply temporal weighting with exponential decay
        weighted_values = []
        for score, created_at in mention_data:
            if score is not None and created_at is not None:
                # Calculate days since creation
                days_old = (current_time - created_at).total_seconds() / (24 * 3600)
                
                # Exponential decay: weight = e^(-days_old / half_life)
                weight = math.exp(-days_old / half_life_days)
                
                # Add weighted copies of the value (round weight to avoid fractional repetition)
                # Use a multiplier to maintain reasonable sample sizes
                weighted_copies = max(1, round(weight * 10))  # Scale factor of 10
                weighted_values.extend([float(score)] * weighted_copies)
        
        values = weighted_values
        
        # Get the most recent mention score as the current value
        most_recent = session.query(score_field, EntityMention.created_at).filter(
            EntityMention.entity_id.in_(entity_ids),
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
            
            source_mentions = session.query(score_field, EntityMention.created_at).join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).filter(
                EntityMention.entity_id.in_(entity_ids),
                NewsArticle.source_id == source_id,
                score_field.isnot(None)
            ).all()
            
            if source and len(source_mentions) >= 3:
                # Apply temporal weighting to source data
                source_weighted_values = []
                for score, created_at in source_mentions:
                    if score is not None and created_at is not None:
                        days_old = (current_time - created_at).total_seconds() / (24 * 3600)
                        weight = math.exp(-days_old / half_life_days)
                        weighted_copies = max(1, round(weight * 10))
                        source_weighted_values.extend([float(score)] * weighted_copies)
                
                comparison_data = {
                    source.name: source_weighted_values
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
                EntityMention.entity_id.in_(entity_ids),
                score_field.isnot(None)
            ).group_by(NewsSource.id, NewsSource.name, NewsSource.country).all()
            
            logger.info(f"📊 Sources with {entity_name} mentions:")
            for source_name, source_country, count in entity_sources:
                logger.info(f"  - {source_name} ({source_country}): {count} mentions")
            
            # Join with NewsArticle and NewsSource to filter by country
            country_mentions = session.query(score_field, EntityMention.created_at).join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).join(
                NewsSource, NewsArticle.source_id == NewsSource.id
            ).filter(
                EntityMention.entity_id.in_(entity_ids),
                score_field.isnot(None),
                func.lower(NewsSource.country) == func.lower(country)
            ).all()
            
            logger.info(f"🎯 Query result: Found {len(country_mentions)} country-specific mentions for '{country}'")
            
            # Only include country data if we have enough values
            if len(country_mentions) >= 3:
                # Apply temporal weighting to country data
                country_weighted_values = []
                for score, created_at in country_mentions:
                    if score is not None and created_at is not None:
                        days_old = (current_time - created_at).total_seconds() / (24 * 3600)
                        weight = math.exp(-days_old / half_life_days)
                        weighted_copies = max(1, round(weight * 10))
                        country_weighted_values.extend([float(score)] * weighted_copies)
                
                comparison_data = {
                    country: country_weighted_values
                }
                comparison_label = country
                logger.info(f"✅ Created temporally weighted comparison data for '{country}' with {len(country_mentions)} raw mentions")
                if country_weighted_values:
                    logger.info(f"📊 Weighted value range: {min(country_weighted_values):.2f} to {max(country_weighted_values):.2f}")
            else:
                logger.warning(f"❌ Insufficient country data for '{country}': only {len(country_mentions)} mentions (need 3+)")
                # Still return some comparison data but with a warning
                if len(country_mentions) > 0:
                    country_weighted_values = []
                    for score, created_at in country_mentions:
                        if score is not None and created_at is not None:
                            days_old = (current_time - created_at).total_seconds() / (24 * 3600)
                            weight = math.exp(-days_old / half_life_days)
                            weighted_copies = max(1, round(weight * 10))
                            country_weighted_values.extend([float(score)] * weighted_copies)
                    
                    comparison_data = {
                        f"{country} (limited data)": country_weighted_values
                    }
                    comparison_label = f"{country} (limited data)"
        
        # Get the count of distinct news sources for this entity
        source_count = session.query(func.count(func.distinct(NewsSource.id))).join(
            NewsArticle, NewsSource.id == NewsArticle.source_id
        ).join(
            EntityMention, NewsArticle.id == EntityMention.article_id
        ).filter(
            EntityMention.entity_id.in_(entity_ids)
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
            EntityMention.entity_id.in_(entity_ids),
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
            entity_name=representative_entity.name,
            entity_type=representative_entity.entity_type or "unknown",
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
    session: Session = Depends(get_session)
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
        
        # Find all entity variants using entity mapper
        entity_variants = find_entity_variants_in_db(entity_name, session)
        
        if not entity_variants:
            # Entity not found in database
            logger.error(f"Entity '{entity_name}' not found in database.")
            raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found in database")
        
        # Use all variant entity IDs for querying mentions
        entity_ids = [entity.id for entity in entity_variants]
        
        # Get entity mentions over the time period
        mentions_query = session.query(
            EntityMention.created_at,
            EntityMention.power_score,
            EntityMention.moral_score
        ).filter(
            EntityMention.entity_id.in_(entity_ids),
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
        # If source_id is provided, exclude that source from global averages for true comparison
        global_avg_query = session.query(
            func.date(EntityMention.created_at).label('date'),
            func.avg(EntityMention.power_score).label('global_power_avg'),
            func.avg(EntityMention.moral_score).label('global_moral_avg'),
            func.stddev(EntityMention.power_score).label('global_power_std'),
            func.stddev(EntityMention.moral_score).label('global_moral_std'),
            func.count(EntityMention.id).label('count')
        ).filter(
            EntityMention.entity_id.in_(entity_ids),
            EntityMention.created_at >= start_date,
            EntityMention.created_at <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )
        
        # If source_id is provided, exclude that source from global averages
        if source_id is not None:
            global_avg_query = global_avg_query.join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).filter(
                NewsArticle.source_id != source_id
            )
        
        global_avg_query = global_avg_query.group_by(
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
            EntityMention.entity_id.in_(entity_ids),
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
        
        # Use the first entity variant for metadata
        primary_entity = entity_variants[0]
        normalized_name = normalize_entity_name(entity_name)
        
        return EntityTrackingResponse(
            entity_name=normalized_name,
            entity_type=primary_entity.entity_type or "unknown",
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
    session: Session = Depends(get_session)
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

@router.get("/entity/available-countries", response_model=AvailableCountriesResponse)
async def get_available_countries_for_entity(
    entity_name: str,
    dimension: str = Query("power", regex="^(power|moral)$"),
    min_mentions: int = Query(3, ge=1),
    session: Session = Depends(get_session)
):
    """
    Get countries that have sufficient data for distribution comparison for a specific entity.
    
    Args:
        entity_name: The name of the entity
        dimension: Which dimension to check (power or moral)
        min_mentions: Minimum number of mentions required per country
        
    Returns:
        List of countries with sufficient data for this entity
    """
    try:
        # Get score field based on dimension
        score_field = EntityMention.power_score if dimension == "power" else EntityMention.moral_score
        
        # Create flexible entity matching patterns for common entities
        def get_entity_patterns(name):
            name_lower = name.lower().strip()
            patterns = [name_lower]  # Always include exact match
            
            if name_lower == "trump" or name_lower == "donald trump":
                patterns.extend(["trump", "donald trump", "president trump", "donald j. trump", "mr trump", "mr. trump"])
            elif name_lower == "russia":
                patterns.extend(["russia", "russian federation"])
            elif name_lower == "united states" or name_lower == "usa":
                patterns.extend(["united states", "usa", "us", "america"])
            elif name_lower == "china":
                patterns.extend(["china", "chinese"])
            elif name_lower == "iran":
                patterns.extend(["iran", "iranian"])
            elif name_lower == "putin" or name_lower == "vladimir putin":
                patterns.extend(["putin", "vladimir putin", "president putin"])
            elif name_lower == "ukraine":
                patterns.extend(["ukraine", "ukrainian"])
            elif name_lower == "biden" or name_lower == "joe biden":
                patterns.extend(["biden", "joe biden", "president biden"])
            
            return patterns
        
        # Get all matching entity IDs
        entity_patterns = get_entity_patterns(entity_name)
        entity_ids = []
        
        for pattern in entity_patterns:
            # Find entities that match this pattern
            matching_entities = session.query(Entity.id).filter(
                func.lower(Entity.name).like(f"%{pattern}%")
            ).all()
            entity_ids.extend([e.id for e in matching_entities])
        
        # Remove duplicates
        entity_ids = list(set(entity_ids))
        
        if not entity_ids:
            logger.error(f"No entities found for '{entity_name}' with patterns: {entity_patterns}")
            return AvailableCountriesResponse(
                entity_name=entity_name,
                countries=[]
            )
        
        logger.info(f"🔍 Found {len(entity_ids)} matching entities for '{entity_name}': {entity_ids[:10]}...")
        
        # Query countries and their data counts across ALL matching entities
        countries_query = session.query(
            NewsSource.country,
            func.count(EntityMention.id).label('mention_count')
        ).join(
            NewsArticle, NewsSource.id == NewsArticle.source_id
        ).join(
            EntityMention, NewsArticle.id == EntityMention.article_id
        ).filter(
            EntityMention.entity_id.in_(entity_ids),
            NewsSource.country.isnot(None),
            score_field.isnot(None)
        ).group_by(
            NewsSource.country
        ).having(
            func.count(EntityMention.id) >= min_mentions
        ).order_by(
            func.count(EntityMention.id).desc()
        )
        
        # Debug: log the query info
        logger.info(f"🔍 Aggregating across {len(entity_ids)} entities for '{entity_name}' ({dimension} dimension)")
        
        countries_result = countries_query.all()
        logger.info(f"🔍 Query returned {len(countries_result)} rows")
        
        # Country code mapping for countries we support in the frontend
        country_mapping = {
            'USA': 'United States',
            'UK': 'United Kingdom', 
            'Canada': 'Canada',
            'Australia': 'Australia',
            'Germany': 'Germany',
            'France': 'France',
            'Japan': 'Japan',
            'Russia': 'Russia',
            'China': 'China',
            'India': 'India',
            'Singapore': 'Singapore',
            'Qatar': 'Qatar',
            'Hong Kong/China': 'Hong Kong',
            'Pakistan': 'Pakistan',
            'Turkey': 'Turkey',
            'UAE': 'UAE'
        }
        
        # Build response with countries that have sufficient data
        available_countries = []
        logger.info(f"🔍 Raw query results for entity '{entity_name}':")
        for country, mention_count in countries_result:
            logger.info(f"  - Country: '{country}', Mentions: {mention_count}")
            
            # Find matching country code
            country_code = None
            country_display_name = None
            
            # Check if it matches any of our supported countries
            for code, name in country_mapping.items():
                if country == code or country == name:
                    country_code = code
                    country_display_name = name
                    logger.info(f"  ✅ Matched '{country}' to code '{country_code}' name '{country_display_name}'")
                    break
            
            # Only include countries we support in the frontend
            if country_code and country_display_name:
                available_countries.append({
                    "code": country_code,
                    "name": country_display_name,
                    "sample_size": int(mention_count)
                })
            else:
                logger.info(f"  ❌ No mapping found for country '{country}'")
        
        logger.info(f"Found {len(available_countries)} countries with sufficient data for entity '{entity_name}' ({dimension} dimension)")
        
        return AvailableCountriesResponse(
            entity_name=entity_name,
            countries=available_countries
        )
        
    except Exception as e:
        logger.error(f"Failed to get available countries for entity: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/entity/global-counts")
def get_global_entity_counts(session: Session = Depends(get_session)):
    """Get global entity mention counts for ordering entities."""
    try:
        if session is None:
            logger.error("Database session is None for global entity counts")
            raise HTTPException(status_code=500, detail="Database connection not available")
            
        # Query to get mention counts for all entities
        entity_counts = session.query(
            Entity.name,
            func.count(EntityMention.id).label('count')
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id, isouter=True
        ).group_by(
            Entity.name
        ).all()
        
        # Convert to dictionary
        counts = {entity.name: entity.count or 0 for entity in entity_counts}
        
        return {"counts": counts}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get global entity counts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Response models for similar articles
class SimilarArticleEntity(BaseModel):
    name: str
    power_score: float
    moral_score: float

class SimilarArticleResponse(BaseModel):
    article_id: str
    url: str
    title: str
    source_name: str
    publish_date: datetime
    entities: List[SimilarArticleEntity]
    entity_overlap: float  # Jaccard similarity score
    sentiment_similarity: float  # Sentiment distance score
    global_sentiment_distance: float  # How far apart the articles are globally

class SimilarArticlesResponse(BaseModel):
    current_article_id: str
    similar_articles: List[SimilarArticleResponse]
    total_count: int

# Database dependency is now imported from database.db

@router.get("/article/{article_id}/similar", response_model=SimilarArticlesResponse)
def get_similar_articles(
    article_id: str,
    limit: int = Query(10, ge=1, le=50),
    days_window: int = Query(3, ge=1, le=7),
    min_entity_overlap: float = Query(0.3, ge=0.1, le=1.0),
    session: Session = Depends(get_session)
):
    """
    Find articles similar to the given article based on:
    1. Temporal proximity (same day ± days_window)
    2. Entity overlap (Jaccard similarity)
    3. Ordered by sentiment divergence (most different first)
    """
    try:
        if session is None:
            logger.error(f"Database session is None for article similarity search '{article_id}'")
            raise HTTPException(status_code=500, detail="Database connection not available")
        
        # Clean article ID - remove 'article_' prefix if present
        clean_article_id = article_id.replace('article_', '') if article_id.startswith('article_') else article_id
        logger.info(f"Looking for article with cleaned ID: {clean_article_id}")
            
        # Get the reference article
        ref_article = session.query(NewsArticle).filter(NewsArticle.id == clean_article_id).first()
        if not ref_article:
            raise HTTPException(status_code=404, detail=f"Article {clean_article_id} not found")
        
        # Get entities for the reference article
        ref_entities = session.query(EntityMention).filter(
            EntityMention.article_id == clean_article_id
        ).all()
        
        if not ref_entities:
            logger.warning(f"No entities found for article {clean_article_id}")
            return SimilarArticlesResponse(
                current_article_id=article_id,
                similar_articles=[],
                total_count=0
            )
        
        ref_entity_names = {e.entity.name.lower() for e in ref_entities}
        ref_entity_scores = {e.entity.name.lower(): (e.power_score, e.moral_score) for e in ref_entities}
        
        logger.info(f"Reference article {article_id} has {len(ref_entity_names)} entities: {list(ref_entity_names)[:5]}...")
        
        # Define time window
        if ref_article.publish_date:
            time_center = ref_article.publish_date
        else:
            time_center = ref_article.scraped_at or datetime.utcnow()
        
        time_start = time_center - timedelta(days=days_window)
        time_end = time_center + timedelta(days=days_window)
        
        # Find candidate articles in time window (exclude the reference article)
        candidate_articles = session.query(NewsArticle).filter(
            NewsArticle.id != clean_article_id,
            and_(
                NewsArticle.publish_date >= time_start,
                NewsArticle.publish_date <= time_end
            ) if ref_article.publish_date else and_(
                NewsArticle.scraped_at >= time_start,
                NewsArticle.scraped_at <= time_end
            )
        ).limit(1000).all()  # Reasonable limit for processing
        
        logger.info(f"Found {len(candidate_articles)} candidate articles in time window {time_start.date()} to {time_end.date()}")
        
        # Calculate similarity for each candidate
        similar_articles = []
        
        for candidate in candidate_articles:
            # Get entities for this candidate
            candidate_entities = session.query(EntityMention).filter(
                EntityMention.article_id == candidate.id
            ).all()
            
            if not candidate_entities:
                continue
                
            candidate_entity_names = {e.entity.name.lower() for e in candidate_entities}
            candidate_entity_scores = {e.entity.name.lower(): (e.power_score, e.moral_score) for e in candidate_entities}
            
            # Calculate Jaccard similarity for entity overlap
            intersection = len(ref_entity_names & candidate_entity_names)
            union = len(ref_entity_names | candidate_entity_names)
            jaccard_similarity = intersection / union if union > 0 else 0
            
            # Skip if not enough entity overlap
            if jaccard_similarity < min_entity_overlap:
                continue
            
            # Calculate sentiment similarity for overlapping entities
            overlapping_entities = ref_entity_names & candidate_entity_names
            if not overlapping_entities:
                continue
                
            sentiment_distances = []
            for entity_name in overlapping_entities:
                ref_power, ref_moral = ref_entity_scores[entity_name]
                cand_power, cand_moral = candidate_entity_scores[entity_name]
                
                # Euclidean distance in 2D sentiment space
                distance = math.sqrt((ref_power - cand_power)**2 + (ref_moral - cand_moral)**2)
                sentiment_distances.append(distance)
            
            avg_sentiment_distance = sum(sentiment_distances) / len(sentiment_distances)
            
            # Calculate global sentiment distance (average across all entities)
            ref_global_power = sum(scores[0] for scores in ref_entity_scores.values()) / len(ref_entity_scores)
            ref_global_moral = sum(scores[1] for scores in ref_entity_scores.values()) / len(ref_entity_scores)
            
            cand_global_power = sum(scores[0] for scores in candidate_entity_scores.values()) / len(candidate_entity_scores)
            cand_global_moral = sum(scores[1] for scores in candidate_entity_scores.values()) / len(candidate_entity_scores)
            
            global_sentiment_distance = math.sqrt(
                (ref_global_power - cand_global_power)**2 + (ref_global_moral - cand_global_moral)**2
            )
            
            # Format entities for response
            entities_response = [
                SimilarArticleEntity(
                    name=e.entity.name,
                    power_score=e.power_score,
                    moral_score=e.moral_score
                ) for e in candidate_entities
            ]
            
            similar_articles.append(SimilarArticleResponse(
                article_id=candidate.id,
                url=candidate.url or "",
                title=candidate.title or "Unknown Title",
                source_name=candidate.source.name if candidate.source else "Unknown Source",
                publish_date=candidate.publish_date or candidate.scraped_at,
                entities=entities_response,
                entity_overlap=jaccard_similarity,
                sentiment_similarity=avg_sentiment_distance,
                global_sentiment_distance=global_sentiment_distance
            ))
        
        # Sort by sentiment similarity (most different first) - this shows divergent coverage
        similar_articles.sort(key=lambda x: x.sentiment_similarity, reverse=True)
        
        # Limit results
        similar_articles = similar_articles[:limit]
        
        logger.info(f"Found {len(similar_articles)} similar articles for article {article_id}")
        
        return SimilarArticlesResponse(
            current_article_id=article_id,
            similar_articles=similar_articles,
            total_count=len(similar_articles)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar articles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to find similar articles: {str(e)}")


# Response models for country entity analysis
class CountryEntityData(BaseModel):
    entity_name: str
    entity_type: str
    mention_count: int
    avg_power_score: float
    avg_moral_score: float
    newspapers: Dict[str, List[Dict[str, Any]]]  # newspaper_name -> daily_data

class CountryTopEntitiesResponse(BaseModel):
    country: str
    entities: List[CountryEntityData]
    available_newspapers: List[str]
    time_period_days: int


@router.get("/country/{country}/top-entities", response_model=CountryTopEntitiesResponse)
async def get_country_top_entities(
    country: str,
    days: int = Query(30, ge=7, le=90, description="Number of days to look back"),
    limit: int = Query(10, ge=5, le=20, description="Number of top entities to return"),
    session: Session = Depends(get_session)
):
    """
    Get the top entities discussed by newspapers in a specific country over the past month,
    with sentiment flow data for each newspaper.
    
    This endpoint provides data for country-specific pages showing the most prominent 
    entities and their sentiment trajectories across different newspapers within that country.
    
    Args:
        country: The country to analyze (e.g., 'USA', 'UK', 'Germany')
        days: Number of days to look back (default: 30)
        limit: Number of top entities to return (default: 10)
        
    Returns:
        Top entities with their sentiment flows across newspapers in that country
    """
    try:
        if session is None:
            logger.error(f"Database session is None for country analysis '{country}'")
            raise HTTPException(status_code=500, detail="Database connection not available")
        
        logger.info(f"🔍 Getting top {limit} entities for country '{country}' over {days} days")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get all newspapers (sources) in this country
        country_sources = session.query(NewsSource).filter(
            func.lower(NewsSource.country) == func.lower(country)
        ).all()
        
        if not country_sources:
            logger.warning(f"No news sources found for country '{country}'")
            raise HTTPException(status_code=404, detail=f"No news sources found for country '{country}'")
        
        source_ids = [source.id for source in country_sources]
        source_names = {source.id: source.name for source in country_sources}
        
        logger.info(f"📰 Found {len(country_sources)} news sources in {country}: {list(source_names.values())}")
        
        # Get top entities by mention count in this country over the time period
        top_entities_query = session.query(
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
            NewsArticle.source_id.in_(source_ids),
            EntityMention.created_at >= start_date,
            EntityMention.created_at <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).group_by(
            Entity.id, Entity.name, Entity.entity_type
        ).having(
            func.count(EntityMention.id) >= 5  # Minimum mentions required
        ).order_by(
            func.count(EntityMention.id).desc()
        ).limit(limit)
        
        top_entities = top_entities_query.all()
        
        if not top_entities:
            logger.warning(f"No entities found with sufficient mentions for country '{country}'")
            return CountryTopEntitiesResponse(
                country=country,
                entities=[],
                available_newspapers=list(source_names.values()),
                time_period_days=days
            )
        
        logger.info(f"📊 Found {len(top_entities)} top entities for {country}")
        
        # For each top entity, get daily sentiment data by newspaper
        entities_data = []
        
        for entity_id, entity_name, entity_type, total_mentions, avg_power, avg_moral in top_entities:
            logger.info(f"🔍 Processing entity '{entity_name}' ({total_mentions} mentions)")
            
            # Get daily sentiment data for this entity, grouped by source (newspaper)
            daily_data_query = session.query(
                func.date(EntityMention.created_at).label('date'),
                NewsArticle.source_id,
                func.avg(EntityMention.power_score).label('avg_power'),
                func.avg(EntityMention.moral_score).label('avg_moral'),
                func.count(EntityMention.id).label('mention_count')
            ).join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).filter(
                EntityMention.entity_id == entity_id,
                NewsArticle.source_id.in_(source_ids),
                EntityMention.created_at >= start_date,
                EntityMention.created_at <= end_date,
                EntityMention.power_score.isnot(None),
                EntityMention.moral_score.isnot(None)
            ).group_by(
                func.date(EntityMention.created_at),
                NewsArticle.source_id
            ).order_by(
                func.date(EntityMention.created_at),
                NewsArticle.source_id
            )
            
            daily_results = daily_data_query.all()
            
            # Group data by newspaper
            newspapers_data = {}
            for date, source_id, power_avg, moral_avg, mentions in daily_results:
                newspaper_name = source_names.get(source_id, f"Unknown Source {source_id}")
                
                if newspaper_name not in newspapers_data:
                    newspapers_data[newspaper_name] = []
                
                newspapers_data[newspaper_name].append({
                    "date": date.isoformat(),
                    "power_score": float(power_avg) if power_avg is not None else 0.0,
                    "moral_score": float(moral_avg) if moral_avg is not None else 0.0,
                    "mention_count": int(mentions)
                })
            
            # Sort each newspaper's data by date
            for newspaper_name in newspapers_data:
                newspapers_data[newspaper_name].sort(key=lambda x: x["date"])
            
            entities_data.append(CountryEntityData(
                entity_name=entity_name,
                entity_type=entity_type or "unknown",
                mention_count=int(total_mentions),
                avg_power_score=float(avg_power) if avg_power is not None else 0.0,
                avg_moral_score=float(avg_moral) if avg_moral is not None else 0.0,
                newspapers=newspapers_data
            ))
        
        logger.info(f"✅ Successfully processed {len(entities_data)} entities for country {country}")
        
        return CountryTopEntitiesResponse(
            country=country,
            entities=entities_data,
            available_newspapers=list(source_names.values()),
            time_period_days=days
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get top entities for country {country}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")