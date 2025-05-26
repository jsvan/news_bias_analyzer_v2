#!/usr/bin/env python3
"""
Run migration 012 - Add source similarity tables
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from database.models import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Execute migration 012 to add source similarity tables."""
    
    engine = get_db_connection()
    
    with engine.begin() as conn:
        logger.info("Creating source_similarity_matrix table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS source_similarity_matrix (
                id SERIAL PRIMARY KEY,
                source_id_1 INTEGER NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
                source_id_2 INTEGER NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
                similarity_score FLOAT NOT NULL,
                correlation_score FLOAT,
                common_entities INTEGER NOT NULL,
                calculation_method VARCHAR(50) NOT NULL,
                time_window_start TIMESTAMP NOT NULL,
                time_window_end TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        
        # Indexes
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_source_similarity_sources_window 
            ON source_similarity_matrix(source_id_1, source_id_2, time_window_start, time_window_end)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_source_similarity_score 
            ON source_similarity_matrix(similarity_score)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_source_similarity_window 
            ON source_similarity_matrix(time_window_start, time_window_end)
        """))
        
        logger.info("Creating source_temporal_drift table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS source_temporal_drift (
                id SERIAL PRIMARY KEY,
                source_id INTEGER NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
                entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                week_start DATE NOT NULL,
                avg_sentiment FLOAT NOT NULL,
                sentiment_change FLOAT,
                mention_count INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        
        # Indexes
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_source_drift_lookup 
            ON source_temporal_drift(source_id, entity_id, week_start)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_source_drift_week 
            ON source_temporal_drift(week_start)
        """))
        
        logger.info("Creating entity_volatility table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS entity_volatility (
                id SERIAL PRIMARY KEY,
                entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                time_window_start TIMESTAMP NOT NULL,
                time_window_end TIMESTAMP NOT NULL,
                volatility_score FLOAT NOT NULL,
                trend_direction FLOAT,
                source_divergence FLOAT,
                mention_count INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        
        # Indexes
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_volatility_lookup 
            ON entity_volatility(entity_id, time_window_start, time_window_end)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_entity_volatility_score 
            ON entity_volatility(volatility_score)
        """))
        
        logger.info("Creating source_clusters table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS source_clusters (
                id SERIAL PRIMARY KEY,
                source_id INTEGER NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
                cluster_id VARCHAR(50) NOT NULL,
                cluster_level INTEGER NOT NULL,
                similarity_to_centroid FLOAT,
                assigned_date DATE NOT NULL,
                is_centroid BOOLEAN NOT NULL DEFAULT FALSE,
                metadata JSONB
            )
        """))
        
        # Indexes
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_source_clusters_lookup 
            ON source_clusters(source_id, assigned_date)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_source_clusters_cluster 
            ON source_clusters(cluster_id, assigned_date)
        """))
        
        logger.info("Migration 012 completed successfully!")
        
        # Verify tables were created
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('source_similarity_matrix', 'source_temporal_drift', 
                              'entity_volatility', 'source_clusters')
            ORDER BY table_name
        """))
        
        tables = [row.table_name for row in result]
        logger.info(f"Created tables: {', '.join(tables)}")
        
        if len(tables) != 4:
            logger.error("Not all tables were created!")
            return False
            
    return True


if __name__ == "__main__":
    try:
        success = run_migration()
        if success:
            logger.info("Migration completed successfully")
        else:
            logger.error("Migration failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        sys.exit(1)