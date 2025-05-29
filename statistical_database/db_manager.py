"""
Statistical Database Manager

Manages the SQLite database for intelligence analysis results and state.
Provides a clean interface for storing and retrieving statistical findings.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class StatisticalDBManager:
    """Manager for the SQLite statistical database."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to statistical_database folder
            base_dir = Path(__file__).parent
            db_path = base_dir / "intelligence_analysis.db"
        
        self.db_path = str(db_path)
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the database with schema if it doesn't exist."""
        schema_path = Path(__file__).parent / "schema.sql"
        
        with sqlite3.connect(self.db_path) as conn:
            # Check if tables exist
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='analysis_state'
            """)
            
            if not cursor.fetchone():
                logger.info("Initializing statistical database with schema")
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                conn.executescript(schema_sql)
                logger.info("Database initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with automatic cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
    
    def store_analysis_state(self, 
                           analysis_type: str,
                           time_window_start: datetime,
                           time_window_end: datetime,
                           state_data: Dict[str, Any],
                           entity_id: Optional[int] = None,
                           source_id: Optional[int] = None,
                           metadata: Optional[Dict[str, Any]] = None):
        """Store the latest analysis state (overwrites existing)."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO analysis_state (
                    analysis_type, entity_id, source_id, 
                    time_window_start, time_window_end, 
                    state_data, metadata, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_type, entity_id, source_id,
                time_window_start, time_window_end,
                json.dumps(state_data),
                json.dumps(metadata) if metadata else None,
                datetime.utcnow()
            ))
            conn.commit()
    
    def get_analysis_state(self, 
                          analysis_type: str,
                          entity_id: Optional[int] = None,
                          source_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get the latest analysis state for a given type."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM analysis_state 
                WHERE analysis_type = ? AND entity_id = ? AND source_id = ?
                ORDER BY last_updated DESC LIMIT 1
            """, (analysis_type, entity_id, source_id))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'analysis_type': row['analysis_type'],
                    'entity_id': row['entity_id'],
                    'source_id': row['source_id'],
                    'time_window_start': datetime.fromisoformat(row['time_window_start']),
                    'time_window_end': datetime.fromisoformat(row['time_window_end']),
                    'state_data': json.loads(row['state_data']),
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None,
                    'last_updated': datetime.fromisoformat(row['last_updated'])
                }
            return None
    
    def store_statistical_finding(self,
                                finding_type: str,
                                title: str,
                                description: str,
                                p_value: float,
                                event_start_date: datetime,
                                baseline_value: float,
                                current_value: float,
                                severity_score: float,
                                dashboard_category: str,
                                entity_id: Optional[int] = None,
                                source_id: Optional[int] = None,
                                source_id_2: Optional[int] = None,
                                cluster_id: Optional[str] = None,
                                z_score: Optional[float] = None,
                                effect_size: Optional[float] = None,
                                confidence_interval: Optional[Tuple[float, float]] = None,
                                event_end_date: Optional[datetime] = None,
                                change_magnitude: Optional[float] = None,
                                consecutive_days: Optional[int] = None,
                                priority_score: float = 0.5,
                                supporting_data: Optional[Dict[str, Any]] = None) -> int:
        """Store a statistical finding. Returns the finding ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            ci_low = confidence_interval[0] if confidence_interval else None
            ci_high = confidence_interval[1] if confidence_interval else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO statistical_findings (
                    finding_type, entity_id, source_id, source_id_2, cluster_id,
                    p_value, z_score, effect_size, confidence_interval_low, confidence_interval_high,
                    event_start_date, event_end_date, baseline_value, current_value,
                    change_magnitude, consecutive_days, title, description, severity_score,
                    priority_score, dashboard_category, supporting_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                finding_type, entity_id, source_id, source_id_2, cluster_id,
                p_value, z_score, effect_size, ci_low, ci_high,
                event_start_date, event_end_date, baseline_value, current_value,
                change_magnitude, consecutive_days, title, description, severity_score,
                priority_score, dashboard_category,
                json.dumps(supporting_data) if supporting_data else None
            ))
            
            finding_id = cursor.lastrowid
            conn.commit()
            return finding_id
    
    def get_active_findings(self, 
                           dashboard_category: Optional[str] = None,
                           limit: int = 20) -> List[Dict[str, Any]]:
        """Get active findings for dashboard display."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM statistical_findings 
                WHERE is_active = TRUE
            """
            params = []
            
            if dashboard_category:
                query += " AND dashboard_category = ?"
                params.append(dashboard_category)
            
            query += " ORDER BY priority_score DESC, detection_date DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            findings = []
            for row in rows:
                finding = dict(row)
                # Parse JSON fields
                if finding['supporting_data']:
                    finding['supporting_data'] = json.loads(finding['supporting_data'])
                # Convert datetime strings
                for date_field in ['detection_date', 'event_start_date', 'event_end_date']:
                    if finding[date_field]:
                        finding[date_field] = datetime.fromisoformat(finding[date_field])
                findings.append(finding)
            
            return findings
    
    def store_clustering_cache(self,
                             time_window_start: datetime,
                             time_window_end: datetime,
                             cluster_id: str,
                             source_count: int,
                             country: Optional[str] = None,
                             intra_cluster_similarity: Optional[float] = None,
                             silhouette_score: Optional[float] = None,
                             centroid_vector: Optional[Dict[int, float]] = None,
                             previous_similarity: Optional[float] = None,
                             similarity_change: Optional[float] = None,
                             member_changes: Optional[List[str]] = None):
        """Store processed clustering results."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO clustering_cache (
                    time_window_start, time_window_end, country, cluster_id, source_count,
                    intra_cluster_similarity, silhouette_score, centroid_vector,
                    previous_similarity, similarity_change, member_changes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time_window_start, time_window_end, country, cluster_id, source_count,
                intra_cluster_similarity, silhouette_score,
                json.dumps(centroid_vector) if centroid_vector else None,
                previous_similarity, similarity_change,
                json.dumps(member_changes) if member_changes else None
            ))
            conn.commit()
    
    def store_baseline_statistics(self,
                                metric_type: str,
                                mean_value: float,
                                std_dev: float,
                                min_value: float,
                                max_value: float,
                                data_start_date: datetime,
                                data_end_date: datetime,
                                sample_count: int,
                                entity_id: Optional[int] = None,
                                source_id: Optional[int] = None,
                                country: Optional[str] = None,
                                window_weeks: int = 12,
                                percentile_95: Optional[float] = None,
                                percentile_5: Optional[float] = None,
                                trend_slope: Optional[float] = None,
                                trend_r_squared: Optional[float] = None):
        """Store baseline statistics for anomaly detection."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO baseline_statistics (
                    metric_type, entity_id, source_id, country, window_weeks,
                    mean_value, std_dev, min_value, max_value, percentile_95, percentile_5,
                    trend_slope, trend_r_squared, data_start_date, data_end_date, sample_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric_type, entity_id, source_id, country, window_weeks,
                mean_value, std_dev, min_value, max_value, percentile_95, percentile_5,
                trend_slope, trend_r_squared, data_start_date, data_end_date, sample_count
            ))
            conn.commit()
    
    def get_baseline_statistics(self,
                              metric_type: str,
                              entity_id: Optional[int] = None,
                              source_id: Optional[int] = None,
                              country: Optional[str] = None,
                              window_weeks: int = 12) -> Optional[Dict[str, Any]]:
        """Get the latest baseline statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM baseline_statistics 
                WHERE metric_type = ? AND entity_id = ? AND source_id = ? 
                      AND country = ? AND window_weeks = ?
                ORDER BY calculation_date DESC LIMIT 1
            """, (metric_type, entity_id, source_id, country, window_weeks))
            
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # Convert datetime strings
                for date_field in ['calculation_date', 'data_start_date', 'data_end_date']:
                    if result[date_field]:
                        result[date_field] = datetime.fromisoformat(result[date_field])
                return result
            return None
    
    def store_source_divergence(self,
                              source_id_1: int,
                              source_id_2: int,
                              historical_correlation: float,
                              historical_window_start: datetime,
                              historical_window_end: datetime,
                              recent_correlation: float,
                              recent_window_start: datetime,
                              recent_window_end: datetime,
                              divergence_p_value: float,
                              divergence_magnitude: float,
                              top_divergent_entities: List[Dict[str, Any]],
                              is_significant: bool = None):
        """Store source divergence analysis."""
        if is_significant is None:
            is_significant = divergence_p_value < 0.01
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if this divergence already exists
            cursor.execute("""
                SELECT id FROM source_divergence_tracking 
                WHERE source_id_1 = ? AND source_id_2 = ? AND recent_window_start = ?
            """, (source_id_1, source_id_2, recent_window_start))
            
            if cursor.fetchone():
                # Update existing
                conn.execute("""
                    UPDATE source_divergence_tracking SET
                        historical_correlation = ?, historical_window_start = ?, historical_window_end = ?,
                        recent_correlation = ?, recent_window_end = ?, divergence_p_value = ?,
                        divergence_magnitude = ?, top_divergent_entities = ?, is_significant = ?,
                        last_updated = ?
                    WHERE source_id_1 = ? AND source_id_2 = ? AND recent_window_start = ?
                """, (
                    historical_correlation, historical_window_start, historical_window_end,
                    recent_correlation, recent_window_end, divergence_p_value,
                    divergence_magnitude, json.dumps(top_divergent_entities), is_significant,
                    datetime.utcnow(), source_id_1, source_id_2, recent_window_start
                ))
            else:
                # Insert new
                conn.execute("""
                    INSERT INTO source_divergence_tracking (
                        source_id_1, source_id_2, historical_correlation,
                        historical_window_start, historical_window_end,
                        recent_correlation, recent_window_start, recent_window_end,
                        divergence_p_value, divergence_magnitude, top_divergent_entities,
                        is_significant
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    source_id_1, source_id_2, historical_correlation,
                    historical_window_start, historical_window_end,
                    recent_correlation, recent_window_start, recent_window_end,
                    divergence_p_value, divergence_magnitude, json.dumps(top_divergent_entities),
                    is_significant
                ))
            
            conn.commit()
    
    def get_significant_divergences(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most significant source divergences."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM source_divergence_tracking 
                WHERE is_significant = TRUE
                ORDER BY divergence_magnitude DESC, last_updated DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            divergences = []
            for row in rows:
                divergence = dict(row)
                # Parse JSON fields
                if divergence['top_divergent_entities']:
                    divergence['top_divergent_entities'] = json.loads(divergence['top_divergent_entities'])
                # Convert datetime strings
                for date_field in ['historical_window_start', 'historical_window_end', 
                                 'recent_window_start', 'recent_window_end', 
                                 'first_detected', 'last_updated']:
                    if divergence[date_field]:
                        divergence[date_field] = datetime.fromisoformat(divergence[date_field])
                divergences.append(divergence)
            
            return divergences
    
    def cleanup_old_findings(self, days_to_keep: int = 90):
        """Clean up old findings that are no longer relevant."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM statistical_findings 
                WHERE detection_date < ? AND is_active = FALSE
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Cleaned up {deleted_count} old statistical findings")
            return deleted_count
    
    def increment_system_metric(self, metric_name: str, increment: int = 1) -> int:
        """Increment a system metric and return the new value."""
        with self.get_connection() as conn:
            # Create table if it doesn't exist (for existing databases)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    metric_name TEXT PRIMARY KEY,
                    metric_value INTEGER NOT NULL DEFAULT 0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # Insert or update the metric
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_metrics (metric_name, metric_value, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(metric_name) DO UPDATE SET
                    metric_value = metric_value + ?,
                    last_updated = CURRENT_TIMESTAMP
            """, (metric_name, increment, increment))
            
            # Get the new value
            cursor.execute("SELECT metric_value FROM system_metrics WHERE metric_name = ?", (metric_name,))
            result = cursor.fetchone()
            
            conn.commit()
            return result[0] if result else increment
    
    def get_system_metric(self, metric_name: str) -> int:
        """Get the current value of a system metric."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Try to get the metric
            cursor.execute("""
                SELECT metric_value FROM system_metrics 
                WHERE metric_name = ?
            """, (metric_name,))
            
            result = cursor.fetchone()
            return result[0] if result else 0