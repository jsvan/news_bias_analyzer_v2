"""
Database integration module for the news scraper.
Handles batch insertion of articles into the database.
"""

import os
import sys
import logging
import datetime
import time
import json
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
        print("No articles to insert")
        return 0
        
    # Start a session
    global current_session
    try:
        session = db_manager.get_session()
        print(f"Database session created successfully: {session}")
        current_session = session  # Set global session for signal handler
    except Exception as session_error:
        print(f"CRITICAL ERROR: Failed to create database session: {session_error}")
        logger.error(f"Failed to create database session: {session_error}")
        return 0
        
    inserted_count = 0
    skipped_count = 0
    
    # Log the initial state
    print(f"\n{'*' * 80}")
    print(f"STARTING DATABASE TRANSACTION FOR {len(articles)} ARTICLES")
    print(f"{'*' * 80}")
    logger.info(f"Preparing to insert batch of {len(articles)} articles")
    
    # Cache source IDs to minimize queries
    source_cache = {}
    
    # Start transaction
    for i, article in enumerate(articles):
        # Critical validation checks with detailed logging
        if 'id' not in article:
            print(f"SKIPPING ARTICLE {i}: Missing required field 'id'")
            logger.warning(f"SKIPPING: Article missing ID field: {article.get('url', 'unknown')}")
            skipped_count += 1
            continue
            
        if 'url' not in article:
            print(f"SKIPPING ARTICLE {article.get('id', '[Unknown ID]')}: Missing required field 'url'")
            logger.warning(f"SKIPPING: Article missing URL field: {article.get('id', '[Unknown ID]')}")
            skipped_count += 1
            continue
            
        if 'source_name' not in article:
            print(f"SKIPPING ARTICLE {article.get('id', '[Unknown ID]')}: Missing required field 'source_name'")
            logger.warning(f"SKIPPING: Article missing source_name field: {article.get('url', 'unknown')}")
            skipped_count += 1
            continue
            
        # Skip articles without text
        if not article.get('text'):
            print(f"SKIPPING ARTICLE {article.get('id', '[Unknown ID]')}: No text content")
            logger.info(f"Skipping article without text: {article.get('url', 'unknown')}")
            skipped_count += 1
            continue
            
        try:
            article_title = article.get('title', '[No Title]')
            article_url = article.get('url', '[No URL]')
            article_id = article.get('id', '[No ID]')
            
            # First, check if this article is worth processing (has sufficient text)
            text_length = len(article.get('text', '')) if article.get('text') else 0
            if text_length < 100:  # Skip very short articles
                print(f"SKIPPING ARTICLE {article_id}: Text too short ({text_length} chars)")
                logger.warning(f"SKIPPING: Short article text ({text_length} chars): {article_title[:30]}...")
                skipped_count += 1
                continue
            
            # Print detailed info for each article being processed
            print(f"PROCESSING: Article {i+1}/{len(articles)}: {article_title[:50]}...")
            print(f"  - URL: {article_url}")
            print(f"  - ID: {article_id}")
            print(f"  - Text length: {text_length} chars")
                
            # Check if article already exists - thorough check
            try:
                # Check by ID first (most efficient)
                existing_by_id = session.query(NewsArticle).filter_by(id=article_id).first()
                
                if existing_by_id:
                    print(f"SKIPPING: Article already exists in database by ID: {article_title[:50]}...")
                    logger.debug(f"Article already exists by ID: {article_id}")
                    skipped_count += 1
                    continue
                    
                # Double-check by URL as a fallback (in case of ID hash collision)
                existing_by_url = session.query(NewsArticle).filter_by(url=article_url).first()
                
                if existing_by_url:
                    print(f"SKIPPING: Article already exists in database by URL: {article_title[:50]}...")
                    logger.warning(f"Article found by URL but not ID - possible hash collision: {article_id} vs {existing_by_url.id}")
                    skipped_count += 1
                    continue
                    
                # Explicitly log that this is a new article
                print(f"NEW ARTICLE CONFIRMED: Not found in database by ID or URL")
                
            except Exception as lookup_error:
                print(f"ERROR during duplicate check: {str(lookup_error)}")
                logger.error(f"Database lookup error: {str(lookup_error)}")
                raise  # Re-raise to be caught at the article level
            
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
                    print(f"CREATED NEW SOURCE: {source_name}")
                    logger.info(f"Created new source: {source_name}")
                    
                source_id = source.id
                source_cache[source_name] = source_id
            
            # Debugging: print details about the article data
            print(f"  - Source: {source_name} (ID: {source_id})")
            print(f"  - Title: {article_title}")
            if 'publish_date' in article:
                print(f"  - Date: {article.get('publish_date')}")
            
            # Prepare and validate data before creating new article
            try:
                # Convert and validate all fields
                cleaned_text = article.get('text', '').strip() if article.get('text') else ''
                cleaned_html = article.get('html', '').strip() if article.get('html') else ''
                
                # Ensure publish_date is a datetime object
                if article.get('publish_date') and not isinstance(article.get('publish_date'), datetime.datetime):
                    try:
                        publish_date = datetime.datetime.fromisoformat(str(article.get('publish_date')))
                    except (ValueError, TypeError):
                        publish_date = datetime.datetime.now()
                        print(f"WARNING: Could not parse publish_date, using current time")
                else:
                    publish_date = article.get('publish_date', datetime.datetime.now())
                
                # Convert authors to JSON if needed
                if article.get('authors') and not isinstance(article.get('authors'), list):
                    authors = [str(article.get('authors'))]
                else:
                    authors = article.get('authors', [])
                
                # Convert extraction_info to dict if needed
                if article.get('extraction_info') and isinstance(article.get('extraction_info'), str):
                    try:
                        extraction_info = json.loads(article.get('extraction_info'))
                    except json.JSONDecodeError:
                        extraction_info = {'error': 'Could not parse extraction_info JSON', 'raw': article.get('extraction_info')}
                else:
                    extraction_info = article.get('extraction_info', {})
                
                # Create new article with validated data
                new_article = NewsArticle(
                    id=article_id,
                    source_id=source_id,
                    url=article_url,
                    title=article_title,
                    text=cleaned_text,
                    html=cleaned_html,
                    publish_date=publish_date,
                    authors=authors,
                    language=article.get('language', 'en'),
                    top_image=article.get('top_image', None),
                    scraped_at=article.get('scraped_at', datetime.datetime.now()),
                    extraction_info=extraction_info
                )
                
                print(f"Article object created successfully with cleaned data")
                
            except Exception as data_error:
                print(f"ERROR: Failed to prepare article data: {str(data_error)}")
                logger.error(f"Data preparation error: {str(data_error)}")
                raise  # Re-raise to be caught at the article level
            
            session.add(new_article)
            print(f"ADDED TO SESSION: {article_title[:50]}...")
            inserted_count += 1
            
            # Log every few articles
            if inserted_count % 5 == 0:
                logger.info(f"Added {inserted_count} articles so far (skipped {skipped_count})")
                
        except Exception as article_error:
            # Catch errors for individual articles but allow processing to continue
            logger.error(f"ERROR processing article {i} ({article.get('url', 'unknown')}): {str(article_error)}")
            logger.error(traceback.format_exc())
    
    # Commit the transaction
    try:
        if inserted_count > 0:
            print(f"\n{'=' * 80}")
            print(f"COMMITTING DATABASE TRANSACTION WITH {inserted_count} ARTICLES")
            print(f"{'=' * 80}")
            logger.info(f"Committing transaction with {inserted_count} articles")
            
            # Get IDs of articles we're trying to insert for verification
            article_ids_to_insert = [a.get('id') for a in articles if a.get('id')]
            print(f"Attempting to insert article IDs: {article_ids_to_insert[:5]}...")
            if len(article_ids_to_insert) > 5:
                print(f"...and {len(article_ids_to_insert) - 5} more")
            
            # Try to get the database state before commit
            try:
                # Use a new session to prevent affecting the transaction
                verification_session = db_manager.get_session()
                try:
                    count_before = verification_session.query(NewsArticle).count()
                    print(f"Current article count before commit: {count_before}")
                except Exception as query_error:
                    print(f"Error querying article count: {str(query_error)}")
                    count_before = -1
                finally:
                    verification_session.close()
            except Exception as count_error:
                print(f"Error creating verification session: {str(count_error)}")
                count_before = -1
            
            # Force flush before commit to catch errors early
            try:
                session.flush()
                print("Session flushed successfully - no errors detected")
            except Exception as flush_error:
                print(f"FLUSH ERROR: {str(flush_error)}")
                logger.error(f"Database flush error: {str(flush_error)}")
                session.rollback()
                raise
            
            # Actual commit with explicit error handling
            commit_start = time.time()
            try:
                session.commit()
                commit_time = time.time() - commit_start
                print(f"COMMIT SUCCESSFUL! (took {commit_time:.2f}s)")
                print(f"Successfully inserted {inserted_count} articles (skipped {skipped_count})")
                logger.info(f"Successfully inserted {inserted_count} articles (skipped {skipped_count})")
            except Exception as commit_error:
                print(f"COMMIT FAILED: {str(commit_error)}")
                logger.error(f"Database commit error: {str(commit_error)}")
                session.rollback()
                raise
            
            # Verify the articles were actually inserted by checking a few random ones
            print(f"\nVERIFYING INSERTION OF ARTICLES:")
            verification_count = min(inserted_count, 5)  # Check up to 5 random articles
            success_count = 0
            
            # Create a list of indexes to verify, starting with the first one
            article_indexes = [0]
            # Add more indexes if we have more articles
            if inserted_count > 1:
                import random
                additional_indexes = random.sample(range(1, len(articles)), min(4, inserted_count-1))
                article_indexes.extend(additional_indexes)
            
            for idx in article_indexes:
                article = articles[idx]
                if 'id' not in article:
                    print(f"  - Cannot verify article {idx+1} (missing ID)")
                    continue
                    
                check = session.query(NewsArticle).filter_by(id=article['id']).first()
                if check:
                    print(f"  ✓ VERIFIED: Article found: {article.get('title', '')[:30]}...")
                    success_count += 1
                else:
                    print(f"  ✗ FAILED: Could not find article {article['id']}")
            
            # Get final count after commit
            try:
                count_after = session.query(NewsArticle).count()
                print(f"\nFinal article count: {count_after} (Change: {count_after - count_before})")
                
                if count_after - count_before != inserted_count:
                    print(f"⚠️ WARNING: Expected +{inserted_count} articles, but count shows +{count_after - count_before}")
            except Exception as count_error:
                print(f"Error getting count after commit: {str(count_error)}")
                
            print(f"Verification summary: {success_count}/{verification_count} articles verified")
        else:
            print("No articles to commit - skipping transaction")
                
    except Exception as commit_error:
        # But still catch commit errors to prevent the whole batch from failing
        print(f"\n{'!' * 80}")
        print(f"CRITICAL DATABASE ERROR DURING COMMIT:")
        print(f"{str(commit_error)}")
        print(f"{'!' * 80}")
        logger.error(f"COMMIT ERROR: {str(commit_error)}")
        logger.error(traceback.format_exc())
        
        if session:
            print("Attempting to roll back transaction...")
            session.rollback()
            print("Session rolled back")
            logger.info("Session rolled back due to commit error")
        
        # Re-raise the error to be caught at a higher level
        raise
        
    finally:
        if session:
            session.close()
            logger.info("Database session closed")
        current_session = None  # Clear the global session reference
        
    return inserted_count

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
    
    # Get limit from environment variable
    limit_per_feed = int(os.getenv('SCRAPER_LIMIT_PER_FEED', 5))
    
    # Initialize database connection
    print("\n" + "=" * 80)
    print("INITIALIZING DATABASE CONNECTION")
    print("=" * 80)
    logger.info("Initializing database connection")
    db_manager = DatabaseManager()
    
    # Verify database connection with explicit test
    test_session = db_manager.get_session()
    try:
        # Simple query to verify connection is working - using SQLAlchemy text()
        from sqlalchemy import text
        result = test_session.execute(text("SELECT 1")).fetchone()
        if result and result[0] == 1:
            print("✓ Database connection verified successfully")
            logger.info("Database connection verified successfully")
            
            # Check for table existence and structure
            print("\nVERIFYING DATABASE TABLES:")
            
            # Check NewsSource table
            try:
                source_count = test_session.query(NewsSource).count()
                print(f"✓ NewsSource table accessible - {source_count} sources found")
            except Exception as source_error:
                print(f"✗ Error accessing NewsSource table: {str(source_error)}")
                raise
                
            # Check NewsArticle table
            try:
                article_count = test_session.query(NewsArticle).count()
                print(f"✓ NewsArticle table accessible - {article_count} articles found")
                
                # Check for the most recent article 
                most_recent = test_session.query(NewsArticle).order_by(NewsArticle.scraped_at.desc()).first()
                if most_recent:
                    print(f"  Most recent article: '{most_recent.title[:50]}...' from {most_recent.scraped_at}")
                
            except Exception as article_error:
                print(f"✗ Error accessing NewsArticle table: {str(article_error)}")
                raise
                
            print("\nDATABASE VERIFICATION SUCCESSFUL - Ready to scrape!\n")
        else:
            print("✗ Database connection test failed - unexpected result")
            logger.error("Database connection test failed - unexpected result")
            return 0
    except Exception as db_test_error:
        print(f"✗ DATABASE CONNECTION ERROR: {str(db_test_error)}")
        logger.error(f"DATABASE CONNECTION ERROR: {db_test_error}")
        raise  # Re-raise to stop execution
    finally:
        test_session.close()
    
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
    
    # Get baseline article count to verify progress
    count_session = db_manager.get_session()
    try:
        initial_count = count_session.query(NewsArticle).count()
        logger.info(f"CURRENT DATABASE STATS: {initial_count} articles before insert")
    except Exception as count_error:
        logger.error(f"Failed to get baseline article count: {count_error}")
        initial_count = -1  # Mark as unknown
    finally:
        count_session.close()
    
    # Insert articles in batches of 20
    total_inserted = 0
    batch_size = int(os.getenv('SCRAPER_BATCH_SIZE', 20))
    
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        logger.info(f"Inserting batch {i//batch_size + 1}/{(len(articles) + batch_size - 1)//batch_size} ({len(batch)} articles)")
        
        # Remove try/except to expose any batch insertion errors
        batch_inserted = insert_articles_batch(db_manager, batch)
        total_inserted += batch_inserted
        logger.info(f"Batch result: {batch_inserted} articles inserted successfully")
        
        # Brief pause between batches to avoid database contention
        if i + batch_size < len(articles):
            time.sleep(1)
    
    # Verify final article count to confirm inserts worked
    count_session = db_manager.get_session()
    try:
        final_count = count_session.query(NewsArticle).count()
        actual_change = final_count - initial_count if initial_count >= 0 else "unknown"
        logger.info(f"DATABASE VERIFICATION: Articles before: {initial_count}, Articles after: {final_count}, Change: {actual_change}")
        
        if initial_count >= 0 and final_count - initial_count != total_inserted:
            logger.warning(f"INCONSISTENCY DETECTED: Expected {total_inserted} new articles, but database shows {final_count - initial_count}")
    except Exception as count_error:
        logger.error(f"Failed to get final article count: {count_error}")
    finally:
        count_session.close()
    
    logger.info(f"Scraping completed. Total articles reported inserted: {total_inserted}")
    return total_inserted

if __name__ == "__main__":
    # Run scraper
    run_scraper_with_db()