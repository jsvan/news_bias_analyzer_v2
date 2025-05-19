#!/usr/bin/env python3
"""
Script to analyze the database status directly.
This script bypasses the status reporting in db_stats.py and directly checks the database.

Usage: ./run.sh custom analyzer/tools/analyze_db_status.py
"""

import os
import sys
import datetime
from sqlalchemy import func, text

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from database.db import DatabaseManager
from database.models import NewsArticle, NewsSource, Entity, EntityMention

def analyze_db_status():
    """Analyze the database status directly."""
    print("\n===== DATABASE STATUS ANALYSIS =====")
    
    # Initialize database connection
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Get article counts
        total_articles = session.query(func.count(NewsArticle.id)).scalar() or 0
        print(f"Total articles: {total_articles}")
        
        # Articles by analysis_status
        print("\nStatus Breakdown:")
        status_counts = session.query(
            NewsArticle.analysis_status,
            func.count(NewsArticle.id)
        ).group_by(
            NewsArticle.analysis_status
        ).all()
        
        for status, count in status_counts:
            print(f"  - {status or 'null'}: {count} articles")
        
        # Check for batch IDs
        batch_count = session.query(func.count(NewsArticle.id)).filter(
            NewsArticle.batch_id.isnot(None)
        ).scalar() or 0
        print(f"\nArticles with batch_id: {batch_count}")
        
        # Recent batch IDs (limit to 5)
        print("\nMost recent batch IDs:")
        recent_batches = session.query(
            NewsArticle.batch_id,
            func.count(NewsArticle.id),
            func.max(NewsArticle.last_analysis_attempt)
        ).filter(
            NewsArticle.batch_id.isnot(None)
        ).group_by(
            NewsArticle.batch_id
        ).order_by(
            text("max DESC")
        ).limit(5).all()
        
        for batch_id, count, last_attempt in recent_batches:
            print(f"  - {batch_id}: {count} articles, last updated: {last_attempt}")
            
        # Get entity counts
        entity_count = session.query(func.count(Entity.id)).scalar() or 0
        entity_mention_count = session.query(func.count(EntityMention.id)).scalar() or 0
        print(f"\nTotal entities: {entity_count}")
        print(f"Total entity mentions: {entity_mention_count}")
        
        # Verify articles with processed_at but no analysis_status
        inconsistent = session.query(func.count(NewsArticle.id)).filter(
            NewsArticle.processed_at.isnot(None),
            NewsArticle.analysis_status != "completed"
        ).scalar() or 0
        
        if inconsistent > 0:
            print(f"\nWARNING: Found {inconsistent} articles with processed_at set but analysis_status is not 'completed'")
        
        # Verify articles with analysis_status=completed but no processed_at
        missing_processed = session.query(func.count(NewsArticle.id)).filter(
            NewsArticle.processed_at.is_(None),
            NewsArticle.analysis_status == "completed"
        ).scalar() or 0
        
        if missing_processed > 0:
            print(f"\nWARNING: Found {missing_processed} articles with analysis_status='completed' but no processed_at date")
            
    finally:
        session.close()

if __name__ == "__main__":
    analyze_db_status()