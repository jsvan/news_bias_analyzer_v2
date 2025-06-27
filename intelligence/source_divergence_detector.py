"""
Source Divergence Detector

Detects when news sources that historically moved together begin to diverge on sentiment,
indicating potential editorial shifts or emerging polarization around specific topics.
"""

import logging
import numpy as np
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from scipy.stats import pearsonr
from sqlalchemy.orm import Session

from database.models import NewsArticle, Entity, EntityMention, NewsSource
from statistical_database.db_manager import StatisticalDBManager
from intelligence.base_analyzer import BaseIntelligenceAnalyzer

logger = logging.getLogger(__name__)

class SourceDivergenceDetector(BaseIntelligenceAnalyzer):
    """
    Detects when sources that historically had similar sentiment patterns begin to diverge.
    
    Key principles:
    - Uses correlation analysis to measure similarity/divergence
    - Compares recent correlation vs historical baseline correlation
    - Focuses on source pairs that had strong historical correlation (>0.7)
    - Requires significant change in correlation with p-value < 0.01
    - Identifies specific entities driving the divergence
    """
    
    def __init__(self,
                 session: Session,
                 statistical_db: StatisticalDBManager,
                 historical_weeks: int = 24,  # 6 months of historical data
                 recent_weeks: int = 4,       # 1 month of recent data
                 min_historical_correlation: float = 0.6,
                 min_divergence_magnitude: float = 0.25):
        super().__init__(
            session=session,
            statistical_db=statistical_db,
            min_mentions_threshold=20,
            min_sources_threshold=2,  # Only need 2 sources for correlation
            significance_threshold=0.01
        )
        self.historical_weeks = historical_weeks
        self.recent_weeks = recent_weeks
        self.min_historical_correlation = min_historical_correlation
        self.min_divergence_magnitude = min_divergence_magnitude
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis entry point for the orchestrator.
        
        Returns:
            List of divergence findings
        """
        start_time = time.time()
        target_week = datetime.utcnow()
        self.log_analysis_start("source divergence", target_week)
        
        try:
            findings = self._run_divergence_detection(target_week)
            duration = time.time() - start_time
            self.log_analysis_complete("source divergence", len(findings), duration)
            return findings
        except Exception as e:
            logger.error(f"Source divergence analysis failed: {e}")
            return []
        finally:
            self.clear_caches()
    
    def _run_divergence_detection(self, target_week: datetime) -> List[Dict[str, Any]]:
        """
        Run source divergence analysis for the given week.
        
        Steps:
        1. Get time periods (historical vs recent)
        2. Get sources with sufficient activity
        3. Find historically correlated source pairs
        4. Calculate recent correlations and test for divergence
        5. Store significant divergences
        """
        # Get time boundaries
        recent_end = target_week
        recent_start = recent_end - timedelta(weeks=self.recent_weeks)
        historical_end = recent_start - timedelta(days=1)
        historical_start = historical_end - timedelta(weeks=self.historical_weeks)
        
        # Get sources with sufficient activity in both periods
        historical_sources = self.get_active_sources(historical_start, historical_end, min_articles=50)
        recent_sources = self.get_active_sources(recent_start, recent_end, min_articles=10)
        
        # Find sources active in both periods
        historical_source_ids = {s['id'] for s in historical_sources}
        recent_source_ids = {s['id'] for s in recent_sources}
        common_source_ids = historical_source_ids & recent_source_ids
        
        if len(common_source_ids) < 3:
            logger.warning("Not enough active sources for divergence analysis")
            return []
        
        # Get common entities for correlation analysis
        common_entities = self._get_common_entities(
            list(common_source_ids), historical_start, recent_end
        )
        
        if len(common_entities) < 15:
            logger.warning("Not enough common entities for reliable correlation analysis")
            return []
        
        logger.info(f"Analyzing {len(common_source_ids)} sources across {len(common_entities)} entities")
        
        # Find historically correlated source pairs and test for divergence
        findings = []
        source_pairs = self._get_source_pairs(list(common_source_ids))
        
        for source1_id, source2_id in source_pairs:
            divergence = self._analyze_pair_divergence(
                source1_id, source2_id, common_entities,
                historical_start, historical_end, recent_start, recent_end
            )
            if divergence:
                findings.append(divergence)
        
        return findings
    
    def _get_common_entities(self, 
                            source_ids: List[int], 
                            start_date: datetime, 
                            end_date: datetime) -> List[int]:
        """
        Get entities covered by multiple sources for correlation analysis.
        
        Args:
            source_ids: List of source IDs to check
            start_date: Start of time period
            end_date: End of time period
            
        Returns:
            List of entity IDs covered by at least 2 sources
        """
        from sqlalchemy import func
        
        # Find entities mentioned by multiple sources
        query = self.session.query(
            EntityMention.entity_id,
            func.count(func.distinct(NewsArticle.source_id)).label('source_count')
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            NewsArticle.source_id.in_(source_ids),
            NewsArticle.publish_date >= start_date,
            NewsArticle.publish_date <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).group_by(
            EntityMention.entity_id
        ).having(
            func.count(func.distinct(NewsArticle.source_id)) >= 2,
            func.count(EntityMention.id) >= 10  # At least 10 mentions total
        ).order_by(
            func.count(func.distinct(NewsArticle.source_id)).desc()
        ).limit(50)  # Top 50 entities for efficiency
        
        return [row.entity_id for row in query.all()]
    
    def _get_source_pairs(self, source_ids: List[int]) -> List[Tuple[int, int]]:
        """
        Generate all possible pairs of sources for correlation analysis.
        
        Args:
            source_ids: List of source IDs
            
        Returns:
            List of (source1_id, source2_id) tuples
        """
        pairs = []
        for i, source1_id in enumerate(source_ids):
            for source2_id in source_ids[i+1:]:
                pairs.append((source1_id, source2_id))
        return pairs[:50]  # Limit to 50 pairs for performance
    
    def _analyze_pair_divergence(self,
                                source1_id: int,
                                source2_id: int,
                                common_entities: List[int],
                                historical_start: datetime,
                                historical_end: datetime,
                                recent_start: datetime,
                                recent_end: datetime) -> Optional[Dict[str, Any]]:
        """
        Analyze a specific source pair for divergence.
        
        Args:
            source1_id: First source ID
            source2_id: Second source ID
            common_entities: List of entity IDs to analyze
            historical_start: Start of historical period
            historical_end: End of historical period
            recent_start: Start of recent period
            recent_end: End of recent period
            
        Returns:
            Divergence finding dictionary or None
        """
        # Get sentiment vectors for both periods
        hist_vector1 = self.get_entity_sentiment_vector(
            source1_id, historical_start, historical_end, common_entities
        )
        hist_vector2 = self.get_entity_sentiment_vector(
            source2_id, historical_start, historical_end, common_entities
        )
        
        recent_vector1 = self.get_entity_sentiment_vector(
            source1_id, recent_start, recent_end, common_entities
        )
        recent_vector2 = self.get_entity_sentiment_vector(
            source2_id, recent_start, recent_end, common_entities
        )
        
        # Calculate correlations
        historical_corr = self.calculate_correlation(hist_vector1, hist_vector2, min_common=8)
        recent_corr = self.calculate_correlation(recent_vector1, recent_vector2, min_common=8)
        
        if not historical_corr or not recent_corr:
            return None
        
        # Check if historical correlation was strong enough
        if historical_corr['correlation'] < self.min_historical_correlation:
            return None
        
        # Calculate divergence magnitude
        divergence_magnitude = abs(historical_corr['correlation'] - recent_corr['correlation'])
        
        if divergence_magnitude < self.min_divergence_magnitude:
            return None
        
        # Simple statistical test for correlation change
        p_value = self._test_correlation_change(historical_corr, recent_corr)
        
        if p_value > self.significance_threshold:
            return None
        
        # Get source names for display
        source1_name = self._get_source_name(source1_id)
        source2_name = self._get_source_name(source2_id)
        
        # Identify top divergent entities
        divergent_entities = self._identify_divergent_entities(
            recent_vector1, recent_vector2, common_entities
        )
        
        # Store divergence in statistical database
        self.statistical_db.store_source_divergence(
            source_id_1=source1_id,
            source_id_2=source2_id,
            historical_correlation=historical_corr['correlation'],
            historical_window_start=historical_start,
            historical_window_end=historical_end,
            recent_correlation=recent_corr['correlation'],
            recent_window_start=recent_start,
            recent_window_end=recent_end,
            divergence_p_value=p_value,
            divergence_magnitude=divergence_magnitude,
            top_divergent_entities=divergent_entities,
            is_significant=True
        )
        
        # Create finding for dashboard
        finding_id = self._create_divergence_finding(
            source1_id, source1_name, source2_id, source2_name,
            historical_corr, recent_corr, divergence_magnitude, p_value,
            divergent_entities, recent_start, recent_end
        )
        
        return {
            'finding_id': finding_id,
            'source1_id': source1_id,
            'source1_name': source1_name,
            'source2_id': source2_id,
            'source2_name': source2_name,
            'historical_correlation': historical_corr['correlation'],
            'recent_correlation': recent_corr['correlation'],
            'divergence_magnitude': divergence_magnitude,
            'p_value': p_value,
            'divergent_entities': divergent_entities
        }
    
    def _get_source_name(self, source_id: int) -> str:
        """Get source name for display purposes."""
        source = self.session.query(NewsSource).filter(NewsSource.id == source_id).first()
        return source.name if source else f"Source {source_id}"
    
    def _test_correlation_change(self, 
                                historical_corr: Dict[str, Any], 
                                recent_corr: Dict[str, Any]) -> float:
        """
        Test if the change in correlation is statistically significant.
        
        Uses a simplified approach based on sample sizes and correlation difference.
        """
        n1 = historical_corr['sample_size']
        n2 = recent_corr['sample_size']
        
        if n1 < 8 or n2 < 8:
            return 1.0  # Not enough data
        
        # Simplified statistical test based on correlation difference
        r1 = historical_corr['correlation']
        r2 = recent_corr['correlation']
        
        # Fisher's z-transformation (simplified)
        z1 = 0.5 * np.log((1 + r1) / (1 - r1)) if abs(r1) < 0.99 else 0
        z2 = 0.5 * np.log((1 + r2) / (1 - r2)) if abs(r2) < 0.99 else 0
        
        se = np.sqrt(1/(n1-3) + 1/(n2-3))
        z_stat = abs(z1 - z2) / se if se > 0 else 0
        
        # Two-tailed p-value
        p_value = 2 * (1 - stats.norm.cdf(z_stat)) if z_stat > 0 else 1.0
        
        return min(1.0, p_value)
    
    def _identify_divergent_entities(self,
                                   vector1: Dict[int, float],
                                   vector2: Dict[int, float],
                                   entity_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Identify entities with the largest sentiment differences between sources.
        
        Args:
            vector1: Sentiment vector for source 1
            vector2: Sentiment vector for source 2
            entity_ids: List of entity IDs to consider
            
        Returns:
            List of entities with divergence information
        """
        divergent_entities = []
        
        for entity_id in entity_ids:
            if entity_id in vector1 and entity_id in vector2:
                sentiment_diff = abs(vector1[entity_id] - vector2[entity_id])
                
                # Get entity name
                entity = self.session.query(Entity).filter(Entity.id == entity_id).first()
                entity_name = entity.name if entity else f"Entity {entity_id}"
                
                divergent_entities.append({
                    'entity_id': entity_id,
                    'entity_name': entity_name,
                    'sentiment_difference': sentiment_diff,
                    'source1_sentiment': vector1[entity_id],
                    'source2_sentiment': vector2[entity_id]
                })
        
        # Sort by divergence magnitude and return top entities
        divergent_entities.sort(key=lambda x: x['sentiment_difference'], reverse=True)
        return divergent_entities[:5]  # Top 5 divergent entities
    
    def _create_divergence_finding(self,
                                 source1_id: int,
                                 source1_name: str,
                                 source2_id: int,
                                 source2_name: str,
                                 historical_corr: Dict[str, Any],
                                 recent_corr: Dict[str, Any],
                                 divergence_magnitude: float,
                                 p_value: float,
                                 divergent_entities: List[Dict[str, Any]],
                                 event_start: datetime,
                                 event_end: datetime) -> int:
        """
        Create a divergence finding for the dashboard.
        
        Returns:
            Finding ID
        """
        # Create title and description
        title = f"Editorial Divergence: {source1_name} vs {source2_name}"
        
        direction_desc = "diverged significantly" if divergence_magnitude > 0.5 else "began diverging"
        
        description = (f"{source1_name} and {source2_name}, which historically moved together "
                      f"(correlation: {historical_corr['correlation']:.2f}), have {direction_desc} "
                      f"(recent correlation: {recent_corr['correlation']:.2f}, p={p_value:.4f})")
        
        if divergent_entities:
            top_entity = divergent_entities[0]
            description += f". Primary divergence on {top_entity['entity_name']}"
        
        # Calculate severity score
        severity_score = min(1.0, divergence_magnitude / 0.8)  # Cap at 0.8 divergence
        
        # Create supporting data for dashboard visualization
        supporting_data = {
            'historical_correlation': historical_corr['correlation'],
            'recent_correlation': recent_corr['correlation'],
            'divergent_entities': divergent_entities[:3],  # Top 3 for display
            'source_pair': {
                'source1_id': source1_id,
                'source1_name': source1_name,
                'source2_id': source2_id,
                'source2_name': source2_name
            }
        }
        
        # Store finding
        finding_id = self.store_finding(
            finding_type='source_divergence',
            title=title,
            description=description,
            p_value=p_value,
            severity_score=severity_score,
            event_start=event_start,
            baseline_value=historical_corr['correlation'],
            current_value=recent_corr['correlation'],
            source_id=source1_id,
            source_id_2=source2_id,
            event_end_date=event_end,
            change_magnitude=divergence_magnitude,
            supporting_data=supporting_data
        )
        
        return finding_id