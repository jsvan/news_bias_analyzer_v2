#!/usr/bin/env python3
"""
Reset database - clears entity data and resets article processing status.

This script:
1. Removes all entity mentions
2. Removes all entities
3. Resets article status to 'unanalyzed'
4. Clears processed_at and batch_id fields

Use with caution as it will delete analysis data. Run with --dry-run first to see what will be deleted.

Usage: ./run.sh custom analyzer/tools/reset_database.py [--dry-run] [--keep-recent-hours N] [--keep-entities]
"""

import os
import sys
import logging
import argparse
import datetime
from sqlalchemy import update, delete

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("reset_database")

def get_database_stats(session):
    """Get database statistics for reporting."""
    stats = {}
    
    # Count articles
    total_articles = session.query(NewsArticle).count()
    completed_articles = session.query(NewsArticle).filter(
        NewsArticle.analysis_status == "completed"
    ).count()
    in_progress_articles = session.query(NewsArticle).filter(
        NewsArticle.analysis_status == "in_progress"
    ).count()
    
    # Count entities
    total_entities = session.query(Entity).count()
    total_mentions = session.query(EntityMention).count()
    
    stats['total_articles'] = total_articles
    stats['completed_articles'] = completed_articles
    stats['in_progress_articles'] = in_progress_articles
    stats['total_entities'] = total_entities
    stats['total_mentions'] = total_mentions
    
    return stats

def reset_database(dry_run=True, keep_recent_hours=None, keep_entities=False):
    """Reset the database by clearing entity data and resetting article status."""
    # Initialize database connection
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Get current stats
        before_stats = get_database_stats(session)
        
        logger.info("\n===== Database Reset Tool =====")
        logger.info(f"Dry run: {'Yes' if dry_run else 'No'}")
        logger.info(f"Keep recent ({keep_recent_hours} hours): {'Yes' if keep_recent_hours else 'No'}")
        logger.info(f"Keep entities: {'Yes' if keep_entities else 'No'}")
        
        logger.info("\n--- Current Database Stats ---")
        logger.info(f"Total articles: {before_stats['total_articles']}")
        logger.info(f"Completed articles: {before_stats['completed_articles']}")
        logger.info(f"In-progress articles: {before_stats['in_progress_articles']}")
        logger.info(f"Total entities: {before_stats['total_entities']}")
        logger.info(f"Total entity mentions: {before_stats['total_mentions']}")
        
        # Calculate cutoff time if keeping recent articles
        cutoff_time = None
        if keep_recent_hours:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=keep_recent_hours)
            logger.info(f"\nKeeping articles analyzed after: {cutoff_time}")
        
        # Delete entity mentions
        if keep_recent_hours:
            # If we're keeping recent hours, we need to identify articles to reset
            if not keep_entities:
                articles_to_reset = session.query(NewsArticle.id).filter(
                    (NewsArticle.processed_at < cutoff_time) | 
                    (NewsArticle.processed_at == None)
                ).all()
                article_ids = [a.id for a in articles_to_reset]
                
                if article_ids:
                    # Only delete mentions for older articles
                    mention_query = delete(EntityMention).where(
                        EntityMention.article_id.in_(article_ids)
                    )
                    if not dry_run:
                        result = session.execute(mention_query)
                        deleted_mentions = result.rowcount
                        logger.info(f"Deleted {deleted_mentions} entity mentions for older articles")
                    else:
                        mention_count = session.query(EntityMention).filter(
                            EntityMention.article_id.in_(article_ids)
                        ).count()
                        logger.info(f"Would delete {mention_count} entity mentions for older articles")
                else:
                    logger.info("No older articles found to reset")
        elif not keep_entities:
            # If we're not keeping any, delete all entity mentions
            if not dry_run:
                result = session.execute(delete(EntityMention))
                deleted_mentions = result.rowcount
                logger.info(f"Deleted all {deleted_mentions} entity mentions")
            else:
                logger.info(f"Would delete all {before_stats['total_mentions']} entity mentions")
        
        # Delete entities
        if not keep_entities and not keep_recent_hours:
            if not dry_run:
                result = session.execute(delete(Entity))
                deleted_entities = result.rowcount
                logger.info(f"Deleted all {deleted_entities} entities")
            else:
                logger.info(f"Would delete all {before_stats['total_entities']} entities")
        
        # Reset article status
        articles_updated = 0
        if keep_recent_hours:
            # Reset only older articles
            article_query = update(NewsArticle).where(
                (NewsArticle.processed_at < cutoff_time) | 
                (NewsArticle.processed_at == None)
            ).values(
                analysis_status="unanalyzed",
                processed_at=None,
                batch_id=None
            )
            
            if not dry_run:
                result = session.execute(article_query)
                articles_updated = result.rowcount
                session.commit()
                logger.info(f"Reset {articles_updated} older articles to unanalyzed")
            else:
                older_count = session.query(NewsArticle).filter(
                    (NewsArticle.processed_at < cutoff_time) | 
                    (NewsArticle.processed_at == None)
                ).count()
                logger.info(f"Would reset {older_count} older articles to unanalyzed")
        else:
            # Reset all articles
            article_query = update(NewsArticle).values(
                analysis_status="unanalyzed",
                processed_at=None,
                batch_id=None
            )
            
            if not dry_run:
                result = session.execute(article_query)
                articles_updated = result.rowcount
                session.commit()
                logger.info(f"Reset all {articles_updated} articles to unanalyzed")
            else:
                logger.info(f"Would reset all {before_stats['total_articles']} articles to unanalyzed")
        
        # Commit changes
        if not dry_run:
            session.commit()
            logger.info("\nChanges committed to database")
            
            # Get updated stats
            after_stats = get_database_stats(session)
            
            logger.info("\n--- Updated Database Stats ---")
            logger.info(f"Total articles: {after_stats['total_articles']}")
            logger.info(f"Completed articles: {after_stats['completed_articles']}")
            logger.info(f"In-progress articles: {after_stats['in_progress_articles']}")
            logger.info(f"Total entities: {after_stats['total_entities']}")
            logger.info(f"Total entity mentions: {after_stats['total_mentions']}")
        else:
            logger.info("\nDRY RUN - No changes made to database")
            logger.info("Run without --dry-run to apply changes")
        
    finally:
        session.close()

def main():
    parser = argparse.ArgumentParser(description='Reset database by clearing entity data and resetting article status')
    parser.add_argument('--dry-run', action='store_true',
                        help="Don't make any changes, just show what would be done")
    parser.add_argument('--keep-recent-hours', type=int,
                        help='Keep analysis data from the last N hours')
    parser.add_argument('--keep-entities', action='store_true',
                        help="Don't delete entities, only reset article status")
    
    args = parser.parse_args()
    reset_database(args.dry_run, args.keep_recent_hours, args.keep_entities)

if __name__ == "__main__":
    main()