#!/usr/bin/env python3
"""
Run migration 013 to add Hotelling T² score support.

This migration adds:
1. hotelling_t2_score column to news_articles table
2. weekly_sentiment_stats table for efficient T² calculation
3. Necessary indexes for performance

Run with: ./run.sh custom 'database/run_migration_013.py'
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run the migration to add Hotelling T² support."""
    
    # Get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False
    
    try:
        # Create engine and session
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("Starting migration 013: Add Hotelling T² score...")
        
        # Check if column already exists
        check_column = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='news_articles' 
                AND column_name='hotelling_t2_score'
        """)
        
        result = session.execute(check_column).fetchone()
        
        if result:
            logger.info("Column hotelling_t2_score already exists, skipping column creation")
        else:
            # Add hotelling_t2_score column
            logger.info("Adding hotelling_t2_score column to news_articles...")
            add_column = text("""
                ALTER TABLE news_articles 
                ADD COLUMN hotelling_t2_score FLOAT
            """)
            session.execute(add_column)
            session.commit()
            logger.info("✓ Added hotelling_t2_score column")
        
        # Check if weekly_sentiment_stats table exists
        check_table = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='weekly_sentiment_stats'
        """)
        
        result = session.execute(check_table).fetchone()
        
        if result:
            logger.info("Table weekly_sentiment_stats already exists, skipping table creation")
        else:
            # Create weekly_sentiment_stats table
            logger.info("Creating weekly_sentiment_stats table...")
            create_table = text("""
                CREATE TABLE weekly_sentiment_stats (
                    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                    week_start DATE NOT NULL,
                    mean_power FLOAT,
                    mean_moral FLOAT,
                    variance_power FLOAT,
                    variance_moral FLOAT,
                    covariance FLOAT,
                    sample_count INTEGER,
                    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    PRIMARY KEY (entity_id, week_start)
                )
            """)
            session.execute(create_table)
            session.commit()
            logger.info("✓ Created weekly_sentiment_stats table")
        
        # Create indexes
        logger.info("Creating indexes...")
        
        # Index for fast percentile queries
        try:
            create_idx1 = text("""
                CREATE INDEX IF NOT EXISTS idx_articles_week_t2
                ON news_articles(processed_at, hotelling_t2_score)
                WHERE hotelling_t2_score IS NOT NULL
            """)
            session.execute(create_idx1)
            logger.info("✓ Created idx_articles_week_t2")
        except Exception as e:
            logger.warning(f"Index idx_articles_week_t2 might already exist: {e}")
        
        # Index for efficient weekly stats lookups
        try:
            create_idx2 = text("""
                CREATE INDEX IF NOT EXISTS idx_weekly_stats_week
                ON weekly_sentiment_stats(week_start, entity_id)
            """)
            session.execute(create_idx2)
            logger.info("✓ Created idx_weekly_stats_week")
        except Exception as e:
            logger.warning(f"Index idx_weekly_stats_week might already exist: {e}")
        
        # Index for cleanup of old weekly stats
        try:
            create_idx3 = text("""
                CREATE INDEX IF NOT EXISTS idx_weekly_stats_updated
                ON weekly_sentiment_stats(updated_at)
            """)
            session.execute(create_idx3)
            logger.info("✓ Created idx_weekly_stats_updated")
        except Exception as e:
            logger.warning(f"Index idx_weekly_stats_updated might already exist: {e}")
        
        session.commit()
        
        # Populate initial weekly statistics
        logger.info("Populating initial weekly statistics...")
        populate_stats = text("""
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
            HAVING COUNT(*) >= 5
            ON CONFLICT (entity_id, week_start) DO NOTHING
        """)
        
        result = session.execute(populate_stats)
        stats_count = result.rowcount
        session.commit()
        logger.info(f"✓ Populated statistics for {stats_count} entities")
        
        logger.info("Migration 013 completed successfully!")
        
        # Show summary
        summary = text("""
            SELECT 
                COUNT(*) FILTER (WHERE hotelling_t2_score IS NOT NULL) as articles_with_t2,
                COUNT(*) as total_articles,
                (SELECT COUNT(*) FROM weekly_sentiment_stats) as weekly_stats_entries
            FROM news_articles
            WHERE analysis_status = 'completed'
        """)
        
        result = session.execute(summary).fetchone()
        
        logger.info("\n=== Migration Summary ===")
        logger.info(f"Total articles: {result.total_articles}")
        logger.info(f"Articles with T² score: {result.articles_with_t2}")
        logger.info(f"Weekly statistics entries: {result.weekly_stats_entries}")
        logger.info("\nNote: T² scores will be calculated for new articles going forward.")
        logger.info("To backfill T² scores for existing articles, run a separate backfill script.")
        
        session.close()
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)