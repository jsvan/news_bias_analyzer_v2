#!/usr/bin/env python3
"""
Script to reset the database by deleting all articles and entities.
This is useful when you want to start fresh with article import.
"""

import os
import sys
import logging
import argparse
from sqlalchemy import func
from datetime import datetime

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.db import DatabaseManager
from database.models import NewsArticle, NewsSource, Entity, EntityMention

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reset_database(keep_sources=True, dry_run=False):
    """
    Reset the database by deleting articles and entities.
    
    Args:
        keep_sources: If True, retain news sources but clear articles and entities
        dry_run: If True, don't actually make changes, just report what would be done
    """
    # Initialize database connection
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Get counts before deletion
        article_count = session.query(func.count(NewsArticle.id)).scalar() or 0
        entity_count = session.query(func.count(Entity.id)).scalar() or 0
        entity_mention_count = session.query(func.count(EntityMention.id)).scalar() or 0
        source_count = session.query(func.count(NewsSource.id)).scalar() or 0
        
        logger.info("===== Current Database State =====")
        logger.info(f"Articles: {article_count}")
        logger.info(f"Entities: {entity_count}")
        logger.info(f"Entity Mentions: {entity_mention_count}")
        logger.info(f"News Sources: {source_count}")
        
        if dry_run:
            logger.info("\n===== DRY RUN - No changes will be made =====")
            logger.info(f"Would delete {entity_mention_count} entity mentions")
            logger.info(f"Would delete {entity_count} entities")
            logger.info(f"Would delete {article_count} articles")
            if not keep_sources:
                logger.info(f"Would delete {source_count} news sources")
            return
        
        # Delete entity mentions first (foreign key constraint)
        logger.info("\n===== Deleting Data =====")
        logger.info("Deleting entity mentions...")
        session.query(EntityMention).delete()
        logger.info(f"Deleted {entity_mention_count} entity mentions")
        
        # Delete entities
        logger.info("Deleting entities...")
        session.query(Entity).delete()
        logger.info(f"Deleted {entity_count} entities")
        
        # Delete articles
        logger.info("Deleting articles...")
        session.query(NewsArticle).delete()
        logger.info(f"Deleted {article_count} articles")
        
        # Optionally delete sources
        if not keep_sources:
            logger.info("Deleting news sources...")
            session.query(NewsSource).delete()
            logger.info(f"Deleted {source_count} news sources")
        
        # Commit changes
        session.commit()
        logger.info("\n===== Database Reset Complete =====")
        logger.info(f"Deleted {entity_mention_count} entity mentions")
        logger.info(f"Deleted {entity_count} entities")
        logger.info(f"Deleted {article_count} articles")
        if not keep_sources:
            logger.info(f"Deleted {source_count} news sources")
        else:
            logger.info(f"Kept {source_count} news sources")
        
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        session.rollback()
    finally:
        session.close()

def main():
    parser = argparse.ArgumentParser(description='Reset the database')
    parser.add_argument('--delete-sources', action='store_true',
                        help='Also delete news sources (default: keep sources)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be deleted without making changes')
    
    args = parser.parse_args()
    
    # Confirm before proceeding
    if not args.dry_run:
        print("\n⚠️  WARNING: You are about to reset the database. This action cannot be undone! ⚠️")
        print("All articles and entities will be permanently deleted.")
        if args.delete_sources:
            print("All news sources will also be deleted.")
        
        confirm = input("\nType 'YES' to confirm: ")
        if confirm != "YES":
            print("Operation cancelled.")
            return
    
    # Reset the database
    reset_database(keep_sources=not args.delete_sources, dry_run=args.dry_run)

if __name__ == "__main__":
    main()