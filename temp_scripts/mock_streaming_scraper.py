#!/usr/bin/env python
"""
End-to-end test of the streaming scraper implementation with mock data.
"""
import os
import sys
import logging
import time
import datetime
import hashlib
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import DatabaseManager
from database.models import NewsArticle
from scrapers.scrape_to_db import insert_articles_batch

def generate_test_article_batch(batch_id, articles_per_batch=2):
    """Generate a batch of test articles."""
    articles = []
    timestamp = datetime.datetime.now()
    
    for i in range(articles_per_batch):
        article_num = (batch_id * articles_per_batch) + i
        url = f"https://test.example.com/test-article-{article_num}-{timestamp.isoformat()}"
        article_id = hashlib.md5(url.encode()).hexdigest()
        
        article = {
            'id': article_id,
            'url': url,
            'title': f"Test Streaming Article {article_num} at {timestamp.isoformat()}",
            'text': f"This is a test article {article_num} created at {timestamp.isoformat()}\n" * 10,
            'html': f"<html><body>Test article {article_num} at {timestamp.isoformat()}</body></html>",
            'source_name': 'Test Source',
            'publish_date': timestamp,
            'authors': ['Test Author'],
            'language': 'en',
            'scraped_at': timestamp,
            'extraction_info': {
                'method': 'test',
                'success': True,
                'text_length': 500
            }
        }
        articles.append(article)
    
    return articles

def mock_streaming_generator(num_batches=3, articles_per_batch=2):
    """Mock generator that yields article batches like the streaming scraper."""
    for batch_id in range(num_batches):
        # Simulate network delay
        time.sleep(1)
        
        # Generate a batch of articles
        batch = generate_test_article_batch(batch_id, articles_per_batch)
        
        # Yield the batch
        yield batch

def run_mock_scraper():
    """Test the full streaming scraper pipeline with mock data."""
    print("\n" + "=" * 80)
    print("STREAMING SCRAPER END-TO-END TEST")
    print("=" * 80)
    
    # Initialize database
    db_manager = DatabaseManager()
    
    # Get initial article count
    count_session = db_manager.get_session()
    try:
        initial_count = count_session.query(NewsArticle).count()
        print(f"Initial article count: {initial_count}")
    finally:
        count_session.close()
    
    # Use the generator version that yields batches as they're processed
    total_inserted = 0
    batch_counter = 0
    
    try:
        for article_batch in mock_streaming_generator():
            batch_counter += 1
            if not article_batch:
                logger.warning(f"Received empty batch {batch_counter}, skipping")
                continue
                
            print(f"\n{'-' * 80}")
            print(f"MOCK BATCH {batch_counter}: {len(article_batch)} ARTICLES")
            print(f"{'-' * 80}")
            
            for i, article in enumerate(article_batch):
                print(f"{i+1}. {article['title']} (ID: {article['id']})")
            
            # Insert this batch immediately
            print(f"\nInserting batch {batch_counter} to database...")
            
            try:
                batch_inserted = insert_articles_batch(db_manager, article_batch)
                total_inserted += batch_inserted
                
                print(f"\nBatch {batch_counter} result: {batch_inserted}/{len(article_batch)} articles inserted")
                print(f"Running total: {total_inserted} articles inserted so far")
            except Exception as batch_error:
                print(f"ERROR IN BATCH {batch_counter}: {str(batch_error)}")
                logger.error(f"Batch {batch_counter} error: {str(batch_error)}")
                logger.error(traceback.format_exc())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user - articles processed so far have been saved")
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        logger.error(traceback.format_exc())
    
    # Verify final article count to confirm inserts worked
    count_session = db_manager.get_session()
    try:
        final_count = count_session.query(NewsArticle).count()
        actual_change = final_count - initial_count
        print(f"\nDATABASE VERIFICATION: Articles before: {initial_count}, Articles after: {final_count}, Change: {actual_change}")
        
        if actual_change != total_inserted:
            print(f"INCONSISTENCY DETECTED: Expected {total_inserted} new articles, but database shows {actual_change}")
        
        # Report some of the newest articles
        newest_articles = count_session.query(NewsArticle).order_by(NewsArticle.scraped_at.desc()).limit(6).all()
        print(f"\nMOST RECENT ARTICLES IN DATABASE:")
        for i, article in enumerate(newest_articles):
            print(f"{i+1}. {article.title} (ID: {article.id}, scraped at: {article.scraped_at})")
    except Exception as count_error:
        logger.error(f"Failed to get final article count: {count_error}")
    finally:
        count_session.close()
    
    print("\n" + "=" * 80)
    if total_inserted > 0:
        print(f"TEST SUCCESSFUL: {total_inserted} articles inserted across {batch_counter} batches")
    else:
        print("TEST FAILED: No articles were inserted")
    print("=" * 80)

if __name__ == "__main__":
    run_mock_scraper()