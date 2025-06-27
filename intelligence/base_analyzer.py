"""
Base Intelligence Analyzer

Provides common functionality for all intelligence analysis modules.
Implements shared patterns for data access, statistical computations, and result storage.
"""

import logging
import numpy as np
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from database.models import NewsArticle, Entity, EntityMention, NewsSource
from statistical_database.db_manager import StatisticalDBManager

logger = logging.getLogger(__name__)

class BaseIntelligenceAnalyzer(ABC):
    """
    Base class for all intelligence analyzers.
    
    Provides:
    - Common time window calculations
    - Standardized database access patterns
    - Statistical utility functions
    - Result storage patterns
    - Error handling and logging
    """
    
    def __init__(self, 
                 session: Session,
                 statistical_db: StatisticalDBManager,
                 min_mentions_threshold: int = 10,
                 min_sources_threshold: int = 3,
                 significance_threshold: float = 0.01):
        """
        Initialize base analyzer.
        
        Args:
            session: Database session for main database
            statistical_db: Statistical database manager
            min_mentions_threshold: Minimum mentions for statistical significance
            min_sources_threshold: Minimum sources for analysis
            significance_threshold: P-value threshold for significance
        """
        self.session = session
        self.statistical_db = statistical_db
        self.min_mentions_threshold = min_mentions_threshold
        self.min_sources_threshold = min_sources_threshold
        self.significance_threshold = significance_threshold
        
        # Cache for expensive queries
        self._entity_cache = {}
        self._source_cache = {}
        self._sentiment_cache = {}
    
    @abstractmethod
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis method that each analyzer must implement.
        
        Returns:
            List of analysis findings
        """
        pass
    
    def get_week_boundaries(self, date: datetime) -> Tuple[datetime, datetime]:
        """
        Get ISO week boundaries (Monday-Sunday).
        
        Args:
            date: Reference date
            
        Returns:
            Tuple of (week_start, week_end)
        """
        days_since_monday = date.weekday()
        monday = date - timedelta(days=days_since_monday)
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return monday, sunday
    
    def get_active_entities(self, 
                           start_date: datetime, 
                           end_date: datetime,
                           min_mentions: int = None,
                           min_sources: int = None) -> List[Dict[str, Any]]:
        """
        Get entities with sufficient activity for analysis.
        
        Args:
            start_date: Period start
            end_date: Period end  
            min_mentions: Override default mention threshold
            min_sources: Override default source threshold
            
        Returns:
            List of entity dictionaries with metadata
        """
        cache_key = f"entities_{start_date.date()}_{end_date.date()}_{min_mentions}_{min_sources}"
        if cache_key in self._entity_cache:
            return self._entity_cache[cache_key]
        
        min_mentions = min_mentions or self.min_mentions_threshold
        min_sources = min_sources or self.min_sources_threshold
        
        query = self.session.query(
            Entity.id,
            Entity.name,
            Entity.entity_type,
            func.count(EntityMention.id).label('mention_count'),
            func.count(func.distinct(NewsArticle.source_id)).label('source_count'),
            func.avg((EntityMention.power_score + EntityMention.moral_score) / 2.0).label('avg_sentiment')
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            NewsArticle.publish_date >= start_date,
            NewsArticle.publish_date <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).group_by(
            Entity.id, Entity.name, Entity.entity_type
        ).having(
            func.count(EntityMention.id) >= min_mentions,
            func.count(func.distinct(NewsArticle.source_id)) >= min_sources
        ).order_by(
            func.count(EntityMention.id).desc()
        )
        
        entities = []
        for row in query.all():
            entity_data = {
                'id': row.id,
                'name': row.name,
                'type': row.entity_type,
                'mention_count': row.mention_count,
                'source_count': row.source_count,
                'avg_sentiment': float(row.avg_sentiment) if row.avg_sentiment else 0.0
            }
            entities.append(entity_data)
        
        self._entity_cache[cache_key] = entities
        return entities
    
    def get_active_sources(self, 
                          start_date: datetime, 
                          end_date: datetime,
                          min_articles: int = 10,
                          country_filter: str = None) -> List[Dict[str, Any]]:
        """
        Get sources with sufficient activity for analysis.
        
        Args:
            start_date: Period start
            end_date: Period end
            min_articles: Minimum articles published
            country_filter: Optional country filter
            
        Returns:
            List of source dictionaries with metadata
        """
        cache_key = f"sources_{start_date.date()}_{end_date.date()}_{min_articles}_{country_filter}"
        if cache_key in self._source_cache:
            return self._source_cache[cache_key]
        
        query = self.session.query(
            NewsSource.id,
            NewsSource.name,
            NewsSource.country,
            func.count(NewsArticle.id).label('article_count'),
            func.count(func.distinct(EntityMention.entity_id)).label('entity_count')
        ).join(
            NewsArticle, NewsSource.id == NewsArticle.source_id
        ).outerjoin(
            EntityMention, NewsArticle.id == EntityMention.article_id
        ).filter(
            NewsArticle.publish_date >= start_date,
            NewsArticle.publish_date <= end_date
        )
        
        if country_filter:
            query = query.filter(NewsSource.country == country_filter)
        
        query = query.group_by(
            NewsSource.id, NewsSource.name, NewsSource.country
        ).having(
            func.count(NewsArticle.id) >= min_articles
        ).order_by(
            func.count(NewsArticle.id).desc()
        )
        
        sources = []
        for row in query.all():
            source_data = {
                'id': row.id,
                'name': row.name,
                'country': row.country,
                'article_count': row.article_count,
                'entity_count': row.entity_count or 0
            }
            sources.append(source_data)
        
        self._source_cache[cache_key] = sources
        return sources
    
    def get_entity_sentiment_by_source(self, 
                                      entity_id: int,
                                      start_date: datetime,
                                      end_date: datetime) -> Dict[int, float]:
        """
        Get entity sentiment aggregated by source.
        
        Args:
            entity_id: Entity to analyze
            start_date: Period start
            end_date: Period end
            
        Returns:
            Dictionary mapping source_id -> average_sentiment
        """
        cache_key = f"sentiment_{entity_id}_{start_date.date()}_{end_date.date()}"
        if cache_key in self._sentiment_cache:
            return self._sentiment_cache[cache_key]
        
        query = self.session.query(
            NewsArticle.source_id,
            func.avg((EntityMention.power_score + EntityMention.moral_score) / 2.0).label('avg_sentiment'),
            func.count(EntityMention.id).label('mention_count')
        ).join(
            EntityMention, NewsArticle.id == EntityMention.article_id
        ).filter(
            EntityMention.entity_id == entity_id,
            NewsArticle.publish_date >= start_date,
            NewsArticle.publish_date <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).group_by(
            NewsArticle.source_id
        ).having(
            func.count(EntityMention.id) >= 3  # At least 3 mentions per source
        )
        
        sentiment_by_source = {}
        for row in query.all():
            sentiment_by_source[row.source_id] = float(row.avg_sentiment)
        
        self._sentiment_cache[cache_key] = sentiment_by_source
        return sentiment_by_source
    
    def get_entity_sentiment_vector(self,
                                   source_id: int,
                                   start_date: datetime,
                                   end_date: datetime,
                                   entity_filter: List[int] = None) -> Dict[int, float]:
        """
        Get sentiment vector for a source across multiple entities.
        
        Args:
            source_id: Source to analyze
            start_date: Period start
            end_date: Period end
            entity_filter: Optional list of entity IDs to include
            
        Returns:
            Dictionary mapping entity_id -> average_sentiment
        """
        query = self.session.query(
            EntityMention.entity_id,
            func.avg((EntityMention.power_score + EntityMention.moral_score) / 2.0).label('avg_sentiment')
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            NewsArticle.source_id == source_id,
            NewsArticle.publish_date >= start_date,
            NewsArticle.publish_date <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )
        
        if entity_filter:
            query = query.filter(EntityMention.entity_id.in_(entity_filter))
        
        query = query.group_by(EntityMention.entity_id)
        
        sentiment_vector = {}
        for row in query.all():
            sentiment_vector[row.entity_id] = float(row.avg_sentiment)
        
        return sentiment_vector
    
    def calculate_z_score(self, value: float, baseline_mean: float, baseline_std: float) -> float:
        """Calculate z-score for anomaly detection."""
        if baseline_std == 0:
            return 0.0
        return (value - baseline_mean) / baseline_std
    
    def calculate_p_value_two_tailed(self, z_score: float) -> float:
        """Calculate two-tailed p-value from z-score."""
        return 2 * (1 - stats.norm.cdf(abs(z_score)))
    
    def test_variance_equality(self, sample1: List[float], sample2: List[float]) -> Tuple[float, float]:
        """
        Test if two samples have equal variance using Levene's test.
        
        Returns:
            Tuple of (test_statistic, p_value)
        """
        try:
            return stats.levene(sample1, sample2)
        except Exception as e:
            logger.warning(f"Variance test failed: {e}")
            return 0.0, 1.0
    
    def calculate_correlation(self, 
                            vector1: Dict[int, float], 
                            vector2: Dict[int, float],
                            min_common: int = 5) -> Optional[Dict[str, Any]]:
        """
        Calculate Pearson correlation between two vectors.
        
        Args:
            vector1: First vector (entity_id -> value)
            vector2: Second vector (entity_id -> value)
            min_common: Minimum common keys required
            
        Returns:
            Dictionary with correlation stats or None
        """
        common_keys = set(vector1.keys()) & set(vector2.keys())
        
        if len(common_keys) < min_common:
            return None
        
        values1 = [vector1[k] for k in common_keys]
        values2 = [vector2[k] for k in common_keys]
        
        try:
            correlation, p_value = stats.pearsonr(values1, values2)
            return {
                'correlation': correlation,
                'p_value': p_value,
                'common_entities': len(common_keys),
                'sample_size': len(values1)
            }
        except Exception as e:
            logger.warning(f"Correlation calculation failed: {e}")
            return None
    
    def store_finding(self,
                     finding_type: str,
                     title: str,
                     description: str,
                     p_value: float,
                     severity_score: float,
                     event_start: datetime,
                     baseline_value: float = None,
                     current_value: float = None,
                     **kwargs) -> int:
        """
        Store a statistical finding with consistent formatting.
        
        Args:
            finding_type: Type of analysis finding
            title: Human-readable title
            description: Detailed description
            p_value: Statistical significance
            severity_score: Severity from 0-1
            event_start: When the event started
            baseline_value: Baseline comparison value
            current_value: Current observed value
            **kwargs: Additional finding-specific data
            
        Returns:
            Finding ID
        """
        # Determine dashboard category from finding type
        category_map = {
            'sentiment_anomaly': 'anomaly',
            'source_divergence': 'divergence', 
            'polarization': 'polarization',
            'clustering_insight': 'clustering'
        }
        dashboard_category = category_map.get(finding_type, 'other')
        
        # Calculate priority score based on severity and significance
        priority_score = severity_score * (1 - p_value) if p_value < 1 else severity_score
        
        return self.statistical_db.store_statistical_finding(
            finding_type=finding_type,
            title=title,
            description=description,
            p_value=p_value,
            event_start_date=event_start,
            baseline_value=baseline_value,
            current_value=current_value,
            severity_score=severity_score,
            priority_score=priority_score,
            dashboard_category=dashboard_category,
            **kwargs
        )
    
    def clear_caches(self):
        """Clear internal caches to free memory."""
        self._entity_cache.clear()
        self._source_cache.clear()
        self._sentiment_cache.clear()
        
    def log_analysis_start(self, analysis_name: str, target_date: datetime = None):
        """Log the start of an analysis with consistent formatting."""
        target_date = target_date or datetime.utcnow()
        logger.info(f"Starting {analysis_name} analysis for {target_date.date()}")
    
    def log_analysis_complete(self, analysis_name: str, findings_count: int, duration: float):
        """Log the completion of an analysis with consistent formatting."""
        logger.info(f"Completed {analysis_name} analysis: {findings_count} findings in {duration:.2f}s")