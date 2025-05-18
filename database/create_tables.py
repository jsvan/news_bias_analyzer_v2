"""
Database initialization script for the News Bias Analyzer.
Creates database tables according to model definitions.
"""
import sys
import os
import logging
import argparse
from sqlalchemy import event, DDL, text

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

def setup_timescaledb_extension(engine):
    """
    Set up TimescaleDB extension.
    """
    try:
        connection = engine.connect()
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
        connection.commit()
        connection.close()
        logger.info("TimescaleDB extension configured")
        return True
    except Exception as e:
        logger.warning(f"Could not set up TimescaleDB extension: {e}")
        logger.warning("Continuing without TimescaleDB optimization.")
        return False

def setup_timescaledb_hypertables(engine):
    """
    Set up TimescaleDB hypertables for time-series data.
    
    This converts existing tables to hypertables to optimize
    performance for time-based queries.
    """
    try:
        connection = engine.connect()
        
        # Check if the entity_mentions table exists
        inspector = sa.inspect(engine)
        tables = inspector.get_table_names()
        
        # Create hypertable for entity_mentions if the table exists
        if 'entity_mentions' in tables:
            try:
                connection.execute(text("""
                    SELECT create_hypertable(
                        'entity_mentions', 
                        'created_at',
                        if_not_exists => TRUE
                    );
                """))
                logger.info("Hypertable for entity_mentions configured")
            except Exception as e:
                logger.warning(f"Could not create hypertable for entity_mentions: {e}")
        
        # Create hypertable for news_articles if the table exists
        if 'news_articles' in tables:
            try:
                connection.execute(text("""
                    SELECT create_hypertable(
                        'news_articles', 
                        'publish_date',
                        if_not_exists => TRUE
                    );
                """))
                logger.info("Hypertable for news_articles configured")
            except Exception as e:
                logger.warning(f"Could not create hypertable for news_articles: {e}")
        
        connection.commit()
        connection.close()
        return True
    except Exception as e:
        logger.warning(f"Could not set up TimescaleDB hypertables: {e}")
        logger.warning("Continuing without TimescaleDB hypertable optimization.")
        return False

def setup_timescaledb(engine):
    """
    Set up TimescaleDB extension for time-series data.
    
    This creates hypertables for time-series data to optimize
    performance for time-based queries.
    """
    # First, set up the extension
    if setup_timescaledb_extension(engine):
        # Only set up hypertables if extension setup was successful
        setup_timescaledb_hypertables(engine)
        logger.info("TimescaleDB setup completed")
    else:
        logger.warning("TimescaleDB extension setup failed, skipping hypertable setup")

def check_if_tables_exist(db_manager):
    """
    Check if any tables from our models already exist in the database.
    
    Returns:
        bool: True if any tables exist, False otherwise
    """
    from sqlalchemy import inspect
    inspector = inspect(db_manager.engine)
    existing_tables = inspector.get_table_names()
    
    # Get all table names from our models
    model_tables = [table.name for table in Base.metadata.tables.values()]
    
    # Check if any of our model tables already exist
    for table in model_tables:
        if table in existing_tables:
            logger.info(f"Found existing table: {table}")
            return True
    
    return False

def create_tables(database_url, drop_existing=False, use_timescaledb=False, skip_if_exists=True):
    """
    Create database tables based on SQLAlchemy models.
    
    Args:
        database_url: URL for database connection
        drop_existing: If True, drop existing tables before creating
        use_timescaledb: If True, configure TimescaleDB extension
        skip_if_exists: If True, skip table creation if tables already exist
    """
    try:
        logger.info(f"Connecting to database: {database_url}")
        db_manager = DatabaseManager(database_url)
        
        # Always set up TimescaleDB extension first if requested
        # (This is safe to do regardless of whether tables exist)
        if use_timescaledb:
            logger.info("Setting up TimescaleDB extension...")
            setup_timescaledb_extension(db_manager.engine)
        
        # Check if tables already exist
        tables_exist = check_if_tables_exist(db_manager)
        
        if tables_exist and skip_if_exists and not drop_existing:
            logger.info("Database tables already exist. Skipping table creation.")
            
            # Set up TimescaleDB hypertables if requested (will only convert existing tables)
            if use_timescaledb:
                logger.info("Setting up TimescaleDB hypertables for existing tables...")
                setup_timescaledb_hypertables(db_manager.engine)
            
            # Create a session and check connection
            session = db_manager.get_session()
            session.execute(text("SELECT 1"))
            session.close()
            
            logger.info("Database connection verified successfully")
            return True
        
        # Drop all tables if requested
        if drop_existing:
            logger.warning("Dropping all existing tables...")
            Base.metadata.drop_all(db_manager.engine)
            logger.info("All tables dropped")
        
        # Create tables
        logger.info("Creating tables...")
        Base.metadata.create_all(db_manager.engine)
        logger.info("Tables created successfully")
        
        # Now set up TimescaleDB hypertables AFTER tables are created
        if use_timescaledb:
            logger.info("Setting up TimescaleDB hypertables for newly created tables...")
            setup_timescaledb_hypertables(db_manager.engine)
        
        # Create a session and check connection
        session = db_manager.get_session()
        session.execute(text("SELECT 1"))
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
    parser.add_argument('--force-create', action='store_true',
                        help='Force table creation even if tables already exist')
    args = parser.parse_args()
    
    # Get database URL from args or environment
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("No database URL provided. Use --database-url or set DATABASE_URL environment variable.")
        return 1
    
    result = create_tables(
        database_url=database_url,
        drop_existing=args.drop_existing,
        use_timescaledb=args.use_timescaledb,
        skip_if_exists=not args.force_create
    )
    
    return 0 if result else 1

if __name__ == "__main__":
    sys.exit(main())