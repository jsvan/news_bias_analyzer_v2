"""
Hotelling's T² computation for article extremeness.

This module implements the statistical test to measure how extreme an article's
sentiment pattern is compared to the global weekly distribution.
"""

import numpy as np
from scipy import stats
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.models import Entity, EntityMention

logger = logging.getLogger(__name__)


class HotellingT2Calculator:
    """Calculate Hotelling's T² statistic for article sentiment patterns."""
    
    def __init__(self, session: Session):
        self.session = session
        self._stats_cache = {}
    
    def calculate_article_t2(self, article_entities: List[Dict]) -> Optional[float]:
        """
        Calculate Hotelling's T² statistic for an article.
        
        Args:
            article_entities: List of dicts with entity_id, power_score, moral_score
            
        Returns:
            T² statistic or None if insufficient data
        """
        if len(article_entities) < 2:
            logger.warning("Need at least 2 entities to calculate T² statistic")
            return None
        
        # Get entity IDs
        entity_ids = [e['entity_id'] for e in article_entities]
        
        # Get weekly statistics for these entities
        stats = self._get_weekly_stats(entity_ids)
        if not stats:
            logger.warning("No weekly statistics available for entities")
            return None
        
        # Build observation vector (2n dimensional: power and moral for each entity)
        X = []
        mu = []
        available_entities = []
        
        for entity in article_entities:
            entity_id = entity['entity_id']
            if entity_id in stats:
                X.extend([entity['power_score'], entity['moral_score']])
                mu.extend([stats[entity_id]['mean_power'], stats[entity_id]['mean_moral']])
                available_entities.append(entity_id)
        
        if len(available_entities) < 2:
            logger.warning("Insufficient entities with statistics")
            return None
        
        # Convert to numpy arrays
        X = np.array(X)
        mu = np.array(mu)
        
        # Build covariance matrix
        cov_matrix = self._build_covariance_matrix(available_entities, stats)
        
        try:
            # Calculate T² statistic
            diff = X - mu
            cov_inv = np.linalg.inv(cov_matrix)
            t2 = diff.T @ cov_inv @ diff
            
            return float(t2)
            
        except np.linalg.LinAlgError:
            logger.error("Covariance matrix is singular, cannot compute T²")
            return None
    
    def _get_weekly_stats(self, entity_ids: List[int]) -> Dict[int, Dict]:
        """
        Get weekly sentiment statistics for entities.
        
        Returns dict mapping entity_id to stats dict.
        """
        # Check cache first
        cache_key = tuple(sorted(entity_ids))
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]
        
        # Query from weekly_sentiment_stats table
        week_start = (datetime.utcnow() - timedelta(days=7)).date()
        
        query = text("""
            SELECT 
                entity_id,
                mean_power,
                mean_moral,
                variance_power,
                variance_moral,
                covariance,
                sample_count
            FROM weekly_sentiment_stats
            WHERE entity_id = ANY(:entity_ids)
                AND week_start >= :week_start
            ORDER BY week_start DESC
        """)
        
        results = self.session.execute(
            query,
            {"entity_ids": entity_ids, "week_start": week_start}
        ).fetchall()
        
        # Group by entity_id and take most recent stats
        stats = {}
        for row in results:
            entity_id = row.entity_id
            if entity_id not in stats:
                stats[entity_id] = {
                    'mean_power': row.mean_power,
                    'mean_moral': row.mean_moral,
                    'variance_power': row.variance_power,
                    'variance_moral': row.variance_moral,
                    'covariance': row.covariance,
                    'sample_count': row.sample_count
                }
        
        # Cache for this request
        self._stats_cache[cache_key] = stats
        
        return stats
    
    def _build_covariance_matrix(self, entity_ids: List[int], stats: Dict) -> np.ndarray:
        """
        Build the covariance matrix for the multivariate distribution.
        
        For simplicity, we assume independence between entities and use
        the individual entity covariances as 2x2 blocks on the diagonal.
        """
        n = len(entity_ids)
        cov_matrix = np.zeros((2*n, 2*n))
        
        for i, entity_id in enumerate(entity_ids):
            entity_stats = stats[entity_id]
            
            # Fill in the 2x2 block for this entity
            row_start = 2*i
            cov_matrix[row_start, row_start] = entity_stats['variance_power']
            cov_matrix[row_start, row_start+1] = entity_stats['covariance']
            cov_matrix[row_start+1, row_start] = entity_stats['covariance']
            cov_matrix[row_start+1, row_start+1] = entity_stats['variance_moral']
        
        # Add small regularization to ensure positive definite
        cov_matrix += np.eye(2*n) * 1e-6
        
        return cov_matrix


def update_weekly_statistics(session: Session) -> int:
    """
    Update the weekly_sentiment_stats table with current data.
    This should be run hourly by the scheduler.
    
    Returns:
        Number of entity statistics updated
    """
    logger.info("Updating weekly sentiment statistics")
    
    # Calculate stats for the past 7 days
    query = text("""
        INSERT INTO weekly_sentiment_stats (
            entity_id, week_start, mean_power, mean_moral, 
            variance_power, variance_moral, covariance, sample_count
        )
        SELECT 
            em.entity_id,
            CURRENT_DATE - INTERVAL '7 days' as week_start,
            AVG(em.power_score) as mean_power,
            AVG(em.moral_score) as mean_moral,
            VAR_SAMP(em.power_score) as variance_power,
            VAR_SAMP(em.moral_score) as variance_moral,
            COVAR_SAMP(em.power_score, em.moral_score) as covariance,
            COUNT(*) as sample_count
        FROM entity_mentions em
        JOIN news_articles na ON em.article_id = na.id
        WHERE na.processed_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
        GROUP BY em.entity_id
        HAVING COUNT(*) >= 5  -- Need at least 5 observations
        ON CONFLICT (entity_id, week_start) 
        DO UPDATE SET
            mean_power = EXCLUDED.mean_power,
            mean_moral = EXCLUDED.mean_moral,
            variance_power = EXCLUDED.variance_power,
            variance_moral = EXCLUDED.variance_moral,
            covariance = EXCLUDED.covariance,
            sample_count = EXCLUDED.sample_count,
            updated_at = NOW()
    """)
    
    result = session.execute(query)
    session.commit()
    
    count = result.rowcount
    logger.info(f"Updated statistics for {count} entities")
    
    # Clean up old statistics (older than 14 days)
    cleanup_query = text("""
        DELETE FROM weekly_sentiment_stats
        WHERE week_start < CURRENT_DATE - INTERVAL '14 days'
    """)
    
    cleanup_result = session.execute(cleanup_query)
    session.commit()
    
    if cleanup_result.rowcount > 0:
        logger.info(f"Cleaned up {cleanup_result.rowcount} old statistics entries")
    
    return count