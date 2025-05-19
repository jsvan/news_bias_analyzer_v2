#!/usr/bin/env python3
"""
Script to monitor batch analysis activity.
Shows active batches, processing statistics, and recent activity.

Usage: ./run.sh custom analyzer/tools/monitor_batch_analysis.py
"""

import os
import sys
import json
import datetime
from sqlalchemy import func, desc

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention

# Set paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCHES_FILE = os.path.join(ROOT_DIR, "analyzer", "batches.txt")

def read_batches_file():
    """Read active batches from batches.txt file."""
    if not os.path.exists(BATCHES_FILE):
        return []
    
    try:
        with open(BATCHES_FILE, 'r') as f:
            batches = [json.loads(line) for line in f if line.strip()]
            return batches
    except Exception as e:
        print(f"Error reading batches file: {e}")
        return []

def monitor_batch_analysis():
    """Monitor batch analysis activity and show statistics."""
    print("\n===== BATCH ANALYSIS MONITORING =====")
    
    # Initialize database connection
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Get article status counts
        status_counts = session.query(
            NewsArticle.analysis_status,
            func.count(NewsArticle.id)
        ).group_by(
            NewsArticle.analysis_status
        ).all()
        
        total_articles = sum(count for _, count in status_counts)
        
        print("\nArticle Status Summary:")
        for status, count in status_counts:
            percentage = round((count / total_articles) * 100, 1) if total_articles > 0 else 0
            print(f"  - {status or 'null'}: {count} articles ({percentage}%)")
        
        # Get active batches from tracking file
        active_batches = read_batches_file()
        
        print(f"\nActive Batches: {len(active_batches)}")
        if active_batches:
            for i, batch in enumerate(active_batches, 1):
                created_at = batch.get('created_at', 'Unknown')
                if isinstance(created_at, str) and created_at != 'Unknown':
                    try:
                        # Parse ISO format
                        dt = datetime.datetime.fromisoformat(created_at)
                        age = datetime.datetime.now() - dt
                        age_str = f"{age.total_seconds() / 60:.1f} minutes ago"
                    except ValueError:
                        age_str = "Unknown"
                else:
                    age_str = "Unknown"
                
                print(f"  {i}. Batch: {batch.get('id', 'Unknown')}")
                print(f"     Status: {batch.get('status', 'Unknown')}")
                print(f"     Created: {age_str}")
                print(f"     Articles: {batch.get('article_count', 'Unknown')}")
        else:
            print("  No active batches found.")
        
        # Get recent processing activity
        recent_completed = session.query(
            NewsArticle.id,
            NewsArticle.title,
            NewsArticle.processed_at
        ).filter(
            NewsArticle.analysis_status == "completed"
        ).order_by(
            desc(NewsArticle.processed_at)
        ).limit(5).all()
        
        print("\nRecent Completed Articles:")
        if recent_completed:
            for article_id, title, processed_at in recent_completed:
                title_short = (title[:50] + '...') if title and len(title) > 50 else title or 'Untitled'
                time_ago = datetime.datetime.now() - processed_at if processed_at else datetime.timedelta(0)
                time_ago_str = f"{time_ago.total_seconds() / 60:.1f} minutes ago" if processed_at else "Unknown"
                
                # Count entity mentions for this article
                entity_count = session.query(func.count(EntityMention.id)).filter(
                    EntityMention.article_id == article_id
                ).scalar() or 0
                
                print(f"  - Article {article_id}: '{title_short}'")
                print(f"    Completed: {time_ago_str}, Entities: {entity_count}")
        else:
            print("  No recently completed articles found.")
        
        # Get processing throughput stats
        last_hour = datetime.datetime.now() - datetime.timedelta(hours=1)
        last_day = datetime.datetime.now() - datetime.timedelta(days=1)
        
        completed_last_hour = session.query(func.count(NewsArticle.id)).filter(
            NewsArticle.analysis_status == "completed",
            NewsArticle.processed_at > last_hour
        ).scalar() or 0
        
        completed_last_day = session.query(func.count(NewsArticle.id)).filter(
            NewsArticle.analysis_status == "completed",
            NewsArticle.processed_at > last_day
        ).scalar() or 0
        
        print("\nProcessor Throughput:")
        print(f"  - Last hour: {completed_last_hour} articles completed")
        print(f"  - Last 24 hours: {completed_last_day} articles completed")
        
        # Estimate remaining time
        unanalyzed_count = dict(status_counts).get('unanalyzed', 0)
        hourly_rate = max(1, completed_last_hour)  # Avoid division by zero
        
        if unanalyzed_count > 0:
            remaining_hours = unanalyzed_count / hourly_rate
            print(f"\nEstimated completion time for remaining {unanalyzed_count} articles:")
            print(f"  - At current rate ({hourly_rate} articles/hour): {remaining_hours:.1f} hours")
        
    finally:
        session.close()

if __name__ == "__main__":
    monitor_batch_analysis()