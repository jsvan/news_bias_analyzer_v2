"""
Database integration module for the news scraper.
Handles batch insertion of articles into the database.
"""

import os
import sys
import logging
import datetime
import time
import signal
from typing import List, Dict, Any, Optional
import traceback
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import DatabaseManager
from database.models import NewsArticle, NewsSource
from scrapers.news_sources import get_news_sources
from scrapers.parallel_scraper import scrape_feeds

# Global database session that can be accessed by signal handlers
db_manager = None
current_session = None

def insert_articles_batch(db_manager: DatabaseManager, articles: List[Dict[str, Any]]) -> int:
    """
    Insert a batch of articles into the database in a single transaction.
    
    Args:
        db_manager: Database manager instance
        articles: List of article dictionaries
        
    Returns:
        Number of articles successfully inserted
    """
    if not articles:
        return 0
        
    # Start a session
    global current_session
    session = db_manager.get_session()
    current_session = session  # Set global session for signal handler
    inserted_count = 0
    
    try:
        # Cache source IDs to minimize queries
        source_cache = {}
        
        # Start transaction
        for article in articles:
            # Skip articles without text
            if not article.get('text'):
                continue
                
            # Check if article already exists
            existing = session.query(NewsArticle).filter_by(id=article['id']).first()
            if existing:
                logger.debug(f"Article already exists: {article['url']}")
                continue
                
            # Get or create source
            source_name = article['source_name']
            if source_name in source_cache:
                source_id = source_cache[source_name]
            else:
                source = session.query(NewsSource).filter_by(name=source_name).first()
                if not source:
                    # Create new source
                    source = NewsSource(
                        name=source_name,
                        base_url=article.get('feed_url', ''),
                        country=article.get('country', None),
                        language=article.get('language', None)
                    )
                    session.add(source)
                    session.flush()
                    
                source_id = source.id
                source_cache[source_name] = source_id
                
            # Create new article
            new_article = NewsArticle(
                id=article['id'],
                source_id=source_id,
                url=article['url'],
                title=article.get('title', ''),
                text=article.get('text', ''),
                html=article.get('html', ''),
                publish_date=article.get('publish_date', datetime.datetime.now()),
                authors=article.get('authors', []),
                language=article.get('language', 'en'),
                top_image=article.get('top_image', None),
                scraped_at=article.get('scraped_at', datetime.datetime.now()),
                extraction_info=article.get('extraction_info', {})
            )
            
            session.add(new_article)
            inserted_count += 1
            
        # Commit the transaction
        session.commit()
        logger.info(f"Successfully inserted {inserted_count} articles")
        return inserted_count
        
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"Error inserting articles: {str(e)}")
        logger.error(traceback.format_exc())
        return 0
        
    finally:
        if session:
            session.close()
        current_session = None  # Clear the global session reference

def handle_keyboard_interrupt(sig, frame):
    """Handle keyboard interrupt (Ctrl+C) by committing any pending changes."""
    logger.info("\n" + "!" * 80)
    logger.info("! KEYBOARD INTERRUPT DETECTED (Ctrl+C)")
    logger.info("! Attempting to commit any pending changes before exiting...")
    logger.info("!" * 80 + "\n")

    # Check if we have a global session
    global current_session, db_manager
    
    if current_session is not None:
        try:
            # Commit any pending changes
            current_session.commit()
            logger.info("\n" + "#" * 80)
            logger.info("# EMERGENCY COMMIT SUCCESSFUL: Changes saved before exit")
            logger.info("# Database transaction completed and saved to disk")
            logger.info("#" * 80 + "\n")

            # Try to get a count of articles to verify database connection
            try:
                count = current_session.query(NewsArticle).count()
                logger.info(f"Current article count in database: {count}")
            except Exception as count_error:
                logger.error(f"Could not get article count: {str(count_error)}")

        except Exception as commit_error:
            logger.error(f"ERROR - EMERGENCY COMMIT FAILED: {str(commit_error)}")
            logger.error(traceback.format_exc())

            # Try to roll back
            try:
                current_session.rollback()
                logger.info("Successfully rolled back the session to a clean state")
            except Exception as rollback_error:
                logger.error(f"CRITICAL - ROLLBACK FAILED: {str(rollback_error)}")
        
        finally:
            # Always try to close the session
            try:
                current_session.close()
                logger.info("Database session closed")
            except Exception as close_error:
                logger.error(f"ERROR - Failed to close database session: {str(close_error)}")
    else:
        logger.info("No active database session found")

    logger.info("Exiting gracefully after Ctrl+C interrupt")
    sys.exit(0)

def run_scraper_with_db() -> int:
    """
    Run the scraper and save results to the database.
    
    Returns:
        Total number of articles inserted
    """
    global db_manager, current_session
    
    # Set up signal handler for keyboard interrupt (Ctrl+C)
    signal.signal(signal.SIGINT, handle_keyboard_interrupt)
    
    try:
        # Get limit from environment variable
        limit_per_feed = int(os.getenv('SCRAPER_LIMIT_PER_FEED', 5))
        
        # Initialize database connection
        logger.info("Initializing database connection")
        db_manager = DatabaseManager()
        
        # Get news sources
        news_sources = get_news_sources()
        
        # Convert to feed configs
        feed_configs = []
        for source in news_sources:
            for feed_url in source.get('rss_feeds', []):
                feed_configs.append({
                    'url': feed_url,
                    'source_name': source['name'],
                    'country': source.get('country', None),
                    'language': source.get('language', None)
                })
                
        # Run the scraper
        logger.info(f"Starting scraper with {len(feed_configs)} feeds (limit: {limit_per_feed} articles per feed)")
        logger.info("NOTE: You can press Ctrl+C at any time to safely exit and commit pending changes")
        
        articles = scrape_feeds(feed_configs, limit_per_feed)
        
        if not articles:
            logger.warning("No articles retrieved from scraper")
            return 0
            
        logger.info(f"Scraper returned {len(articles)} articles")
        
        # Insert articles in batches of 20
        total_inserted = 0
        batch_size = int(os.getenv('SCRAPER_BATCH_SIZE', 20))
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            logger.info(f"Inserting batch {i//batch_size + 1}/{(len(articles) + batch_size - 1)//batch_size} ({len(batch)} articles)")
            
            batch_inserted = insert_articles_batch(db_manager, batch)
            total_inserted += batch_inserted
            
            # Brief pause between batches to avoid database contention
            if i + batch_size < len(articles):
                time.sleep(1)
        
        logger.info(f"Scraping completed. Total articles inserted: {total_inserted}")
        return total_inserted
        
    except Exception as e:
        logger.error(f"Error in scraper process: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Try to commit any pending changes before exiting due to error
        if current_session is not None:
            try:
                logger.info("Attempting to commit any pending changes before exiting due to error...")
                current_session.commit()
                logger.info("Emergency commit successful")
            except Exception as commit_error:
                logger.error(f"Emergency commit failed: {str(commit_error)}")
                try:
                    current_session.rollback()
                    logger.info("Session rolled back")
                except:
                    pass
            finally:
                try:
                    current_session.close()
                    logger.info("Database session closed")
                except:
                    pass
        
        return 0

if __name__ == "__main__":
    # Run scraper
    run_scraper_with_db()