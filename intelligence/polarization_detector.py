"""
Polarization Detector

Detects increasing polarization in sentiment patterns across news sources.
Identifies entities and topics that are becoming more divisive over time.
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from sqlalchemy.orm import Session

# Import database connections
from database.db import get_session  
from database.models import NewsArticle, Entity, EntityMention, NewsSource
from .statistical_database.db_manager import StatisticalDBManager

logger = logging.getLogger(__name__)

class PolarizationDetector:
    """
    Detects increasing polarization in news sentiment patterns.
    
    Key principles:
    - Measures sentiment variance across sources for entities
    - Compares current variance to historical baseline
    - Identifies entities becoming more divisive over time
    - Focuses on entities with broad coverage for statistical significance
    - Uses bimodal distribution detection to identify true polarization
    """
    
    def __init__(self,
                 statistical_db: StatisticalDBManager,
                 baseline_weeks: int = 12,
                 current_weeks: int = 4,
                 significance_threshold: float = 0.01,
                 min_sources_per_entity: int = 8,
                 polarization_threshold: float = 1.5):  # Standard deviation increase
        self.statistical_db = statistical_db
        self.baseline_weeks = baseline_weeks
        self.current_weeks = current_weeks
        self.significance_threshold = significance_threshold
        self.min_sources_per_entity = min_sources_per_entity
        self.polarization_threshold = polarization_threshold
    
    def run_weekly_analysis(self, session: Session, target_week: datetime = None):
        """
        Run weekly polarization detection analysis.
        
        TODO: Implement the following steps:
        1. Get entities with broad source coverage
        2. Calculate sentiment variance across sources (current vs baseline)
        3. Detect bimodal distributions indicating polarization
        4. Test for statistical significance of increased polarization
        5. Store significant polarization findings
        """
        if target_week is None:
            target_week = datetime.utcnow()
        
        logger.info(f"Starting polarization detection for week of {target_week.date()}")
        
        # TODO: Calculate time windows
        current_end = target_week
        current_start = current_end - timedelta(weeks=self.current_weeks)
        baseline_end = current_start - timedelta(days=1)
        baseline_start = baseline_end - timedelta(weeks=self.baseline_weeks)
        
        # TODO: Get entities with sufficient source coverage
        entities = self._get_broadly_covered_entities(session, current_start, current_end)
        logger.info(f"Analyzing {len(entities)} entities for polarization")
        
        polarizations = []
        for entity in entities:
            # TODO: Analyze each entity for polarization
            polarization = self._analyze_entity_polarization(
                session, entity, 
                baseline_start, baseline_end,
                current_start, current_end
            )
            if polarization:
                polarizations.append(polarization)
        
        logger.info(f"Detected {len(polarizations)} significant polarization increases")
        return polarizations
    
    def _get_broadly_covered_entities(self, 
                                    session: Session, 
                                    start_date: datetime, 
                                    end_date: datetime) -> List[Dict]:
        """
        Get entities covered by many sources for polarization analysis.
        
        TODO: Implement query to get entities with:
        - Coverage by at least min_sources_per_entity sources
        - Sufficient mention count for statistical analysis
        - Ideally from multiple countries for global polarization detection
        
        Returns:
            List of entity dictionaries with id, name, type, source_count
        """
        # TODO: Implement database query
        # query = session.query(
        #     Entity.id, Entity.name, Entity.entity_type,
        #     func.count(distinct(NewsSource.id)).label('source_count'),
        #     func.count(EntityMention.id).label('mention_count')
        # ).join(EntityMention).join(NewsArticle).join(NewsSource)...
        
        # Placeholder return
        return []
    
    def _analyze_entity_polarization(self, 
                                   session: Session,
                                   entity: Dict,
                                   baseline_start: datetime,
                                   baseline_end: datetime,
                                   current_start: datetime,
                                   current_end: datetime) -> Optional[Dict]:
        """
        Analyze polarization for a specific entity.
        
        TODO: Implement the following:
        1. Get source sentiment distributions for baseline and current periods
        2. Calculate variance and bimodality metrics
        3. Test for significant increase in polarization
        4. Identify source clusters if polarized
        5. Create polarization finding if significant
        
        Returns:
            Polarization finding dictionary or None
        """
        entity_id = entity['id']
        entity_name = entity['name']
        
        # TODO: Get baseline sentiment distribution across sources
        baseline_sentiments = self._get_source_sentiment_distribution(
            session, entity_id, baseline_start, baseline_end
        )
        
        # TODO: Get current sentiment distribution across sources
        current_sentiments = self._get_source_sentiment_distribution(
            session, entity_id, current_start, current_end
        )
        
        if not baseline_sentiments or not current_sentiments:
            return None
        
        if len(baseline_sentiments) < self.min_sources_per_entity or \
           len(current_sentiments) < self.min_sources_per_entity:
            return None
        
        # TODO: Calculate polarization metrics
        baseline_variance = np.var(list(baseline_sentiments.values()))
        current_variance = np.var(list(current_sentiments.values()))
        
        variance_increase = current_variance - baseline_variance
        relative_increase = variance_increase / baseline_variance if baseline_variance > 0 else float('inf')
        
        # TODO: Test for statistical significance
        p_value = self._test_variance_increase(baseline_sentiments, current_sentiments)
        
        if p_value > self.significance_threshold or \
           relative_increase < self.polarization_threshold:
            return None
        
        # TODO: Detect bimodal distribution (true polarization vs just increased variance)
        bimodality_score = self._calculate_bimodality_score(list(current_sentiments.values()))
        
        # TODO: Identify polarized source clusters
        source_clusters = self._identify_polarized_clusters(current_sentiments)
        
        # TODO: Create polarization finding
        finding_id = self._create_polarization_finding(
            entity_id=entity_id,
            entity_name=entity_name,
            baseline_variance=baseline_variance,
            current_variance=current_variance,
            variance_increase=variance_increase,
            relative_increase=relative_increase,
            p_value=p_value,
            bimodality_score=bimodality_score,
            source_clusters=source_clusters,
            event_start=current_start,
            event_end=current_end
        )
        
        return {
            'finding_id': finding_id,
            'entity_id': entity_id,
            'entity_name': entity_name,
            'polarization_type': 'variance_increase',
            'variance_increase': variance_increase,
            'relative_increase': relative_increase,
            'p_value': p_value,
            'bimodality_score': bimodality_score,
            'source_clusters': source_clusters
        }
    
    def _get_source_sentiment_distribution(self, 
                                         session: Session,
                                         entity_id: int,
                                         start_date: datetime,
                                         end_date: datetime) -> Dict[int, float]:
        """
        Get sentiment distribution across sources for an entity.
        
        TODO: Implement query to get average sentiment per source for entity
        
        Returns:
            Dictionary mapping source_id -> average_sentiment
        """
        # TODO: Query source-level sentiment averages
        # query = session.query(
        #     NewsSource.id,
        #     func.avg((EntityMention.power_score + EntityMention.moral_score) / 2).label('avg_sentiment')
        # ).join(NewsArticle).join(EntityMention).filter(...)
        
        # Placeholder return
        return {}
    
    def _test_variance_increase(self, 
                              baseline_sentiments: Dict[int, float],
                              current_sentiments: Dict[int, float]) -> float:
        """
        Test if the increase in variance is statistically significant.
        
        TODO: Implement Levene's test or F-test for variance equality
        This tests whether the two groups have significantly different variances
        """
        baseline_values = list(baseline_sentiments.values())
        current_values = list(current_sentiments.values())
        
        # TODO: Use proper statistical test for variance difference
        # For now, use a simplified Levene's test
        try:
            statistic, p_value = stats.levene(baseline_values, current_values)
            return p_value
        except:
            return 1.0  # Unable to compute
    
    def _calculate_bimodality_score(self, sentiments: List[float]) -> float:
        """
        Calculate bimodality score to detect true polarization.
        
        TODO: Implement bimodality detection using:
        1. Hartigan's dip test for unimodality
        2. Or bimodality coefficient based on skewness and kurtosis
        3. Or simple gap detection in sentiment distribution
        
        Returns:
            Score from 0-1 where 1 indicates strong bimodality (polarization)
        """
        if len(sentiments) < 4:
            return 0.0
        
        # TODO: Implement proper bimodality test
        # For now, use a simplified approach based on distribution shape
        
        sentiments = np.array(sentiments)
        
        # Calculate bimodality coefficient (simplified)
        # BC = (skew^2 + 1) / (kurtosis + 3 * (n-1)^2 / ((n-2)*(n-3)))
        n = len(sentiments)
        if n < 4:
            return 0.0
        
        skewness = stats.skew(sentiments)
        kurt = stats.kurtosis(sentiments)
        
        # Simplified bimodality coefficient
        bc = (skewness**2 + 1) / (kurt + 3 * (n-1)**2 / ((n-2)*(n-3)))
        
        # Normalize to 0-1 scale (values > 0.555 suggest bimodality)
        bimodality_score = min(1.0, max(0.0, (bc - 0.3) / 0.5))
        
        return bimodality_score
    
    def _identify_polarized_clusters(self, source_sentiments: Dict[int, float]) -> List[Dict[str, Any]]:
        """
        Identify clusters of sources with similar sentiment (polarized groups).
        
        TODO: Implement clustering to identify polarized source groups:
        1. Use k-means or hierarchical clustering on sentiment values
        2. Identify 2-3 distinct clusters if they exist
        3. Return cluster information with source lists and centroids
        
        Returns:
            List of cluster dictionaries with source_ids, centroid, size
        """
        if len(source_sentiments) < 4:
            return []
        
        # TODO: Implement proper clustering
        # For now, use simple threshold-based clustering
        
        sentiments = list(source_sentiments.values())
        source_ids = list(source_sentiments.keys())
        
        # Simple approach: split at median and see if we get distinct groups
        median_sentiment = np.median(sentiments)
        
        positive_cluster = []
        negative_cluster = []
        
        for source_id, sentiment in source_sentiments.items():
            if sentiment > median_sentiment + 0.5:  # Threshold for positive cluster
                positive_cluster.append(source_id)
            elif sentiment < median_sentiment - 0.5:  # Threshold for negative cluster
                negative_cluster.append(source_id)
        
        clusters = []
        if len(positive_cluster) >= 2:
            positive_sentiments = [source_sentiments[sid] for sid in positive_cluster]
            clusters.append({
                'cluster_type': 'positive',
                'source_ids': positive_cluster,
                'centroid': np.mean(positive_sentiments),
                'size': len(positive_cluster)
            })
        
        if len(negative_cluster) >= 2:
            negative_sentiments = [source_sentiments[sid] for sid in negative_cluster]
            clusters.append({
                'cluster_type': 'negative',
                'source_ids': negative_cluster,
                'centroid': np.mean(negative_sentiments),
                'size': len(negative_cluster)
            })
        
        return clusters
    
    def _create_polarization_finding(self,
                                   entity_id: int,
                                   entity_name: str,
                                   baseline_variance: float,
                                   current_variance: float,
                                   variance_increase: float,
                                   relative_increase: float,
                                   p_value: float,
                                   bimodality_score: float,
                                   source_clusters: List[Dict],
                                   event_start: datetime,
                                   event_end: datetime) -> int:
        """
        Create a polarization finding for the dashboard.
        
        TODO: Create properly formatted finding and store in statistical database
        """
        # Determine polarization type and severity
        if bimodality_score > 0.7:
            polarization_type = "Strong Polarization"
            severity_desc = "sharply polarized"
        elif bimodality_score > 0.4:
            polarization_type = "Moderate Polarization"
            severity_desc = "increasingly polarized"
        else:
            polarization_type = "Increased Disagreement"
            severity_desc = "more divisive"
        
        # Create title and description
        title = f"{polarization_type}: {entity_name}"
        
        description = (f"Coverage of {entity_name} has become {severity_desc} across news sources. "
                      f"Sentiment variance increased by {relative_increase:.1%} "
                      f"(p={p_value:.4f})")
        
        if source_clusters and len(source_clusters) >= 2:
            cluster_desc = f". Sources split into {len(source_clusters)} distinct sentiment clusters"
            description += cluster_desc
        
        # Calculate severity score
        severity_score = min(1.0, (relative_increase / 3.0) + (bimodality_score / 2.0))
        
        # Create supporting data for dashboard
        supporting_data = {
            'baseline_variance': baseline_variance,
            'current_variance': current_variance,
            'variance_increase': variance_increase,
            'relative_increase': relative_increase,
            'bimodality_score': bimodality_score,
            'source_clusters': source_clusters,
            'chart_data': {
                'variance_timeline': [],  # TODO: Add historical variance timeline
                'sentiment_distribution': [],  # TODO: Add current sentiment distribution
                'cluster_visualization': source_clusters
            }
        }
        
        # Store finding
        finding_id = self.statistical_db.store_statistical_finding(
            finding_type='polarization',
            title=title,
            description=description,
            p_value=p_value,
            event_start_date=event_start,
            baseline_value=baseline_variance,
            current_value=current_variance,
            severity_score=severity_score,
            dashboard_category='polarization',
            entity_id=entity_id,
            event_end_date=event_end,
            change_magnitude=variance_increase,
            priority_score=severity_score,
            supporting_data=supporting_data
        )
        
        return finding_id
    
    def analyze_global_polarization_trends(self, session: Session, weeks_back: int = 24) -> Dict[str, Any]:
        """
        Analyze overall polarization trends across all entities and sources.
        
        TODO: Implement global polarization analysis:
        1. Calculate average polarization scores over time
        2. Identify entities with consistently high polarization
        3. Detect countries/regions with increasing polarization
        4. Generate summary statistics for dashboard overview
        
        Returns:
            Dictionary with global polarization metrics and trends
        """
        logger.info("Analyzing global polarization trends")
        
        # TODO: Implement global trend analysis
        # This would provide high-level insights for dashboard summary
        
        return {
            'overall_polarization_trend': 'increasing',  # TODO: Calculate actual trend
            'most_polarized_entities': [],  # TODO: Get top polarized entities
            'polarization_by_country': {},  # TODO: Calculate country-level polarization
            'weekly_trends': []  # TODO: Get weekly polarization scores
        }
    
    def get_entity_polarization_history(self, 
                                      session: Session,
                                      entity_id: int, 
                                      weeks_back: int = 12) -> Dict[str, Any]:
        """
        Get detailed polarization history for a specific entity.
        
        TODO: Implement entity-specific polarization timeline
        This could be used for dashboard drill-down or detailed analysis
        """
        # TODO: Implement entity polarization timeline
        # Show variance over time, key polarization events, source clusters, etc.
        
        logger.info(f"Getting polarization history for entity {entity_id}")
        
        return {
            'entity_id': entity_id,
            'weekly_variance': [],  # TODO: Get weekly variance scores
            'polarization_events': [],  # TODO: Get significant polarization increases
            'source_clusters_over_time': [],  # TODO: Track cluster evolution
            'trend_analysis': {}  # TODO: Statistical trend analysis
        }