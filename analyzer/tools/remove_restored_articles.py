#!/usr/bin/env python3
"""
Remove all 'restored articles' from the database.

This script specifically targets articles with URLs like 'restored_article_*'
that were erroneously created during OpenAI batch recovery.

Usage:
  ./run.sh custom analyzer/tools/remove_restored_articles.py [--dry-run]
"""

import os
import sys
import logging
import argparse
import datetime
from sqlalchemy import delete, func

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("remove_restored_articles")

def get_database_stats(session):
    """Get database statistics for reporting."""
    stats = {}
    
    # Count articles
    total_articles = session.query(NewsArticle).count()
    restored_articles = session.query(NewsArticle).filter(
        NewsArticle.url.like('restored_article_%')
    ).count()
    
    # Count source breakdown for restored articles
    source_breakdown = session.query(
        NewsArticle.source_id,
        func.count(NewsArticle.id)
    ).filter(
        NewsArticle.url.like('restored_article_%')
    ).group_by(
        NewsArticle.source_id
    ).all()
    
    # Count entities
    total_entities = session.query(Entity).count()
    
    # Count entity mentions from restored articles
    restored_article_ids = session.query(NewsArticle.id).filter(
        NewsArticle.url.like('restored_article_%')
    ).all()
    
    restored_article_ids = [id[0] for id in restored_article_ids]
    
    mentions_from_restored = 0
    if restored_article_ids:
        mentions_from_restored = session.query(EntityMention).filter(
            EntityMention.article_id.in_(restored_article_ids)
        ).count()
    
    stats['total_articles'] = total_articles
    stats['restored_articles'] = restored_articles
    stats['total_entities'] = total_entities
    stats['mentions_from_restored'] = mentions_from_restored
    stats['source_breakdown'] = source_breakdown
    
    return stats

def remove_restored_articles(dry_run=True):
    """
    Remove all restored articles from the database.
    
    Args:
        dry_run: If True, don't actually delete anything, just report what would be deleted
    """
    # Initialize database connection
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Get current stats
        before_stats = get_database_stats(session)
        
        logger.info("\n===== Remove Restored Articles Tool =====")
        logger.info(f"Dry run: {'Yes' if dry_run else 'No'}")
        
        logger.info("\n--- Current Database Stats ---")
        logger.info(f"Total articles: {before_stats['total_articles']}")
        logger.info(f"Restored articles to remove: {before_stats['restored_articles']}")
        logger.info(f"Total entities: {before_stats['total_entities']}")
        logger.info(f"Entity mentions from restored articles: {before_stats['mentions_from_restored']}")
        
        # Show source breakdown
        if before_stats['source_breakdown']:
            logger.info("\n--- Source Breakdown for Restored Articles ---")
            for source_id, count in before_stats['source_breakdown']:
                logger.info(f"Source ID {source_id}: {count} articles")
        
        # Get sample of restored articles
        sample_articles = session.query(NewsArticle.id, NewsArticle.title, NewsArticle.url, NewsArticle.source_id).filter(
            NewsArticle.url.like('restored_article_%')
        ).limit(5).all()
        
        if sample_articles:
            logger.info("\n--- Sample of Restored Articles ---")
            for id, title, url, source_id in sample_articles:
                logger.info(f"ID: {id}, Title: {title[:50]}..., Source ID: {source_id}")
        
        # If there are no restored articles, return early
        if before_stats['restored_articles'] == 0:
            logger.info("\nNo restored articles found in the database.")
            return
        
        # Only proceed if not a dry run
        if not dry_run:
            # First delete all entity mentions for restored articles
            article_ids = session.query(NewsArticle.id).filter(
                NewsArticle.url.like('restored_article_%')
            ).all()
            
            article_ids = [id[0] for id in article_ids]
            
            if article_ids:
                # Delete mentions
                mentions_query = delete(EntityMention).where(
                    EntityMention.article_id.in_(article_ids)
                )
                
                result = session.execute(mentions_query)
                deleted_mentions = result.rowcount
                logger.info(f"\nDeleted {deleted_mentions} entity mentions from restored articles")
                
                # Delete articles
                articles_query = delete(NewsArticle).where(
                    NewsArticle.url.like('restored_article_%')
                )
                
                result = session.execute(articles_query)
                deleted_articles = result.rowcount
                logger.info(f"Deleted {deleted_articles} restored articles")
                
                # Commit the changes
                session.commit()
                logger.info("\nChanges committed to database")
                
                # Get updated stats
                after_stats = get_database_stats(session)
                
                logger.info("\n--- Updated Database Stats ---")
                logger.info(f"Total articles remaining: {after_stats['total_articles']}")
                logger.info(f"Restored articles remaining: {after_stats['restored_articles']}")
                logger.info(f"Entity mentions from restored articles remaining: {after_stats['mentions_from_restored']}")
            else:
                logger.info("\nNo article IDs found for deletion")
        else:
            logger.info("\nDRY RUN - No changes made to database")
            logger.info(f"Would delete {before_stats['mentions_from_restored']} entity mentions")
            logger.info(f"Would delete {before_stats['restored_articles']} restored articles")
            logger.info("Run without --dry-run to apply changes")
        
    except Exception as e:
        logger.error(f"Error removing restored articles: {e}")
        session.rollback()
    finally:
        session.close()

def main():
    parser = argparse.ArgumentParser(description='Remove all "restored articles" from the database')
    parser.add_argument('--dry-run', action='store_true',
                        help="Don't make any changes, just show what would be done")
    
    args = parser.parse_args()
    remove_restored_articles(args.dry_run)

if __name__ == "__main__":
    main()