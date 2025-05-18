#!/usr/bin/env python3
"""
Script to check the status of articles in the database.
This script allows you to check for missing articles, unprocessed articles,
and articles without entities.
"""

import os
import sys
import logging
import argparse
import json
from pathlib import Path

# Add the parent directory to the path to import database modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_article_id(custom_id):
    """Extract article_id from custom_id in batch request."""
    if custom_id.startswith('article_'):
        return custom_id[8:]  # Remove 'article_' prefix
    return custom_id

def get_batch_article_ids(batch_dir):
    """Get all article IDs from batch files."""
    batch_dir = Path(batch_dir)
    
    article_ids = set()
    
    # Get all input files
    input_files = list(batch_dir.glob('*_input.jsonl'))
    
    for input_file in input_files:
        with open(input_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    custom_id = data.get('custom_id')
                    if custom_id:
                        article_id = parse_article_id(custom_id)
                        article_ids.add(article_id)
                except Exception as e:
                    logger.error(f"Error parsing {input_file}: {e}")
    
    return article_ids

def check_articles_in_database(db_manager, article_ids):
    """Check which articles exist in the database."""
    session = db_manager.get_session()
    try:
        # Find existing articles
        existing_articles = {}
        for article in session.query(NewsArticle).filter(NewsArticle.id.in_(article_ids)).all():
            existing_articles[article.id] = {
                'id': article.id,
                'title': article.title,
                'processed_at': article.processed_at,
                'has_entities': False
            }
        
        # Check which articles have entities
        article_entity_counts = {}
        for em in session.query(EntityMention).filter(EntityMention.article_id.in_(article_ids)).all():
            if em.article_id in existing_articles:
                existing_articles[em.article_id]['has_entities'] = True
                article_entity_counts[em.article_id] = article_entity_counts.get(em.article_id, 0) + 1
        
        # Update entity counts
        for article_id, count in article_entity_counts.items():
            if article_id in existing_articles:
                existing_articles[article_id]['entity_count'] = count
        
        # Identify missing, unprocessed, and articles without entities
        missing_ids = set(article_ids) - set(existing_articles.keys())
        unprocessed_ids = {aid for aid, info in existing_articles.items() if not info.get('processed_at')}
        no_entities_ids = {aid for aid, info in existing_articles.items() 
                          if info.get('processed_at') and not info.get('has_entities')}
        
        return {
            'total_batch_articles': len(article_ids),
            'existing_articles': len(existing_articles),
            'missing_articles': list(missing_ids),
            'unprocessed_articles': list(unprocessed_ids),
            'no_entities_articles': list(no_entities_ids),
            'article_details': existing_articles
        }
    
    finally:
        session.close()

def main():
    parser = argparse.ArgumentParser(description='Check article status in database')
    parser.add_argument('--batch-dir', type=str, default='openai_batches',
                        help='Directory containing batch files (default: openai_batches)')
    parser.add_argument('--output', type=str,
                        help='Output file to save article status (JSON format)')
    parser.add_argument('--missing-only', action='store_true',
                        help='Only show missing articles')
    
    args = parser.parse_args()
    
    # Create database manager
    db_manager = DatabaseManager()
    
    # Get article IDs from batch files
    article_ids = get_batch_article_ids(args.batch_dir)
    logger.info(f"Found {len(article_ids)} article IDs in batch files")
    
    # Check articles in database
    result = check_articles_in_database(db_manager, article_ids)
    
    # Display results
    logger.info(f"Total batch articles: {result['total_batch_articles']}")
    logger.info(f"Existing articles in DB: {result['existing_articles']}")
    logger.info(f"Missing articles: {len(result['missing_articles'])}")
    logger.info(f"Unprocessed articles: {len(result['unprocessed_articles'])}")
    logger.info(f"Articles without entities: {len(result['no_entities_articles'])}")
    
    if args.missing_only:
        logger.info("\nMissing article IDs:")
        for article_id in sorted(result['missing_articles']):
            print(article_id)
    
    # Save results to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"Results saved to {args.output}")

if __name__ == "__main__":
    main()