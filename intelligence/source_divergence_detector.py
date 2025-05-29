"""
Source Divergence Detector

Detects when news sources that historically moved together begin to diverge on sentiment,
indicating potential editorial shifts or emerging polarization around specific topics.
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from scipy.stats import pearsonr
from sqlalchemy.orm import Session

# Import database connections  
from database.db import get_session
from database.models import NewsArticle, Entity, EntityMention, NewsSource
from .statistical_database.db_manager import StatisticalDBManager

logger = logging.getLogger(__name__)

class SourceDivergenceDetector:
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
                 statistical_db: StatisticalDBManager,
                 historical_weeks: int = 24,  # 6 months of historical data
                 recent_weeks: int = 4,       # 1 month of recent data
                 significance_threshold: float = 0.01,
                 min_historical_correlation: float = 0.7,
                 min_divergence_magnitude: float = 0.3,
                 min_common_entities: int = 10):
        self.statistical_db = statistical_db
        self.historical_weeks = historical_weeks
        self.recent_weeks = recent_weeks
        self.significance_threshold = significance_threshold
        self.min_historical_correlation = min_historical_correlation
        self.min_divergence_magnitude = min_divergence_magnitude
        self.min_common_entities = min_common_entities
    
    def run_weekly_analysis(self, session: Session, target_week: datetime = None):
        """
        Run weekly source divergence analysis.
        
        TODO: Implement the following steps:
        1. Get source pairs that had high historical correlation
        2. Calculate recent correlation for these pairs
        3. Test for significant divergence
        4. Identify entities driving the divergence
        5. Store significant divergences
        """
        if target_week is None:
            target_week = datetime.utcnow()
        
        logger.info(f"Starting source divergence detection for week of {target_week.date()}")
        
        # TODO: Get date ranges
        recent_end = target_week
        recent_start = recent_end - timedelta(weeks=self.recent_weeks)
        historical_end = recent_start - timedelta(days=1)
        historical_start = historical_end - timedelta(weeks=self.historical_weeks)
        
        # TODO: Get source pairs with sufficient historical correlation
        source_pairs = self._get_historically_correlated_pairs(session, historical_start, historical_end)
        logger.info(f"Analyzing {len(source_pairs)} historically correlated source pairs")
        
        divergences = []
        for source_pair in source_pairs:
            # TODO: Analyze each pair for divergence
            divergence = self._analyze_pair_divergence(
                session, source_pair, 
                historical_start, historical_end,
                recent_start, recent_end
            )
            if divergence:
                divergences.append(divergence)
        
        logger.info(f"Detected {len(divergences)} significant source divergences")
        return divergences
    
    def _get_historically_correlated_pairs(self, 
                                         session: Session, 
                                         start_date: datetime, 
                                         end_date: datetime) -> List[Tuple[Dict, Dict]]:
        """
        Get pairs of sources that had high correlation in the historical period.
        
        TODO: Implement the following:
        1. Get all sources with sufficient activity in historical period
        2. Calculate pairwise correlations on entity sentiment
        3. Filter for pairs with correlation > min_historical_correlation
        4. Return list of (source1, source2) tuples
        
        Returns:
            List of tuples containing source dictionaries (id, name, country)
        """
        # TODO: Get active sources in historical period
        active_sources = self._get_active_sources(session, start_date, end_date)
        
        # TODO: Calculate all pairwise correlations
        correlated_pairs = []
        
        # TODO: This is computationally expensive - consider caching or sampling
        for i, source1 in enumerate(active_sources):
            for source2 in active_sources[i+1:]:
                # TODO: Calculate correlation between source1 and source2
                correlation = self._calculate_source_correlation(
                    session, source1, source2, start_date, end_date
                )
                
                if correlation and correlation['correlation'] > self.min_historical_correlation:
                    correlated_pairs.append((source1, source2, correlation))
        
        # TODO: Return top correlated pairs
        correlated_pairs.sort(key=lambda x: x[2]['correlation'], reverse=True)
        return [(pair[0], pair[1]) for pair in correlated_pairs[:100]]  # Limit to top 100
    
    def _get_active_sources(self, session: Session, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get sources with sufficient activity for correlation analysis.
        
        TODO: Implement query to get sources with:
        - Sufficient article count in time period
        - Coverage of multiple entities for correlation
        - Same country (for meaningful comparison)
        """
        # TODO: Implement database query
        # query = session.query(NewsSource).join(NewsArticle)...
        
        # Placeholder return
        return []
    
    def _calculate_source_correlation(self, 
                                    session: Session,
                                    source1: Dict, 
                                    source2: Dict,
                                    start_date: datetime, 
                                    end_date: datetime) -> Optional[Dict]:
        """
        Calculate correlation between two sources' entity sentiment patterns.
        
        TODO: Implement the following:
        1. Get entity sentiment vectors for both sources
        2. Find common entities
        3. Calculate Pearson correlation
        4. Return correlation data with sample size
        
        Returns:
            Dictionary with correlation, p_value, common_entities count or None
        """
        # TODO: Get sentiment vectors for both sources
        vector1 = self._get_source_sentiment_vector(session, source1['id'], start_date, end_date)
        vector2 = self._get_source_sentiment_vector(session, source2['id'], start_date, end_date)
        
        if not vector1 or not vector2:
            return None
        
        # TODO: Find common entities
        common_entities = set(vector1.keys()) & set(vector2.keys())
        
        if len(common_entities) < self.min_common_entities:
            return None
        
        # TODO: Calculate correlation
        values1 = [vector1[entity_id] for entity_id in common_entities]
        values2 = [vector2[entity_id] for entity_id in common_entities]
        
        correlation, p_value = pearsonr(values1, values2)
        
        return {
            'correlation': correlation,
            'p_value': p_value,
            'common_entities': len(common_entities),
            'sample_size': len(values1)
        }
    
    def _get_source_sentiment_vector(self, 
                                   session: Session,
                                   source_id: int, 
                                   start_date: datetime, 
                                   end_date: datetime) -> Dict[int, float]:
        """
        Get entity sentiment vector for a source in a time period.
        
        TODO: Implement query to get average sentiment per entity for this source
        
        Returns:
            Dictionary mapping entity_id -> average_sentiment
        """
        # TODO: Query entity sentiments
        # query = session.query(
        #     EntityMention.entity_id,
        #     func.avg((EntityMention.power_score + EntityMention.moral_score) / 2).label('avg_sentiment')
        # ).join(NewsArticle).filter(...)
        
        # Placeholder return
        return {}
    
    def _analyze_pair_divergence(self, 
                               session: Session,
                               source_pair: Tuple[Dict, Dict],
                               historical_start: datetime,
                               historical_end: datetime,
                               recent_start: datetime,
                               recent_end: datetime) -> Optional[Dict]:
        """
        Analyze a specific source pair for divergence.
        
        TODO: Implement the following:
        1. Calculate historical correlation
        2. Calculate recent correlation  
        3. Test for significant change
        4. Identify entities driving divergence
        5. Create divergence finding if significant
        
        Returns:
            Divergence finding dictionary or None
        """
        source1, source2 = source_pair
        
        # TODO: Calculate historical correlation
        historical_corr = self._calculate_source_correlation(
            session, source1, source2, historical_start, historical_end
        )
        
        # TODO: Calculate recent correlation
        recent_corr = self._calculate_source_correlation(
            session, source1, source2, recent_start, recent_end
        )
        
        if not historical_corr or not recent_corr:
            return None
        
        # TODO: Test for significant divergence
        divergence_magnitude = abs(historical_corr['correlation'] - recent_corr['correlation'])
        
        if divergence_magnitude < self.min_divergence_magnitude:
            return None
        
        # TODO: Statistical test for significance of correlation change
        # This is complex - could use Fisher's z-transformation
        p_value = self._test_correlation_change(historical_corr, recent_corr)
        
        if p_value > self.significance_threshold:
            return None
        
        # TODO: Identify entities driving the divergence
        divergent_entities = self._identify_divergent_entities(
            session, source1, source2, recent_start, recent_end
        )
        
        # TODO: Store divergence in statistical database
        self.statistical_db.store_source_divergence(
            source_id_1=source1['id'],
            source_id_2=source2['id'],
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
        
        # TODO: Create finding for dashboard
        finding_id = self._create_divergence_finding(
            source1, source2, historical_corr, recent_corr, 
            divergence_magnitude, p_value, divergent_entities,
            recent_start, recent_end
        )
        
        return {
            'finding_id': finding_id,
            'source1': source1,
            'source2': source2,
            'historical_correlation': historical_corr['correlation'],
            'recent_correlation': recent_corr['correlation'],
            'divergence_magnitude': divergence_magnitude,
            'p_value': p_value,
            'divergent_entities': divergent_entities
        }
    
    def _test_correlation_change(self, historical_corr: Dict, recent_corr: Dict) -> float:
        """
        Test if the change in correlation is statistically significant.
        
        TODO: Implement Fisher's z-transformation test for correlation difference
        This is a complex statistical test - may need to simplify or use approximation
        """
        # TODO: Implement proper statistical test
        # For now, use a simplified approach based on sample sizes
        
        # Placeholder implementation
        n1 = historical_corr['sample_size']
        n2 = recent_corr['sample_size']
        
        if n1 < 10 or n2 < 10:
            return 1.0  # Not enough data
        
        # Very simplified approximation
        se = np.sqrt(1/(n1-3) + 1/(n2-3))
        z = abs(historical_corr['correlation'] - recent_corr['correlation']) / se
        p_value = 2 * (1 - stats.norm.cdf(z))
        
        return p_value
    
    def _identify_divergent_entities(self, 
                                   session: Session,
                                   source1: Dict, 
                                   source2: Dict,
                                   start_date: datetime, 
                                   end_date: datetime) -> List[Dict[str, Any]]:
        """
        Identify which entities are driving the divergence between sources.
        
        TODO: Implement the following:
        1. Get entity sentiment differences between sources in recent period
        2. Compare to historical differences
        3. Identify entities with largest sentiment gaps
        4. Return top divergent entities with context
        
        Returns:
            List of entities with divergence information
        """
        # TODO: Get sentiment vectors for both sources
        vector1 = self._get_source_sentiment_vector(session, source1['id'], start_date, end_date)
        vector2 = self._get_source_sentiment_vector(session, source2['id'], start_date, end_date)
        
        # TODO: Calculate entity-level divergences
        divergent_entities = []
        
        common_entities = set(vector1.keys()) & set(vector2.keys())
        for entity_id in common_entities:
            sentiment_diff = abs(vector1[entity_id] - vector2[entity_id])
            
            # TODO: Get entity name and context
            # entity_name = session.query(Entity).filter(Entity.id == entity_id).first().name
            
            divergent_entities.append({
                'entity_id': entity_id,
                # 'entity_name': entity_name,
                'sentiment_difference': sentiment_diff,
                'source1_sentiment': vector1[entity_id],
                'source2_sentiment': vector2[entity_id]
            })
        
        # TODO: Sort by divergence magnitude and return top entities
        divergent_entities.sort(key=lambda x: x['sentiment_difference'], reverse=True)
        return divergent_entities[:10]  # Top 10 divergent entities
    
    def _create_divergence_finding(self, 
                                 source1: Dict, 
                                 source2: Dict,
                                 historical_corr: Dict, 
                                 recent_corr: Dict,
                                 divergence_magnitude: float,
                                 p_value: float,
                                 divergent_entities: List[Dict],
                                 event_start: datetime,
                                 event_end: datetime) -> int:
        """
        Create a divergence finding for the dashboard.
        
        TODO: Create properly formatted finding and store in statistical database
        """
        # Create title and description
        title = f"Editorial Divergence: {source1['name']} vs {source2['name']}"
        
        direction_desc = "diverged significantly" if divergence_magnitude > 0.5 else "began diverging"
        
        description = (f"{source1['name']} and {source2['name']}, which historically moved together "
                      f"(correlation: {historical_corr['correlation']:.2f}), have {direction_desc} "
                      f"(recent correlation: {recent_corr['correlation']:.2f}, p={p_value:.4f})")
        
        if divergent_entities:
            top_entity = divergent_entities[0]
            description += f". Primary divergence on {top_entity.get('entity_name', 'key topics')}"
        
        # Calculate severity score
        severity_score = min(1.0, divergence_magnitude / 0.8)  # Cap at 0.8 divergence
        
        # Create supporting data for dashboard visualization
        supporting_data = {
            'historical_correlation': historical_corr['correlation'],
            'recent_correlation': recent_corr['correlation'],
            'divergent_entities': divergent_entities[:5],  # Top 5 for display
            'chart_data': {
                'correlation_timeline': [],  # TODO: Add historical correlation timeline
                'entity_divergence': divergent_entities[:5]
            }
        }
        
        # Store finding
        finding_id = self.statistical_db.store_statistical_finding(
            finding_type='source_divergence',
            title=title,
            description=description,
            p_value=p_value,
            event_start_date=event_start,
            baseline_value=historical_corr['correlation'],
            current_value=recent_corr['correlation'],
            severity_score=severity_score,
            dashboard_category='divergence',
            source_id=source1['id'],
            source_id_2=source2['id'],
            event_end_date=event_end,
            change_magnitude=divergence_magnitude,
            priority_score=severity_score,
            supporting_data=supporting_data
        )
        
        return finding_id
    
    def analyze_single_pair(self, 
                          session: Session,
                          source1_id: int, 
                          source2_id: int,
                          weeks_back: int = 12) -> Optional[Dict]:
        """
        Analyze a specific pair of sources for divergence over time.
        
        TODO: Implement detailed analysis of a specific source pair
        This could be used for dashboard drill-down or manual investigation
        """
        # TODO: Implement single pair analysis with timeline
        # This would show correlation over time, key divergent entities, etc.
        
        logger.info(f"Analyzing divergence between sources {source1_id} and {source2_id}")
        
        # Placeholder return
        return None