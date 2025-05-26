"""
Base classes and utilities for clustering module.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
import time
from functools import wraps

logger = logging.getLogger(__name__)


def log_timing(func):
    """Decorator to log function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        logger.info(f"{func.__name__} completed in {elapsed:.2f} seconds")
        return result
    return wrapper


class ClusterConfig:
    """Configuration for clustering operations."""
    
    # Similarity thresholds
    CLUSTER_SIMILARITY_THRESHOLD = 0.7
    MIN_CLUSTER_SIZE = 2
    
    # Tier definitions
    TIER1_SOURCES_PER_COUNTRY = 5
    MAX_SOURCES_PER_COUNTRY = 20
    MAX_SOURCES_TWO_COUNTRIES = 15
    
    # Time windows
    CLUSTERING_INTERVAL_DAYS = 30  # Monthly clustering
    SIMILARITY_WINDOW_DAYS = 7     # Weekly similarity computation
    
    # Performance limits
    MIN_ARTICLES_FOR_COMPARISON = 10
    MAX_ENTITIES_PER_SOURCE = 1000
    MIN_COMMON_ENTITIES = 5
    
    # Cache settings
    CACHE_TTL_CURRENT_WEEK = 3600      # 1 hour
    CACHE_TTL_HISTORICAL = 3600 * 24 * 7  # 1 week


class BaseAnalyzer:
    """Base class for all analyzers."""
    
    def __init__(self, session: Session):
        self.session = session
        self.config = ClusterConfig()
        
    def get_week_boundaries(self, date: datetime = None) -> Tuple[datetime, datetime]:
        """Get ISO week boundaries (Monday-Sunday)."""
        if date is None:
            date = datetime.utcnow()
            
        # Find the Monday of this week
        days_since_monday = date.weekday()
        monday = date - timedelta(days=days_since_monday)
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Sunday is 6 days later
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        return monday, sunday
    
    def get_active_sources(self, 
                          start_date: datetime, 
                          end_date: datetime,
                          country: Optional[str] = None,
                          min_articles: int = None) -> List[Dict]:
        """Get sources that published enough articles in the time window."""
        if min_articles is None:
            min_articles = self.config.MIN_ARTICLES_FOR_COMPARISON
            
        query = text("""
            SELECT 
                ns.id,
                ns.name,
                ns.country,
                COUNT(DISTINCT na.id) as article_count,
                COUNT(DISTINCT em.entity_id) as entity_count
            FROM news_sources ns
            JOIN news_articles na ON ns.id = na.source_id
            LEFT JOIN entity_mentions em ON na.id = em.article_id
            WHERE 
                na.publish_date BETWEEN :start_date AND :end_date
                AND (:country IS NULL OR ns.country = :country)
            GROUP BY ns.id, ns.name, ns.country
            HAVING COUNT(DISTINCT na.id) >= :min_articles
            ORDER BY COUNT(DISTINCT na.id) DESC
        """)
        
        results = self.session.execute(query, {
            'start_date': start_date,
            'end_date': end_date,
            'country': country,
            'min_articles': min_articles
        }).fetchall()
        
        return [
            {
                'id': row.id,
                'name': row.name,
                'country': row.country,
                'article_count': row.article_count,
                'entity_count': row.entity_count
            }
            for row in results
        ]
    
    def get_source_entity_vectors(self,
                                 source_ids: List[int],
                                 start_date: datetime,
                                 end_date: datetime) -> Dict[int, Dict[int, float]]:
        """Get entity sentiment vectors for multiple sources."""
        if not source_ids:
            return {}
            
        query = text("""
            SELECT 
                na.source_id,
                em.entity_id,
                AVG((em.power_score + em.moral_score) / 2.0) as avg_sentiment,
                COUNT(*) as mention_count
            FROM entity_mentions em
            JOIN news_articles na ON em.article_id = na.id
            WHERE 
                na.source_id = ANY(:source_ids)
                AND na.publish_date BETWEEN :start_date AND :end_date
                AND em.power_score IS NOT NULL
                AND em.moral_score IS NOT NULL
            GROUP BY na.source_id, em.entity_id
            HAVING COUNT(*) >= 2  -- At least 2 mentions for stability
        """)
        
        results = self.session.execute(query, {
            'source_ids': source_ids,
            'start_date': start_date,
            'end_date': end_date
        }).fetchall()
        
        # Build nested dict: source_id -> entity_id -> sentiment
        vectors = {}
        for row in results:
            if row.source_id not in vectors:
                vectors[row.source_id] = {}
            vectors[row.source_id][row.entity_id] = row.avg_sentiment
            
        return vectors
    
    def compute_pearson_correlation(self,
                                   vector1: Dict[int, float],
                                   vector2: Dict[int, float]) -> Optional[Tuple[float, int]]:
        """
        Compute Pearson correlation on common entities.
        
        Returns:
            Tuple of (correlation, common_entity_count) or None if insufficient data
        """
        # Find common entities
        common_entities = set(vector1.keys()) & set(vector2.keys())
        
        if len(common_entities) < self.config.MIN_COMMON_ENTITIES:
            return None
            
        # Extract aligned arrays
        values1 = np.array([vector1[entity] for entity in common_entities])
        values2 = np.array([vector2[entity] for entity in common_entities])
        
        # Check for zero variance
        if np.std(values1) == 0 or np.std(values2) == 0:
            return 0.0, len(common_entities)
            
        # Compute correlation
        correlation = np.corrcoef(values1, values2)[0, 1]
        
        return correlation, len(common_entities)