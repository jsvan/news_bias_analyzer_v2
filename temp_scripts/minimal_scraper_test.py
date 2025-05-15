#!/usr/bin/env python
"""
Minimal test of the scraper with database insertion.
"""
import os
import sys
import logging
import time
import datetime
import hashlib
import json

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
from scrapers.scrape_to_db import insert_articles_batch

def generate_test_articles(count=3):
    """Generate a batch of test articles for database insertion."""
    articles = []
    for i in range(count):
        timestamp = datetime.datetime.now().isoformat()
        url = f"https://test.example.com/test-article-{i}-{timestamp}"
        article_id = hashlib.md5(url.encode()).hexdigest()
        
        article = {
            'id': article_id,
            'url': url,
            'title': f"Test Article {i} at {timestamp}",
            'text': f"This is test article {i} created at {timestamp}\n" * 10,
            'html': f"<html><body>Test article {i} at {timestamp}</body></html>",
            'source_name': 'Test Source',
            'publish_date': datetime.datetime.now(),
            'authors': ['Test Author'],
            'language': 'en',
            'scraped_at': datetime.datetime.now(),
            'extraction_info': {
                'method': 'test',
                'success': True,
                'text_length': 500
            }
        }
        articles.append(article)
    
    return articles

def main():
    """Run a minimal test of scraper database insertion."""
    print("\n" + "=" * 80)
    print("MINIMAL DATABASE INSERTION TEST")
    print("=" * 80)
    
    # Initialize database
    db_manager = DatabaseManager()
    
    # Get current count
    session = db_manager.get_session()
    try:
        initial_count = session.query(NewsArticle).count()
        print(f"Initial article count: {initial_count}")
    finally:
        session.close()
    
    # Generate test articles
    articles = generate_test_articles(3)
    
    print(f"\nGenerated {len(articles)} test articles:")
    for i, article in enumerate(articles):
        print(f"{i+1}. {article['title']} (ID: {article['id']})")
    
    # Insert articles
    print("\nInserting articles to database...")
    inserted = insert_articles_batch(db_manager, articles)
    print(f"Insertion result: {inserted} articles inserted")
    
    # Verify insertion
    session = db_manager.get_session()
    try:
        final_count = session.query(NewsArticle).count()
        print(f"Final article count: {final_count}")
        print(f"Change: {final_count - initial_count}")
        
        # Verify inserted articles
        print("\nVerifying inserted articles:")
        for article in articles:
            result = session.query(NewsArticle).filter_by(id=article['id']).first()
            if result:
                print(f"✓ Found article: {article['title']}")
            else:
                print(f"✗ Missing article: {article['title']}")
    finally:
        session.close()
    
    print("\n" + "=" * 80)
    if final_count > initial_count:
        print("TEST SUCCESSFUL: Articles were inserted correctly")
    else:
        print("TEST FAILED: No articles were inserted")
    print("=" * 80)

if __name__ == "__main__":
    main()