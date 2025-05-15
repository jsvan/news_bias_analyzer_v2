#!/usr/bin/env python3
"""
Run the Alembic database migration to update the news_articles table
with the analysis_status, batch_id, and last_analysis_attempt columns.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("migration")

def go():
    """Main function to run the migration."""
    # Get the project root directory
    project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    database_dir = project_root / "database"
    
    logger.info(f"Project root: {project_root}")
    logger.info(f"Database directory: {database_dir}")
    
    # Check if migrations directory exists
    migrations_dir = database_dir / "migrations"
    if not migrations_dir.exists():
        logger.error(f"Migrations directory not found: {migrations_dir}")
        return
    
    logger.info("Checking database connection...")
    
    # Get database URL from environment
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set")
        return
    
    logger.info(f"Database URL: {db_url}")
    
    # Check if the table exists
    try:
        from sqlalchemy import create_engine, inspect, text
        
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        if "news_articles" not in inspector.get_table_names():
            logger.error("news_articles table does not exist")
            return
        
        # Check if columns already exist
        columns = inspector.get_columns("news_articles")
        column_names = [col["name"] for col in columns]
        
        if "analysis_status" in column_names:
            logger.info("Column 'analysis_status' already exists")
            return
        
        logger.info("Table 'news_articles' exists and needs migration")
        
        # SQL to add the required columns
        with engine.connect() as connection:
            # Add analysis_status column
            connection.execute(text("""
                ALTER TABLE news_articles
                ADD COLUMN analysis_status VARCHAR(20) DEFAULT 'unanalyzed' NOT NULL
            """))
            
            # Add batch_id column
            connection.execute(text("""
                ALTER TABLE news_articles
                ADD COLUMN batch_id VARCHAR(50) NULL
            """))
            
            # Add last_analysis_attempt column
            connection.execute(text("""
                ALTER TABLE news_articles
                ADD COLUMN last_analysis_attempt TIMESTAMP NULL
            """))
            
            # Create indexes
            connection.execute(text("""
                CREATE INDEX idx_news_articles_analysis_status
                ON news_articles(analysis_status)
            """))
            
            connection.execute(text("""
                CREATE INDEX idx_news_articles_batch_id
                ON news_articles(batch_id)
            """))
            
            # Update existing articles with processed_at to have 'completed' status
            connection.execute(text("""
                UPDATE news_articles 
                SET analysis_status = 'completed' 
                WHERE processed_at IS NOT NULL
            """))
            
            connection.commit()
        
        logger.info("Migration completed successfully")
        
        # Get counts of articles by status
        with engine.connect() as connection:
            completed_count = connection.execute(text("""
                SELECT COUNT(*) FROM news_articles
                WHERE analysis_status = 'completed'
            """)).scalar()
            
            unanalyzed_count = connection.execute(text("""
                SELECT COUNT(*) FROM news_articles
                WHERE analysis_status = 'unanalyzed'
            """)).scalar()
            
            total_count = connection.execute(text("""
                SELECT COUNT(*) FROM news_articles
            """)).scalar()
        
        logger.info(f"Article counts after migration:")
        logger.info(f"  Total articles: {total_count}")
        logger.info(f"  Completed articles: {completed_count}")
        logger.info(f"  Unanalyzed articles: {unanalyzed_count}")
        
    except Exception as e:
        logger.error(f"Error performing migration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return

if __name__ == "__main__":
    go()