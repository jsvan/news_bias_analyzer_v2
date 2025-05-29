"""
Sentiment Anomaly Detector

Detects statistically significant sentiment anomalies using sliding window analysis.
Focuses on week-to-week changes with low p-values (< 0.01) to identify truly meaningful shifts.
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

class SentimentAnomalyDetector:
    """
    Detects unusual sentiment patterns that deviate significantly from historical baselines.
    
    Key principles:
    - Uses rolling 12-week baseline to detect anomalies
    - Requires p-value < 0.01 for significance (roughly once per year events)
    - Focuses on entities with substantial mention counts for statistical robustness
    - Tracks consecutive days of anomalous sentiment to reduce false positives
    """
    
    def __init__(self, 
                 statistical_db: StatisticalDBManager,
                 baseline_weeks: int = 12,
                 significance_threshold: float = 0.01,
                 min_mentions_per_week: int = 10,
                 min_consecutive_days: int = 3):
        self.statistical_db = statistical_db
        self.baseline_weeks = baseline_weeks
        self.significance_threshold = significance_threshold
        self.min_mentions_per_week = min_mentions_per_week
        self.min_consecutive_days = min_consecutive_days
    
    def run_weekly_analysis(self, session: Session, target_week: datetime = None):
        """
        Run the weekly sentiment anomaly detection analysis.
        
        TODO: Implement the following steps:
        1. Get current week boundaries
        2. Calculate baseline statistics for all entities with sufficient mentions
        3. Get current week sentiment data
        4. Perform statistical tests for anomalies
        5. Track consecutive anomalous days
        6. Store significant findings
        """
        if target_week is None:
            target_week = datetime.utcnow()
        
        logger.info(f"Starting sentiment anomaly detection for week of {target_week.date()}")
        
        # TODO: Implement week boundary calculation
        week_start, week_end = self._get_week_boundaries(target_week)
        
        # TODO: Get entities with sufficient mention volume
        entities = self._get_entities_for_analysis(session, week_start, week_end)
        logger.info(f"Analyzing {len(entities)} entities for sentiment anomalies")
        
        findings = []
        for entity in entities:
            # TODO: Implement per-entity anomaly detection
            entity_findings = self._detect_entity_anomalies(session, entity, week_start, week_end)
            findings.extend(entity_findings)
        
        logger.info(f"Detected {len(findings)} sentiment anomalies")
        return findings
    
    def _get_week_boundaries(self, date: datetime) -> Tuple[datetime, datetime]:
        """
        Get ISO week boundaries (Monday-Sunday).
        
        TODO: Implement proper week boundary calculation
        """
        # Placeholder implementation
        # Find the Monday of this week
        days_since_monday = date.weekday()
        monday = date - timedelta(days=days_since_monday)
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Sunday is 6 days later
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        return monday, sunday
    
    def _get_entities_for_analysis(self, session: Session, week_start: datetime, week_end: datetime) -> List[Dict]:
        """
        Get entities with sufficient mention volume for statistical analysis.
        
        Returns:
            List of entity dictionaries with id, name, type, mention_count
        """
        from sqlalchemy import func
        
        # Query entities with sufficient mentions in current week
        query = session.query(
            Entity.id,
            Entity.name,
            Entity.entity_type,
            func.count(EntityMention.id).label('mention_count'),
            func.count(func.distinct(NewsArticle.source_id)).label('source_count')
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            NewsArticle.publish_date >= week_start,
            NewsArticle.publish_date <= week_end,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).group_by(
            Entity.id, Entity.name, Entity.entity_type
        ).having(
            func.count(EntityMention.id) >= self.min_mentions_per_week,
            func.count(func.distinct(NewsArticle.source_id)) >= 3  # At least 3 sources
        ).order_by(
            func.count(EntityMention.id).desc()
        ).limit(100)  # Limit to top 100 entities
        
        entities = []
        for row in query.all():
            entities.append({
                'id': row.id,
                'name': row.name,
                'type': row.entity_type,
                'mention_count': row.mention_count,
                'source_count': row.source_count
            })
        
        return entities
    
    def _detect_entity_anomalies(self, 
                                session: Session, 
                                entity: Dict, 
                                week_start: datetime, 
                                week_end: datetime) -> List[Dict]:
        """
        Detect sentiment anomalies for a specific entity.
        
        TODO: Implement the following:
        1. Get baseline statistics for this entity
        2. Calculate current week sentiment
        3. Perform statistical tests (z-score, t-test)
        4. Check for consecutive anomalous days
        5. Create finding records for significant anomalies
        
        Args:
            entity: Entity dictionary with id, name, type
            week_start: Start of current analysis week
            week_end: End of current analysis week
            
        Returns:
            List of anomaly finding dictionaries
        """
        entity_id = entity['id']
        entity_name = entity['name']
        
        # TODO: Get or calculate baseline statistics
        baseline = self._get_entity_baseline(session, entity_id, week_start)
        
        if not baseline:
            # TODO: Calculate new baseline
            baseline = self._calculate_entity_baseline(session, entity_id, week_start)
            if not baseline:
                return []  # Insufficient historical data
        
        # TODO: Get current week sentiment data
        current_sentiment = self._get_current_week_sentiment(session, entity_id, week_start, week_end)
        
        if current_sentiment is None:
            return []  # No current data
        
        # TODO: Perform statistical test
        z_score = (current_sentiment - baseline['mean']) / baseline['std_dev']
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))  # Two-tailed test
        
        findings = []
        
        if p_value < self.significance_threshold:
            # TODO: Check for consecutive anomalous days
            consecutive_days = self._count_consecutive_anomalous_days(session, entity_id, week_end)
            
            if consecutive_days >= self.min_consecutive_days:
                # TODO: Create finding record
                finding = self._create_anomaly_finding(
                    entity_id=entity_id,
                    entity_name=entity_name,
                    baseline_value=baseline['mean'],
                    current_value=current_sentiment,
                    z_score=z_score,
                    p_value=p_value,
                    consecutive_days=consecutive_days,
                    event_start_date=week_start,
                    event_end_date=week_end
                )
                findings.append(finding)
        
        return findings
    
    def _get_entity_baseline(self, session: Session, entity_id: int, reference_date: datetime) -> Optional[Dict]:
        """
        Get cached baseline statistics for an entity.
        
        TODO: Query statistical database for existing baseline stats
        """
        # TODO: Use statistical_db.get_baseline_statistics()
        return self.statistical_db.get_baseline_statistics(
            metric_type='entity_sentiment',
            entity_id=entity_id,
            window_weeks=self.baseline_weeks
        )
    
    def _calculate_entity_baseline(self, session: Session, entity_id: int, reference_date: datetime) -> Optional[Dict]:
        """
        Calculate baseline statistics for an entity using historical data.
        
        Args:
            entity_id: Entity to analyze
            reference_date: Date to work backwards from
            
        Returns:
            Dictionary with baseline statistics or None if insufficient data
        """
        from sqlalchemy import func
        
        # Calculate date range for baseline
        end_date = reference_date - timedelta(days=1)  # Don't include current week
        start_date = end_date - timedelta(weeks=self.baseline_weeks)
        
        # Query historical sentiment data
        sentiments_query = session.query(
            ((EntityMention.power_score + EntityMention.moral_score) / 2.0).label('sentiment')
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            EntityMention.entity_id == entity_id,
            NewsArticle.publish_date >= start_date,
            NewsArticle.publish_date <= end_date,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        )
        
        sentiments = [row.sentiment for row in sentiments_query.all()]
        
        if len(sentiments) < 20:  # Need at least 20 data points
            return None
        
        # Calculate statistics
        sentiments_array = np.array(sentiments)
        mean_sentiment = float(np.mean(sentiments_array))
        std_sentiment = float(np.std(sentiments_array))
        min_sentiment = float(np.min(sentiments_array))
        max_sentiment = float(np.max(sentiments_array))
        percentile_95 = float(np.percentile(sentiments_array, 95))
        percentile_5 = float(np.percentile(sentiments_array, 5))
        
        baseline_stats = {
            'mean': mean_sentiment,
            'std_dev': std_sentiment,
            'min_value': min_sentiment,
            'max_value': max_sentiment,
            'percentile_95': percentile_95,
            'percentile_5': percentile_5,
            'sample_count': len(sentiments)
        }
        
        # Store baseline in statistical database
        self.statistical_db.store_baseline_statistics(
            metric_type='entity_sentiment',
            entity_id=entity_id,
            mean_value=mean_sentiment,
            std_dev=std_sentiment,
            min_value=min_sentiment,
            max_value=max_sentiment,
            data_start_date=start_date,
            data_end_date=end_date,
            sample_count=len(sentiments),
            window_weeks=self.baseline_weeks,
            percentile_95=percentile_95,
            percentile_5=percentile_5
        )
        
        return baseline_stats
    
    def _get_current_week_sentiment(self, 
                                  session: Session, 
                                  entity_id: int, 
                                  week_start: datetime, 
                                  week_end: datetime) -> Optional[float]:
        """
        Get average sentiment for entity in current week.
        """
        from sqlalchemy import func
        
        result = session.query(
            func.avg((EntityMention.power_score + EntityMention.moral_score) / 2.0).label('avg_sentiment'),
            func.count(EntityMention.id).label('mention_count')
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            EntityMention.entity_id == entity_id,
            NewsArticle.publish_date >= week_start,
            NewsArticle.publish_date <= week_end,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).first()
        
        if result and result.avg_sentiment is not None and result.mention_count >= 5:
            return float(result.avg_sentiment)
        
        return None
    
    def _count_consecutive_anomalous_days(self, session: Session, entity_id: int, end_date: datetime) -> int:
        """
        Count how many consecutive days this entity has shown anomalous sentiment.
        
        TODO: Implement daily sentiment analysis going backwards from end_date
        to count consecutive days where sentiment is statistically anomalous
        """
        # TODO: Implement consecutive day counting
        # This requires daily sentiment aggregation and comparison to baseline
        
        # Placeholder return
        return 1
    
    def _create_anomaly_finding(self, 
                              entity_id: int,
                              entity_name: str,
                              baseline_value: float,
                              current_value: float,
                              z_score: float,
                              p_value: float,
                              consecutive_days: int,
                              event_start_date: datetime,
                              event_end_date: datetime) -> Dict:
        """
        Create a formatted anomaly finding for storage.
        
        TODO: Create properly formatted finding dictionary and store in database
        """
        # Determine sentiment direction and magnitude
        change_magnitude = current_value - baseline_value
        direction = "more positive" if change_magnitude > 0 else "more negative"
        magnitude_desc = "dramatically" if abs(z_score) > 3 else "significantly"
        
        # Create title and description
        title = f"{entity_name}: {magnitude_desc} {direction} sentiment"
        description = (f"{entity_name} sentiment shifted {magnitude_desc} {direction} "
                      f"({current_value:.2f} vs baseline {baseline_value:.2f}, "
                      f"p={p_value:.4f}) for {consecutive_days} consecutive days")
        
        # Calculate severity score (0-1)
        severity_score = min(1.0, abs(z_score) / 5.0)  # Cap at z=5
        
        # TODO: Store finding in statistical database
        finding_id = self.statistical_db.store_statistical_finding(
            finding_type='sentiment_anomaly',
            title=title,
            description=description,
            p_value=p_value,
            event_start_date=event_start_date,
            baseline_value=baseline_value,
            current_value=current_value,
            severity_score=severity_score,
            dashboard_category='anomaly',
            entity_id=entity_id,
            z_score=z_score,
            event_end_date=event_end_date,
            change_magnitude=change_magnitude,
            consecutive_days=consecutive_days,
            priority_score=severity_score
        )
        
        return {
            'finding_id': finding_id,
            'entity_id': entity_id,
            'entity_name': entity_name,
            'anomaly_type': 'sentiment_shift',
            'significance': p_value,
            'magnitude': abs(change_magnitude),
            'direction': direction,
            'consecutive_days': consecutive_days
        }
    
    def update_baselines(self, session: Session, force_recalculate: bool = False):
        """
        Update baseline statistics for all entities.
        
        TODO: Implement batch baseline updates:
        1. Get all entities that need baseline updates
        2. Calculate new baselines in batches
        3. Store updated baselines
        4. Clean up old baseline data
        """
        logger.info("Starting baseline statistics update")
        
        # TODO: Implement baseline update logic
        # This should run periodically (e.g., weekly) to keep baselines current
        
        logger.info("Baseline statistics update complete")