"""
Database initialization script for the News Bias Analyzer.
Creates database tables according to model definitions.
"""
import sys
import os
import logging
import argparse
from sqlalchemy import event, DDL

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import Base
from database.db import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_timescaledb(engine):
    """
    Set up TimescaleDB extension for time-series data.
    
    This creates hypertables for time-series data to optimize
    performance for time-based queries.
    """
    try:
        # Create the extension if it doesn't exist
        event.listen(
            Base.metadata,
            'after_create',
            DDL("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        )
        
        # Create hypertable for entity_mentions
        event.listen(
            Base.metadata,
            'after_create',
            DDL("""
                SELECT create_hypertable(
                    'entity_mentions', 
                    'created_at',
                    if_not_exists => TRUE
                );
            """)
        )
        
        # Create hypertable for news_articles
        event.listen(
            Base.metadata,
            'after_create',
            DDL("""
                SELECT create_hypertable(
                    'news_articles', 
                    'publish_date',
                    if_not_exists => TRUE
                );
            """)
        )
        
        logger.info("TimescaleDB extension and hypertables configured")
    except Exception as e:
        logger.warning(f"Could not set up TimescaleDB: {e}")
        logger.warning("Continuing without TimescaleDB optimization.")

def create_tables(database_url, drop_existing=False, use_timescaledb=False):
    """
    Create database tables based on SQLAlchemy models.
    
    Args:
        database_url: URL for database connection
        drop_existing: If True, drop existing tables before creating
        use_timescaledb: If True, configure TimescaleDB extension
    """
    try:
        logger.info(f"Connecting to database: {database_url}")
        db_manager = DatabaseManager(database_url)
        
        # Set up TimescaleDB if requested
        if use_timescaledb:
            setup_timescaledb(db_manager.engine)
        
        # Drop all tables if requested
        if drop_existing:
            logger.warning("Dropping all existing tables...")
            Base.metadata.drop_all(db_manager.engine)
            logger.info("All tables dropped")
        
        # Create tables
        logger.info("Creating tables...")
        Base.metadata.create_all(db_manager.engine)
        logger.info("Tables created successfully")
        
        # Create a session and check connection
        session = db_manager.get_session()
        session.execute("SELECT 1")
        session.close()
        
        logger.info("Database setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        return False

def main():
    """Main entry point for database setup from command line."""
    parser = argparse.ArgumentParser(description='Set up the News Bias Analyzer database')
    parser.add_argument('--database-url', help='Database connection URL')
    parser.add_argument('--drop-existing', action='store_true', 
                        help='Drop existing tables before creating new ones')
    parser.add_argument('--use-timescaledb', action='store_true',
                        help='Configure TimescaleDB extension for time-series data')
    args = parser.parse_args()
    
    # Get database URL from args or environment
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("No database URL provided. Use --database-url or set DATABASE_URL environment variable.")
        return 1
    
    result = create_tables(
        database_url=database_url,
        drop_existing=args.drop_existing,
        use_timescaledb=args.use_timescaledb
    )
    
    return 0 if result else 1

if __name__ == "__main__":
    sys.exit(main())