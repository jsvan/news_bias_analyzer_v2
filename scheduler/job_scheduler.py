#!/usr/bin/env python3
"""
Job scheduler for the News Bias Analyzer.

Coordinates the timing of:
1. Daily news scraping (continuous)
2. Batch analysis via OpenAI (continuous with rate limits)
3. Weekly similarity computation (Sundays 2 AM)
4. Monthly clustering (1st of month, 3 AM)
5. Database maintenance (entity pruning, backups)
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
import schedule
import signal
import subprocess
from pathlib import Path

# Setup paths
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from database.models import get_db_connection
from sqlalchemy.orm import sessionmaker
from clustering.source_similarity import SourceSimilarityComputer
from clustering.cluster_manager import ClusterManager
from clustering.temporal_analyzer import TemporalAnalyzer
from analyzer.hotelling_t2 import update_weekly_statistics

# Setup logging
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduler")

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info("Shutdown signal received. Finishing current jobs...")
    shutdown_requested = True


def run_scraper():
    """Run the news scraper."""
    logger.info("Starting news scraper job")
    try:
        # Run scraper with timeout
        result = subprocess.run(
            ["python", "-m", "scrapers.scrape_to_db"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if result.returncode == 0:
            logger.info("Scraper completed successfully")
        else:
            logger.error(f"Scraper failed with code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error("Scraper timed out after 1 hour")
    except Exception as e:
        logger.error(f"Error running scraper: {e}")


def check_analyzer_status():
    """Check if the batch analyzer daemon is running."""
    lock_file = ROOT_DIR / "analyzer" / "analyzer.lock"
    if lock_file.exists():
        # Check if process is actually running
        try:
            # Try to acquire lock to see if process is alive
            import fcntl
            with open(lock_file, 'w') as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
            # If we got here, lock was available = process died
            logger.warning("Analyzer lock file exists but process is dead")
            lock_file.unlink()
            return False
        except IOError:
            # Lock is held = process is running
            return True
    return False


def ensure_analyzer_running():
    """Ensure the batch analyzer daemon is running."""
    if not check_analyzer_status():
        logger.info("Starting batch analyzer daemon")
        subprocess.Popen(
            ["python", "-m", "analyzer.batch_analyzer", "--daemon"],
            cwd=ROOT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    else:
        logger.debug("Batch analyzer daemon is already running")


def run_weekly_similarity():
    """Run weekly similarity computation."""
    logger.info("Starting weekly similarity computation")
    
    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Run similarity computation
        similarity_computer = SourceSimilarityComputer(session)
        similarity_computer.compute_weekly_similarities()
        
        # Run temporal analysis
        temporal_analyzer = TemporalAnalyzer(session)
        temporal_analyzer.compute_weekly_drift_metrics()
        
        session.close()
        logger.info("Weekly similarity computation completed")
        
    except Exception as e:
        logger.error(f"Error in weekly similarity computation: {e}", exc_info=True)


def run_monthly_clustering():
    """Run monthly clustering job."""
    logger.info("Starting monthly clustering")
    
    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()
        
        cluster_manager = ClusterManager(session)
        cluster_manager.perform_monthly_clustering()
        
        session.close()
        logger.info("Monthly clustering completed")
        
    except Exception as e:
        logger.error(f"Error in monthly clustering: {e}", exc_info=True)


def update_sentiment_statistics():
    """Update weekly sentiment statistics for T² calculations."""
    logger.info("Starting weekly sentiment statistics update")
    
    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()
        
        count = update_weekly_statistics(session)
        
        session.close()
        logger.info(f"Updated sentiment statistics for {count} entities")
        
    except Exception as e:
        logger.error(f"Error updating sentiment statistics: {e}", exc_info=True)


def database_maintenance():
    """Run database maintenance tasks."""
    logger.info("Starting database maintenance")
    
    try:
        # Vacuum analyze for performance
        engine = get_db_connection()
        with engine.connect() as conn:
            conn.execute("VACUUM ANALYZE")
            conn.commit()
        
        logger.info("Database maintenance completed")
        
    except Exception as e:
        logger.error(f"Error in database maintenance: {e}", exc_info=True)


def setup_schedule():
    """Set up the job schedule."""
    # Continuous jobs (every N minutes/hours)
    schedule.every(30).minutes.do(run_scraper)
    schedule.every(5).minutes.do(ensure_analyzer_running)
    
    # Hourly jobs
    schedule.every().hour.do(update_sentiment_statistics)
    
    # Weekly jobs
    schedule.every().sunday.at("02:00").do(run_weekly_similarity)
    
    # Monthly jobs (1st of month)
    # Note: schedule doesn't support monthly directly, so we check in the job
    schedule.every().day.at("03:00").do(lambda: run_monthly_clustering() if datetime.now().day == 1 else None)
    
    # Daily maintenance
    schedule.every().day.at("04:00").do(database_maintenance)
    
    logger.info("Schedule configured:")
    logger.info("- Scraper: every 30 minutes")
    logger.info("- Analyzer check: every 5 minutes")
    logger.info("- Sentiment statistics: every hour")
    logger.info("- Similarity computation: Sundays at 2 AM")
    logger.info("- Clustering: 1st of month at 3 AM")
    logger.info("- Database maintenance: Daily at 4 AM")


def main():
    """Main scheduler loop."""
    logger.info("News Bias Analyzer Scheduler starting")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Set up schedule
    setup_schedule()
    
    # Run scraper immediately on startup
    run_scraper()
    
    # Main loop
    while not shutdown_requested:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            time.sleep(300)  # Wait 5 minutes before retrying
    
    logger.info("Scheduler shutdown complete")


if __name__ == "__main__":
    main()