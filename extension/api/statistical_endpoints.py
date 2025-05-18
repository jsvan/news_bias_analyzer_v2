"""
Statistical Endpoints Module

This module provides API endpoints for retrieving statistical data and visualizations
for the browser extension, including sentiment distributions and entity tracking.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
from pydantic import BaseModel
import numpy as np

# Import database utilities (adjust imports as needed)
from database.db import get_session
from database.models import Entity, EntityMention, NewsArticle

router = APIRouter()

class SentimentDistributionResponse(BaseModel):
    entity_name: str
    entity_type: str
    current_value: float
    values: List[float]
    country_data: Optional[Dict[str, List[float]]] = None
    sample_size: int
    source_count: int


@router.get("/sentiment/distribution", response_model=SentimentDistributionResponse)
async def get_sentiment_distribution(
    entity_name: str,
    dimension: str = Query("power", regex="^(power|moral)$"),
    country: Optional[str] = None,
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
        # In a real implementation, you would:
        # 1. Query for the entity in the database
        # 2. Get all mentions of this entity
        # 3. Calculate distribution statistics
        # 4. Return properly formatted data
        
        # For demo purposes, generate mock data
        current_value = random.uniform(-1.5, 1.5)
        
        # Create a normal-ish distribution around a mean value
        mean = random.uniform(-0.5, 0.5)
        std_dev = random.uniform(0.5, 1.0)
        
        # Generate distribution values
        values = []
        for _ in range(100):
            # Base value from normal distribution
            value = np.random.normal(mean, std_dev)
            # Clamp to -2 to 2 range
            value = max(-2, min(2, value))
            values.append(value)
        
        # Create country-specific data if requested
        country_data = None
        if country:
            country_data = {
                country: [
                    max(-2, min(2, np.random.normal(mean + 0.3, std_dev * 0.8)))
                    for _ in range(50)
                ]
            }
        
        return SentimentDistributionResponse(
            entity_name=entity_name,
            entity_type=get_mock_entity_type(entity_name),
            current_value=current_value,
            values=values,
            country_data=country_data,
            sample_size=len(values),
            source_count=random.randint(10, 40)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sentiment distribution: {str(e)}")


class EntityTrackingResponse(BaseModel):
    entity_name: str
    entity_type: str
    data: List[Dict[str, Any]]  # Contains date, power_score, moral_score


@router.get("/entity/tracking", response_model=EntityTrackingResponse)
async def get_entity_tracking(
    entity_name: str,
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session)
):
    """
    Get entity sentiment tracking data over time.
    
    This endpoint provides time series data for visualizing how sentiment toward
    an entity has changed over time.
    
    Args:
        entity_name: The name of the entity to track
        days: Number of days to look back
        
    Returns:
        Time series data with sentiment values
    """
    try:
        # Get date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # In a real implementation, you would:
        # 1. Query for the entity in the database
        # 2. Get mentions over the time period
        # 3. Aggregate by day/week
        # 4. Return the time series
        
        # For demo purposes, generate mock data
        tracking_data = generate_mock_tracking_data(entity_name, days)
        
        return EntityTrackingResponse(
            entity_name=entity_name,
            entity_type=get_mock_entity_type(entity_name),
            data=tracking_data
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get entity tracking data: {str(e)}")


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
        # In a real implementation, you would:
        # 1. Query for topics/entities based on parameters
        # 2. Calculate relationship strengths
        # 3. Create network visualization data
        
        # For demo purposes, generate mock data
        return generate_mock_topic_clusters(view_type, threshold, article_url)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get topic clusters: {str(e)}")


# Helper functions for generating mock data

def get_mock_entity_type(entity_name):
    """Guess entity type based on name."""
    entity_name = entity_name.lower()
    
    country_keywords = ['america', 'china', 'russia', 'united states', 'france', 'germany', 'japan']
    org_keywords = ['company', 'corp', 'inc', 'organization', 'united nations', 'who', 'nato']
    party_keywords = ['party', 'republican', 'democrat', 'labour', 'conservative']
    
    if any(keyword in entity_name for keyword in country_keywords):
        return 'country'
    elif any(keyword in entity_name for keyword in org_keywords):
        return 'organization'
    elif any(keyword in entity_name for keyword in party_keywords):
        return 'political_party'
    else:
        return 'person'  # Default assumption


def generate_mock_tracking_data(entity_name, days):
    """Generate mock time series data for entity tracking."""
    end_date = datetime.now()
    
    # Create a base trend direction
    trend_power = random.choice([-0.02, -0.01, 0, 0.01, 0.02])
    trend_moral = random.choice([-0.02, -0.01, 0, 0.01, 0.02])
    
    # Start with a random sentiment in the middle range
    base_power = random.uniform(-0.5, 0.5)
    base_moral = random.uniform(-0.5, 0.5)
    
    # Generate daily data points
    tracking_data = []
    for day in range(days):
        # Calculate date
        current_date = end_date - timedelta(days=days-day-1)
        
        # Calculate sentiment with trend and some random variation
        power_score = base_power + (trend_power * day) + random.uniform(-0.3, 0.3)
        moral_score = base_moral + (trend_moral * day) + random.uniform(-0.3, 0.3)
        
        # Clamp values to -2 to 2 range
        power_score = max(-2, min(2, power_score))
        moral_score = max(-2, min(2, moral_score))
        
        # Add data point
        tracking_data.append({
            "date": current_date.isoformat(),
            "power_score": power_score,
            "moral_score": moral_score
        })
    
    return tracking_data


def generate_mock_topic_clusters(view_type, threshold, article_url=None):
    """Generate mock topic cluster data for visualization."""
    # Number of nodes based on threshold
    node_counts = {
        "weak": 15,
        "medium": 10,
        "strong": 6
    }
    
    # Topic or entity names based on view type
    node_names = {
        "topics": [
            "Politics", "Economics", "Foreign Policy", "Climate", 
            "Healthcare", "Technology", "Education", "Military", 
            "Immigration", "Trade", "Social Issues", "Energy",
            "Transportation", "Housing", "Agriculture"
        ],
        "entities": [
            "Joe Biden", "Donald Trump", "United States", "China", 
            "Russia", "European Union", "United Nations", "Congress",
            "Federal Reserve", "Republican Party", "Democratic Party", 
            "NATO", "World Health Organization", "Supreme Court", "Pentagon"
        ]
    }
    
    # Create nodes based on type and threshold
    nodes = []
    num_nodes = min(node_counts[threshold], len(node_names[view_type]))
    
    for i in range(num_nodes):
        node_type = "topic" if view_type == "topics" else "entity"
        entity_type = "" if view_type == "topics" else get_mock_entity_type(node_names[view_type][i])
        
        nodes.append({
            "id": f"{node_type}_{i}",
            "label": node_names[view_type][i],
            "type": node_type,
            "entity_type": entity_type,
            "count": random.randint(3, 20),
            "cluster": random.randint(0, 2),
            "size": 1.0 + random.random()
        })
    
    # Create links between nodes
    links = []
    link_density = {
        "weak": 0.4,
        "medium": 0.3,
        "strong": 0.2
    }
    
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            # Probability of link based on threshold
            if random.random() < link_density[threshold]:
                # Stronger weight for nodes in same cluster
                weight = 0.3 + (0.7 * random.random())
                if nodes[i]["cluster"] == nodes[j]["cluster"]:
                    weight += 0.2
                
                links.append({
                    "source": nodes[i]["id"],
                    "target": nodes[j]["id"],
                    "weight": weight,
                    "value": weight
                })
    
    return {
        "nodes": nodes,
        "links": links
    }