"""
Sentiment Anomaly Detector

Detects statistically significant sentiment anomalies using sliding window analysis.
Focuses on week-to-week changes with low p-values (< 0.01) to identify truly meaningful shifts.
"""

import logging
import numpy as np
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from sqlalchemy.orm import Session
from sqlalchemy import func

# Import database connections
from database.models import NewsArticle, Entity, EntityMention, NewsSource
from statistical_database.db_manager import StatisticalDBManager
from intelligence.base_analyzer import BaseIntelligenceAnalyzer

logger = logging.getLogger(__name__)

class SentimentAnomalyDetector(BaseIntelligenceAnalyzer):
    """
    Detects unusual sentiment patterns that deviate significantly from historical baselines.
    
    Key principles:
    - Uses rolling 12-week baseline to detect anomalies
    - Requires p-value < 0.01 for significance (roughly once per year events)
    - Focuses on entities with substantial mention counts for statistical robustness
    - Tracks consecutive days of anomalous sentiment to reduce false positives
    """
    
    def __init__(self, 
                 session: Session,
                 statistical_db: StatisticalDBManager,
                 baseline_weeks: int = 12,
                 current_weeks: int = 1,
                 min_consecutive_days: int = 3):
        super().__init__(
            session=session,
            statistical_db=statistical_db,
            min_mentions_threshold=15,  # Higher threshold for anomaly detection
            min_sources_threshold=5,
            significance_threshold=0.01
        )
        self.baseline_weeks = baseline_weeks
        self.current_weeks = current_weeks
        self.min_consecutive_days = min_consecutive_days
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis entry point for the orchestrator.
        
        Returns:
            List of anomaly findings
        """
        start_time = time.time()
        target_week = datetime.utcnow()
        self.log_analysis_start("sentiment anomaly", target_week)
        
        try:
            findings = self._run_anomaly_detection(target_week)
            duration = time.time() - start_time
            self.log_analysis_complete("sentiment anomaly", len(findings), duration)
            return findings
        except Exception as e:
            logger.error(f"Sentiment anomaly analysis failed: {e}")
            return []
        finally:
            self.clear_caches()
    
    def _run_anomaly_detection(self, target_week: datetime) -> List[Dict[str, Any]]:
        """
        Run the weekly sentiment anomaly detection analysis.
        
        Steps:
        1. Get current week boundaries
        2. Get entities with sufficient mention volume
        3. Calculate baseline statistics and current sentiment
        4. Perform statistical tests for anomalies
        5. Store significant findings
        """
        # Get time boundaries
        current_start, current_end = self.get_week_boundaries(target_week)
        baseline_end = current_start - timedelta(days=1)
        baseline_start = baseline_end - timedelta(weeks=self.baseline_weeks)
        
        # Get entities with sufficient activity in current period
        entities = self.get_active_entities(
            current_start, current_end,
            min_mentions=self.min_mentions_threshold,
            min_sources=self.min_sources_threshold
        )
        
        logger.info(f"Analyzing {len(entities)} entities for sentiment anomalies")
        
        findings = []
        for entity in entities:
            entity_findings = self._detect_entity_anomalies(
                entity, baseline_start, baseline_end, current_start, current_end
            )
            findings.extend(entity_findings)
        
        return findings
    
    def _detect_entity_anomalies(self, 
                                entity: Dict[str, Any], 
                                baseline_start: datetime, 
                                baseline_end: datetime,
                                current_start: datetime, 
                                current_end: datetime) -> List[Dict[str, Any]]:
        """
        Detect sentiment anomalies for a specific entity.
        
        Args:
            entity: Entity dictionary from get_active_entities()
            baseline_start: Start of baseline period
            baseline_end: End of baseline period
            current_start: Start of current analysis period
            current_end: End of current analysis period
            
        Returns:
            List of anomaly finding dictionaries
        """
        entity_id = entity['id']
        entity_name = entity['name']
        
        # Get or calculate baseline statistics
        baseline = self._get_or_calculate_baseline(entity_id, baseline_start, baseline_end)
        if not baseline:
            return []  # Insufficient historical data
        
        # Get current period sentiment
        current_sentiment = self._get_period_sentiment(entity_id, current_start, current_end)
        if current_sentiment is None:
            return []  # No current data
        
        # Perform statistical test
        z_score = self.calculate_z_score(
            current_sentiment, baseline['mean'], baseline['std_dev']
        )
        p_value = self.calculate_p_value_two_tailed(z_score)
        
        findings = []
        
        if p_value < self.significance_threshold and abs(z_score) > 2.0:
            # Check for consecutive anomalous days (simplified to current implementation)
            consecutive_days = self._estimate_consecutive_days(
                entity_id, current_end, baseline['mean'], baseline['std_dev']
            )
            
            if consecutive_days >= self.min_consecutive_days:
                finding = self._create_anomaly_finding(
                    entity_id=entity_id,
                    entity_name=entity_name,
                    baseline_value=baseline['mean'],
                    current_value=current_sentiment,
                    z_score=z_score,
                    p_value=p_value,
                    consecutive_days=consecutive_days,
                    event_start_date=current_start,
                    event_end_date=current_end,
                    sample_count=baseline['sample_count']
                )
                findings.append(finding)
        
        return findings
    
    def _get_or_calculate_baseline(self, 
                                  entity_id: int, 
                                  baseline_start: datetime, 
                                  baseline_end: datetime) -> Optional[Dict[str, Any]]:
        """
        Get cached baseline statistics or calculate new ones.
        
        Args:
            entity_id: Entity to get baseline for
            baseline_start: Start of baseline period
            baseline_end: End of baseline period
            
        Returns:
            Dictionary with baseline statistics or None if insufficient data
        """
        # Try to get cached baseline
        baseline = self.statistical_db.get_baseline_statistics(
            metric_type='entity_sentiment',
            entity_id=entity_id,
            window_weeks=self.baseline_weeks
        )
        
        # Check if baseline is recent enough (within last week)
        if baseline and baseline.get('calculation_date'):
            age_days = (datetime.utcnow() - baseline['calculation_date']).days
            if age_days <= 7:  # Use cached baseline if less than a week old
                return baseline
        
        # Calculate new baseline
        return self._calculate_entity_baseline(entity_id, baseline_start, baseline_end)
    
    def _calculate_entity_baseline(self, 
                                  entity_id: int, 
                                  baseline_start: datetime, 
                                  baseline_end: datetime) -> Optional[Dict[str, Any]]:
        """
        Calculate baseline statistics for an entity using historical data.
        
        Args:
            entity_id: Entity to analyze
            baseline_start: Start date for baseline calculation
            baseline_end: End date for baseline calculation
            
        Returns:
            Dictionary with baseline statistics or None if insufficient data
        """
        # Query historical sentiment data
        sentiments_query = self.session.query(
            ((EntityMention.power_score + EntityMention.moral_score) / 2.0).label('sentiment')
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            EntityMention.entity_id == entity_id,
            NewsArticle.publish_date >= baseline_start,
            NewsArticle.publish_date <= baseline_end,
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
        
        # Ensure std_dev is not zero
        if std_sentiment < 0.01:
            std_sentiment = 0.01
        
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
            data_start_date=baseline_start,
            data_end_date=baseline_end,
            sample_count=len(sentiments),
            window_weeks=self.baseline_weeks,
            percentile_95=percentile_95,
            percentile_5=percentile_5
        )
        
        return baseline_stats
    
    def _get_period_sentiment(self, 
                             entity_id: int, 
                             period_start: datetime, 
                             period_end: datetime) -> Optional[float]:
        """
        Get average sentiment for entity in a specific time period.
        
        Args:
            entity_id: Entity to analyze
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Average sentiment or None if insufficient data
        """
        result = self.session.query(
            func.avg((EntityMention.power_score + EntityMention.moral_score) / 2.0).label('avg_sentiment'),
            func.count(EntityMention.id).label('mention_count')
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).filter(
            EntityMention.entity_id == entity_id,
            NewsArticle.publish_date >= period_start,
            NewsArticle.publish_date <= period_end,
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).first()
        
        if result and result.avg_sentiment is not None and result.mention_count >= 5:
            return float(result.avg_sentiment)
        
        return None
    
    def _estimate_consecutive_days(self, 
                                  entity_id: int, 
                                  end_date: datetime, 
                                  baseline_mean: float, 
                                  baseline_std: float) -> int:
        """
        Estimate consecutive days of anomalous sentiment.
        
        This is a simplified implementation that checks the last few days.
        A more sophisticated version would analyze daily sentiment patterns.
        
        Args:
            entity_id: Entity to check
            end_date: End date to work backwards from
            baseline_mean: Baseline mean for comparison
            baseline_std: Baseline standard deviation
            
        Returns:
            Estimated number of consecutive anomalous days
        """
        consecutive_count = 0
        
        # Check last 7 days for anomalous sentiment
        for days_back in range(7):
            day_end = end_date - timedelta(days=days_back)
            day_start = day_end - timedelta(hours=23, minutes=59, seconds=59)
            
            day_sentiment = self._get_period_sentiment(entity_id, day_start, day_end)
            
            if day_sentiment is not None:
                z_score = self.calculate_z_score(day_sentiment, baseline_mean, baseline_std)
                if abs(z_score) > 2.0:  # Anomalous day
                    consecutive_count += 1
                else:
                    break  # Non-anomalous day breaks the streak
            else:
                break  # No data breaks the streak
        
        return max(1, consecutive_count)  # At least 1 day
    
    def _create_anomaly_finding(self,
                               entity_id: int,
                               entity_name: str,
                               baseline_value: float,
                               current_value: float,
                               z_score: float,
                               p_value: float,
                               consecutive_days: int,
                               event_start_date: datetime,
                               event_end_date: datetime,
                               sample_count: int) -> Dict[str, Any]:
        """
        Create a formatted anomaly finding for storage and return.
        
        Args:
            entity_id: Entity ID
            entity_name: Entity name for display
            baseline_value: Historical baseline mean
            current_value: Current observed value
            z_score: Statistical z-score
            p_value: Statistical p-value
            consecutive_days: Number of consecutive anomalous days
            event_start_date: When the anomaly period started
            event_end_date: When the anomaly period ended
            sample_count: Size of baseline sample
            
        Returns:
            Dictionary with finding details and stored finding_id
        """
        # Determine sentiment direction and magnitude
        change_magnitude = current_value - baseline_value
        direction = "more positive" if change_magnitude > 0 else "more negative"
        magnitude_desc = "dramatically" if abs(z_score) > 3 else "significantly"
        
        # Create title and description
        title = f"{entity_name}: {magnitude_desc} {direction} sentiment"
        description = (f"{entity_name} sentiment shifted {magnitude_desc} {direction} "
                      f"({current_value:.2f} vs baseline {baseline_value:.2f}, "
                      f"z={z_score:.2f}, p={p_value:.4f}) for {consecutive_days} consecutive days")
        
        # Calculate severity score (0-1)
        severity_score = min(1.0, abs(z_score) / 5.0)  # Cap at z=5
        
        # Create supporting data for dashboard visualization
        supporting_data = {
            'z_score': z_score,
            'change_magnitude': change_magnitude,
            'consecutive_days': consecutive_days,
            'baseline_sample_size': sample_count,
            'sentiment_direction': direction,
            'chart_data': {
                'baseline_mean': baseline_value,
                'current_value': current_value,
                'change_percent': (change_magnitude / abs(baseline_value)) * 100 if baseline_value != 0 else 0
            }
        }
        
        # Store finding in statistical database
        finding_id = self.store_finding(
            finding_type='sentiment_anomaly',
            title=title,
            description=description,
            p_value=p_value,
            severity_score=severity_score,
            event_start=event_start_date,
            baseline_value=baseline_value,
            current_value=current_value,
            entity_id=entity_id,
            z_score=z_score,
            event_end_date=event_end_date,
            change_magnitude=change_magnitude,
            consecutive_days=consecutive_days,
            supporting_data=supporting_data
        )
        
        return {
            'finding_id': finding_id,
            'entity_id': entity_id,
            'entity_name': entity_name,
            'anomaly_type': 'sentiment_shift',
            'significance': p_value,
            'magnitude': abs(change_magnitude),
            'direction': direction,
            'consecutive_days': consecutive_days,
            'z_score': z_score,
            'severity_score': severity_score
        }