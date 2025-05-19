#!/usr/bin/env python3
"""
Script to reset articles that are stuck in 'in_progress' status.
This helps recover from failed or stuck batch processing.

Usage: ./run.sh custom temp_scripts/reset_stuck_articles.py [--hours HOURS] [--dry-run]
"""

import os
import sys
import argparse
import datetime
from sqlalchemy import func

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from database.db import DatabaseManager
from database.models import NewsArticle

def reset_stuck_articles(hours=24, dry_run=False):
    """
    Reset articles stuck in 'in_progress' status for longer than specified hours.
    
    Args:
        hours: Number of hours to consider an article stuck
        dry_run: If True, only report articles but don't reset them
    """
    print(f"\n===== RESET STUCK ARTICLES {'(DRY RUN)' if dry_run else ''} =====")
    
    # Calculate the cutoff time
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
    print(f"Cutoff time: {cutoff_time} (articles in 'in_progress' before this time will be reset)")
    
    # Initialize database connection
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Find stuck articles
        stuck_articles = session.query(NewsArticle).filter(
            NewsArticle.analysis_status == "in_progress",
            NewsArticle.last_analysis_attempt < cutoff_time
        ).all()
        
        if not stuck_articles:
            print(f"No articles found stuck in 'in_progress' status for more than {hours} hours.")
            return
        
        print(f"Found {len(stuck_articles)} articles stuck in 'in_progress' status for more than {hours} hours.")
        
        # Group by batch_id
        batch_counts = {}
        for article in stuck_articles:
            batch_id = article.batch_id or "None"
            if batch_id not in batch_counts:
                batch_counts[batch_id] = 0
            batch_counts[batch_id] += 1
        
        print("\nStuck articles by batch:")
        for batch_id, count in batch_counts.items():
            print(f"  - Batch {batch_id}: {count} articles")
        
        # Reset articles if not in dry run mode
        if not dry_run:
            for article in stuck_articles:
                article.analysis_status = "unanalyzed"
                article.batch_id = None
                
            session.commit()
            print(f"\nSuccessfully reset {len(stuck_articles)} articles to 'unanalyzed' status.")
        else:
            print("\nDRY RUN: No articles were reset. Run without --dry-run to perform the reset.")
        
    finally:
        session.close()

def main():
    parser = argparse.ArgumentParser(description="Reset articles stuck in 'in_progress' status")
    parser.add_argument("--hours", type=int, default=24, 
                        help="Consider articles stuck if in 'in_progress' for more than this many hours (default: 24)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't actually reset articles, just report them")
    
    args = parser.parse_args()
    reset_stuck_articles(hours=args.hours, dry_run=args.dry_run)

if __name__ == "__main__":
    main()