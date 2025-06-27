"""
Analyzes temporal patterns in source sentiment and detects drift.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
from scipy import stats
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

from .base import BaseAnalyzer
# Import statistical database for storing results
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from statistical_database.db_manager import StatisticalDBManager

logger = logging.getLogger(__name__)


class TemporalAnalyzer(BaseAnalyzer):
    """Handles temporal analysis of sentiment patterns."""
    
    def __init__(self, session: Session):
        super().__init__(session)
        # Initialize statistical database for storing results
        self.statistical_db = StatisticalDBManager()
    
    def analyze(self):
        """Run temporal analysis - called by statistical orchestrator."""
        logger.info("Running weekly drift metrics analysis...")
        return self.compute_weekly_drift_metrics()
    
    def compute_weekly_drift_metrics(self, week_start: datetime = None):
        """Compute drift metrics for all sources."""
        start_date, end_date = self.get_week_boundaries(week_start)
        logger.info(f"Computing drift metrics for week {start_date.date()}")
        
        # Get previous week for comparison
        prev_start = start_date - timedelta(days=7)
        prev_end = start_date - timedelta(seconds=1)
        
        # Get all active sources
        sources = self.get_active_sources(start_date, end_date)
        logger.info(f"Computing drift for {len(sources)} active sources")
        
        # Process in batches
        batch_size = 50
        for i in range(0, len(sources), batch_size):
            batch = sources[i:i+batch_size]
            self._process_drift_batch(batch, start_date, end_date, prev_start, prev_end)
            
        # Compute entity volatility
        self._compute_entity_volatility(start_date, end_date)
        
        logger.info("Weekly drift computation complete")
    
    def _process_drift_batch(self,
                           sources: List[Dict],
                           curr_start: datetime,
                           curr_end: datetime,
                           prev_start: datetime,
                           prev_end: datetime):
        """Process drift metrics for a batch of sources."""
        source_ids = [s['id'] for s in sources]
        
        # Get entity sentiments for current and previous week
        curr_vectors = self.get_source_entity_vectors(source_ids, curr_start, curr_end)
        prev_vectors = self.get_source_entity_vectors(source_ids, prev_start, prev_end)
        
        drift_records = []
        
        for source in sources:
            source_id = source['id']
            
            # Skip if no data for either week
            if source_id not in curr_vectors or source_id not in prev_vectors:
                continue
                
            curr_vec = curr_vectors[source_id]
            prev_vec = prev_vectors[source_id]
            
            # Find common entities
            common_entities = set(curr_vec.keys()) & set(prev_vec.keys())
            
            for entity_id in common_entities:
                sentiment_change = curr_vec[entity_id] - prev_vec[entity_id]
                
                drift_records.append({
                    'source_id': source_id,
                    'entity_id': entity_id,
                    'week_start': curr_start.date(),
                    'avg_sentiment': curr_vec[entity_id],
                    'sentiment_change': sentiment_change,
                    'mention_count': 1  # Would need actual count
                })
        
        # Store drift records
        if drift_records:
            self._store_drift_records(drift_records)
    
    def _store_drift_records(self, records: List[Dict]):
        """Store temporal drift records to database."""
        # Delete existing records for this week
        if records:
            week_start = records[0]['week_start']
            source_ids = list(set(r['source_id'] for r in records))
            
            delete_query = text("""
                DELETE FROM source_temporal_drift
                WHERE 
                    week_start = :week_start
                    AND source_id = ANY(:source_ids)
            """)
            
            self.session.execute(delete_query, {
                'week_start': week_start,
                'source_ids': source_ids
            })
        
        # Insert new records
        insert_query = text("""
            INSERT INTO source_temporal_drift (
                source_id, entity_id, week_start,
                avg_sentiment, sentiment_change, mention_count
            ) VALUES (
                :source_id, :entity_id, :week_start,
                :avg_sentiment, :sentiment_change, :mention_count
            )
        """)
        
        for record in records:
            self.session.execute(insert_query, record)
            
        self.session.commit()
        logger.info(f"Stored {len(records)} drift records")
    
    def _compute_entity_volatility(self, start_date: datetime, end_date: datetime):
        """Compute volatility scores for entities."""
        # Get entities with significant coverage
        query = text("""
            WITH entity_stats AS (
                SELECT 
                    em.entity_id,
                    COUNT(DISTINCT na.source_id) as source_count,
                    COUNT(*) as total_mentions,
                    STDDEV((em.power_score + em.moral_score) / 2.0) as sentiment_stddev,
                    AVG((em.power_score + em.moral_score) / 2.0) as avg_sentiment
                FROM entity_mentions em
                JOIN news_articles na ON em.article_id = na.id
                WHERE 
                    na.publish_date BETWEEN :start_date AND :end_date
                    AND em.power_score IS NOT NULL
                    AND em.moral_score IS NOT NULL
                GROUP BY em.entity_id
                HAVING COUNT(DISTINCT na.source_id) >= 5  -- At least 5 sources
                   AND COUNT(*) >= 20  -- At least 20 mentions
            ),
            source_averages AS (
                SELECT 
                    em.entity_id,
                    na.source_id,
                    AVG((em.power_score + em.moral_score) / 2.0) as source_avg_sentiment
                FROM entity_mentions em
                JOIN news_articles na ON em.article_id = na.id
                WHERE 
                    na.publish_date BETWEEN :start_date AND :end_date
                    AND em.entity_id IN (SELECT entity_id FROM entity_stats)
                GROUP BY em.entity_id, na.source_id
                HAVING COUNT(*) >= 2
            ),
            source_variance AS (
                SELECT 
                    entity_id,
                    VARIANCE(source_avg_sentiment) as cross_source_var
                FROM source_averages
                GROUP BY entity_id
            )
            SELECT 
                es.entity_id,
                es.source_count,
                es.total_mentions,
                es.sentiment_stddev,
                COALESCE(sv.cross_source_var, 0) as cross_source_variance
            FROM entity_stats es
            LEFT JOIN source_variance sv ON es.entity_id = sv.entity_id
            ORDER BY es.sentiment_stddev DESC
            LIMIT 1000
        """)
        
        results = self.session.execute(query, {
            'start_date': start_date,
            'end_date': end_date
        }).fetchall()
        
        volatility_records = []
        
        for row in results:
            # Calculate composite volatility score
            # Weight cross-source variance more heavily than temporal variance
            volatility_score = (
                0.6 * (row.cross_source_variance or 0) +
                0.4 * (row.sentiment_stddev or 0)
            )
            
            volatility_records.append({
                'entity_id': row.entity_id,
                'time_window_start': start_date,
                'time_window_end': end_date,
                'volatility_score': float(volatility_score),
                'source_divergence': float(row.cross_source_variance or 0),
                'mention_count': row.total_mentions
            })
        
        # Store volatility records
        if volatility_records:
            self._store_volatility_records(volatility_records)
    
    def _store_volatility_records(self, records: List[Dict]):
        """Store entity volatility records."""
        # Delete existing records for this time window
        if records:
            delete_query = text("""
                DELETE FROM entity_volatility
                WHERE 
                    time_window_start = :start_date
                    AND time_window_end = :end_date
            """)
            
            self.session.execute(delete_query, {
                'start_date': records[0]['time_window_start'],
                'end_date': records[0]['time_window_end']
            })
        
        # Insert new records
        insert_query = text("""
            INSERT INTO entity_volatility (
                entity_id, time_window_start, time_window_end,
                volatility_score, source_divergence, mention_count
            ) VALUES (
                :entity_id, :time_window_start, :time_window_end,
                :volatility_score, :source_divergence, :mention_count
            )
        """)
        
        for record in records:
            self.session.execute(insert_query, record)
            
        self.session.commit()
        logger.info(f"Stored volatility scores for {len(records)} entities")
        
        # Also store entity volatility in statistical database for intelligence analysis
        self._store_volatility_in_statistical_db(records)
    
    def detect_editorial_shifts(self, 
                              source_id: int, 
                              weeks: int = 12,
                              sensitivity: float = 2.0) -> List[Dict]:
        """Detect significant editorial shifts for a source."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(weeks=weeks)
        
        # Get weekly sentiment data
        query = text("""
            SELECT 
                std.entity_id,
                e.name as entity_name,
                std.week_start,
                std.avg_sentiment,
                std.sentiment_change
            FROM source_temporal_drift std
            JOIN entities e ON std.entity_id = e.id
            WHERE 
                std.source_id = :source_id
                AND std.week_start >= :start_date
                AND std.mention_count >= 5  -- Enough mentions for reliability
            ORDER BY std.entity_id, std.week_start
        """)
        
        results = self.session.execute(query, {
            'source_id': source_id,
            'start_date': start_date.date()
        }).fetchall()
        
        # Group by entity
        entity_timeseries = {}
        for row in results:
            if row.entity_id not in entity_timeseries:
                entity_timeseries[row.entity_id] = {
                    'name': row.entity_name,
                    'weeks': [],
                    'sentiments': []
                }
            entity_timeseries[row.entity_id]['weeks'].append(row.week_start)
            entity_timeseries[row.entity_id]['sentiments'].append(row.avg_sentiment)
        
        # Detect shifts for each entity
        shifts = []
        
        for entity_id, data in entity_timeseries.items():
            if len(data['sentiments']) < 4:  # Need at least 4 weeks
                continue
                
            sentiments = np.array(data['sentiments'])
            
            # Simple change detection: look for changes > sensitivity * historical std
            if len(sentiments) > 1:
                # Calculate rolling std (excluding current point)
                for i in range(2, len(sentiments)):
                    historical = sentiments[:i]
                    current = sentiments[i]
                    
                    hist_mean = np.mean(historical)
                    hist_std = np.std(historical)
                    
                    if hist_std > 0:
                        z_score = abs(current - hist_mean) / hist_std
                        
                        if z_score > sensitivity:
                            shifts.append({
                                'entity_id': entity_id,
                                'entity_name': data['name'],
                                'week': data['weeks'][i],
                                'old_sentiment': float(hist_mean),
                                'new_sentiment': float(current),
                                'change_magnitude': float(current - hist_mean),
                                'z_score': float(z_score)
                            })
        
        # Sort by recency and magnitude
        shifts.sort(key=lambda x: (x['week'], abs(x['z_score'])), reverse=True)
        
        return shifts[:20]  # Return top 20 shifts
    
    def _store_volatility_in_statistical_db(self, volatility_records: List[Dict]):
        """Store entity volatility records in statistical database for intelligence analysis."""
        try:
            for record in volatility_records:
                # Store baseline statistics for this entity's volatility
                self.statistical_db.store_baseline_statistics(
                    metric_type='entity_volatility',
                    entity_id=record['entity_id'],
                    mean_value=record['volatility_score'],
                    std_dev=record['source_divergence'],  # Use divergence as std measure
                    min_value=0.0,  # Volatility is always >= 0
                    max_value=record['volatility_score'],
                    data_start_date=record['time_window_start'],
                    data_end_date=record['time_window_end'],
                    sample_count=record['mention_count'],
                    window_weeks=1  # Weekly volatility measurement
                )
            
            logger.info(f"Stored {len(volatility_records)} volatility records in statistical database")
            
        except Exception as e:
            logger.error(f"Error storing volatility data in statistical database: {e}")
            # Don't fail the main process if statistical storage fails