#!/usr/bin/env python
"""
A debugging script to test database insertion.
"""
import os
import sys
import logging
import datetime
import time
import hashlib
import json
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import DatabaseManager
from database.models import NewsArticle, NewsSource

def generate_article_id(url):
    """Generate MD5 hash from URL to use as article ID."""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def main():
    """Run a test insert and verify the result."""
    print("\n" + "=" * 80)
    print("TESTING DATABASE INSERTION")
    print("=" * 80)
    
    # Initialize database connection
    db_manager = DatabaseManager()
    
    # Verify database connection with explicit test
    test_session = db_manager.get_session()
    try:
        # Simple query to verify connection is working - using SQLAlchemy text()
        result = test_session.execute(text("SELECT 1")).fetchone()
        if result and result[0] == 1:
            print("✓ Database connection verified successfully")
        else:
            print("✗ Database connection test failed - unexpected result")
            return False
    except Exception as db_test_error:
        print(f"✗ DATABASE CONNECTION ERROR: {str(db_test_error)}")
        logger.error(f"DATABASE CONNECTION ERROR: {db_test_error}")
        return False
    finally:
        test_session.close()
    
    # Get baseline article count
    count_session = db_manager.get_session()
    try:
        initial_count = count_session.query(NewsArticle).count()
        print(f"Initial article count: {initial_count}")
    except Exception as count_error:
        print(f"Error getting initial count: {str(count_error)}")
        return False
    finally:
        count_session.close()
    
    # Create a test article
    test_timestamp = datetime.datetime.now()
    test_article = {
        'id': generate_article_id(f"https://test.example.com/test-article-{test_timestamp.isoformat()}"),
        'url': f"https://test.example.com/test-article-{test_timestamp.isoformat()}",
        'title': f"Test Article at {test_timestamp.isoformat()}",
        'text': f"This is a test article generated at {test_timestamp.isoformat()}\n" * 20,
        'html': f"<html><body>This is a test article generated at {test_timestamp.isoformat()}</body></html>",
        'publish_date': test_timestamp,
        'source_name': 'Test Source',
        'authors': ['Test Author 1', 'Test Author 2'],
        'language': 'en',
        'scraped_at': test_timestamp,
        'extraction_info': {
            'method': 'test',
            'timestamp': test_timestamp.isoformat()
        }
    }
    
    print("\n" + "-" * 80)
    print(f"TESTING ARTICLE INSERTION")
    print(f"Article ID: {test_article['id']}")
    print(f"Article Title: {test_article['title']}")
    print(f"Article URL: {test_article['url']}")
    print("-" * 80)
    
    # Start a session for insertion
    session = db_manager.get_session()
    try:
        # Get or create source
        source_name = test_article['source_name']
        source = session.query(NewsSource).filter_by(name=source_name).first()
        if not source:
            # Create new source
            source = NewsSource(
                name=source_name,
                base_url='https://test.example.com',
                country='Test Country',
                language='en'
            )
            session.add(source)
            session.flush()
            print(f"Created new source: {source_name}")
            
        source_id = source.id
        print(f"Using source ID: {source_id}")
        
        # Check if article already exists
        existing_by_id = session.query(NewsArticle).filter_by(id=test_article['id']).first()
        if existing_by_id:
            print(f"Article already exists in database by ID: {test_article['id']}")
            session.close()
            return False
            
        # Create new article
        new_article = NewsArticle(
            id=test_article['id'],
            source_id=source_id,
            url=test_article['url'],
            title=test_article['title'],
            text=test_article['text'],
            html=test_article['html'],
            publish_date=test_article['publish_date'],
            authors=test_article['authors'],
            language=test_article['language'],
            top_image=None,
            scraped_at=test_article['scraped_at'],
            extraction_info=test_article['extraction_info']
        )
        
        # Add to session
        session.add(new_article)
        print(f"Article added to session")
        
        # Flush to catch errors early
        try:
            session.flush()
            print("Session flushed successfully - no errors detected")
        except Exception as flush_error:
            print(f"FLUSH ERROR: {str(flush_error)}")
            session.rollback()
            raise
        
        # Commit
        commit_start = time.time()
        session.commit()
        commit_time = time.time() - commit_start
        print(f"COMMIT SUCCESSFUL! (took {commit_time:.2f}s)")
        
        # Verify article was inserted
        check_session = db_manager.get_session()
        try:
            check = check_session.query(NewsArticle).filter_by(id=test_article['id']).first()
            if check:
                print(f"VERIFICATION SUCCESS: Found article {test_article['id']} in database")
            else:
                print(f"VERIFICATION FAILED: Could not find article {test_article['id']} in database")
                return False
        finally:
            check_session.close()
        
        # Get final count
        final_count_session = db_manager.get_session()
        try:
            final_count = final_count_session.query(NewsArticle).count()
            print(f"Final article count: {final_count} (Change: {final_count - initial_count})")
            if final_count > initial_count:
                print("TEST SUCCESSFUL: Article count increased")
                return True
            else:
                print("TEST FAILED: Article count did not increase")
                return False
        except Exception as count_error:
            print(f"Error getting final count: {str(count_error)}")
            return False
        finally:
            final_count_session.close()
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        logger.error(f"Error inserting test article: {e}")
        session.rollback()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    result = main()
    if result:
        print("\n✅ DATABASE INSERTION TEST PASSED")
    else:
        print("\n❌ DATABASE INSERTION TEST FAILED")