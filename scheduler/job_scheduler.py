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

from database.models import get_db_connection, NewsArticle
from sqlalchemy import func, text
from sqlalchemy.orm import sessionmaker
from clustering.source_similarity import SourceSimilarityComputer
from clustering.cluster_manager import ClusterManager
from clustering.temporal_analyzer import TemporalAnalyzer
from analyzer.hotelling_t2 import update_weekly_statistics
from analyzer.entity_resolution import run_merge_job
from database.entity_pruning import prune_low_activity_entities
from database.refresh_materialized_views import refresh_mv_source_entity_week
from analyzer.entity_embeddings import run_entity_embedding_job
from analyzer.drift_detection import run_drift_detection_job

# Setup logging
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# force=True: the imports above configure the root logger first (module-level
# basicConfig in drift_detection et al.), which made this call a no-op and left
# scheduler.log empty since deploy day. Force our handlers in regardless.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "scheduler.log"),
        logging.StreamHandler()
    ],
    force=True,
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

    # Kick off the analyzer daemon for the day's batch; it submits async OpenAI
    # batches, ingests results, runs statistics once, and exits when done.
    ensure_analyzer_running()


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
        logger.info("Starting batch analyzer daemon (output -> logs/batch_analysis.log)")
        # The daemon logs to stderr; capture everything (including uncaught
        # tracebacks) in a host-mounted file. DEVNULL here once hid a 4-hour
        # billing-failure loop completely.
        daemon_log = open(LOG_DIR / "batch_analysis.log", "a")
        try:
            subprocess.Popen(
                ["python", "-m", "analyzer.batch_analyzer", "--daemon"],
                cwd=ROOT_DIR,
                stdout=daemon_log,
                stderr=subprocess.STDOUT
            )
        finally:
            daemon_log.close()  # the child holds its own copy of the fd
    else:
        logger.debug("Batch analyzer daemon is already running")


def ensure_analyzer_if_work():
    """Self-heal: restart the analyzer daemon only if unfinished analysis work exists.

    The daemon exits on its own once the day's articles are processed (running
    statistics exactly once). Restarting it unconditionally would re-run those
    statistics every idle cycle, so only intervene when a crash left work behind.
    Threshold matches the analyzer's minimum batch size (50) - a smaller tail
    waits for the next day's scrape rather than churning the daemon hourly.
    """
    if check_analyzer_status():
        return

    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()
        pending = session.query(NewsArticle).filter(
            NewsArticle.analysis_status.in_(["unanalyzed", "in_progress"]),
            NewsArticle.text != None,
            NewsArticle.text != "",
            # Retired articles (3 failed submissions) are not pending work
            func.coalesce(NewsArticle.analysis_attempts, 0) < 3
        ).count()
        session.close()
    except Exception as e:
        logger.error(f"Error checking pending analysis work: {e}", exc_info=True)
        return

    if pending >= 50:
        logger.info(f"{pending} articles awaiting analysis with no daemon running; restarting it")
        ensure_analyzer_running()


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


def run_entity_merge():
    """Auto-merge duplicate-name entities via canonical_id (analyzer/entity_resolution.py).

    Exact-match tier only - no human review queue, so fuzzy near-misses are deliberately
    left as separate entities rather than risk a bad automatic merge.
    """
    logger.info("Starting entity merge job")

    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()

        merged_count = run_merge_job(session)

        session.close()
        logger.info(f"Entity merge job completed: {merged_count} entities merged")

    except Exception as e:
        logger.error(f"Error in entity merge job: {e}", exc_info=True)


def run_entity_pruning():
    """Prune low-activity entities (database/entity_pruning.py).

    Runs after run_entity_merge in the weekly schedule so pruning sees post-merge mention
    counts, not counts fragmented across duplicate rows.
    """
    logger.info("Starting entity pruning job")

    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()

        pruned_count = prune_low_activity_entities(session)

        session.close()
        logger.info(f"Entity pruning job completed: {pruned_count} entities pruned")

    except Exception as e:
        logger.error(f"Error in entity pruning job: {e}", exc_info=True)


def run_mv_refresh():
    """Refresh mv_source_entity_week (database/refresh_materialized_views.py).

    Runs daily, after the weekly merge/pruning jobs so its canonical_id resolution
    reflects the latest merges.
    """
    logger.info("Starting materialized view refresh")

    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()

        refresh_mv_source_entity_week(session)

        session.close()
        logger.info("Materialized view refresh completed")

    except Exception as e:
        logger.error(f"Error refreshing materialized views: {e}", exc_info=True)


def run_entity_embeddings():
    """Recompute entity relatedness embeddings (analyzer/entity_embeddings.py).

    Runs after run_mv_refresh so the sentiment-profile matrix reflects the latest
    materialized-view data, and after the weekly merge job so entity identity is
    already resolved through canonical_id before the co-occurrence matrix is built.
    """
    logger.info("Starting entity embedding job")

    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()

        n = run_entity_embedding_job(session)

        session.close()
        logger.info(f"Entity embedding job completed: {n} entities embedded")

    except Exception as e:
        logger.error(f"Error in entity embedding job: {e}", exc_info=True)


def run_drift_detection():
    """Recompute statistical-surprise drift events (analyzer/drift_detection.py).

    Runs after run_mv_refresh for the same reason as run_entity_embeddings - depends
    on mv_source_entity_week reflecting the latest data and canonical entity ids.
    """
    logger.info("Starting drift detection job")

    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()

        n = run_drift_detection_job(session)

        session.close()
        logger.info(f"Drift detection job completed: {n} events written")

    except Exception as e:
        logger.error(f"Error in drift detection job: {e}", exc_info=True)


def database_maintenance():
    """Run database maintenance tasks."""
    logger.info("Starting database maintenance")
    
    try:
        # Vacuum analyze for performance. VACUUM can't run inside a transaction
        # block, and SQLAlchemy 2.x requires text() for raw SQL - the old
        # `conn.execute("VACUUM ANALYZE")` form failed silently every day.
        engine = get_db_connection()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("VACUUM ANALYZE"))

        logger.info("Database maintenance completed")
        
    except Exception as e:
        logger.error(f"Error in database maintenance: {e}", exc_info=True)


def setup_schedule():
    """Set up the job schedule."""
    # Daily scrape (05:00, after the 04:30 backup). run_scraper kicks the
    # analyzer daemon afterwards; it processes the day's articles via async
    # OpenAI batches and exits on its own when done.
    schedule.every().day.at("05:00").do(run_scraper)
    # Hourly crash recovery only - no-op while the daemon runs or when idle
    schedule.every().hour.do(ensure_analyzer_if_work)

    # Hourly jobs
    schedule.every().hour.do(update_sentiment_statistics)
    
    # Weekly jobs - entity merge, then pruning (needs post-merge counts), before similarity
    # computation at 02:00 so it runs against already-deduped entities.
    schedule.every().sunday.at("01:00").do(run_entity_merge)
    schedule.every().sunday.at("01:15").do(run_entity_pruning)
    schedule.every().sunday.at("02:00").do(run_weekly_similarity)

    # Monthly jobs (1st of month)
    # Note: schedule doesn't support monthly directly, so we check in the job
    schedule.every().day.at("03:00").do(lambda: run_monthly_clustering() if datetime.now().day == 1 else None)

    # Daily maintenance
    schedule.every().day.at("00:30").do(run_mv_refresh)
    schedule.every().day.at("04:00").do(database_maintenance)

    # Weekly narrative-analysis jobs (Phase 4/5) - after mv refresh and entity merge so
    # both the co-occurrence/sentiment matrices and the drift series see canonical,
    # up-to-date data. Staggered 15 minutes apart since both can be CPU/DB heavy.
    schedule.every().sunday.at("02:30").do(run_entity_embeddings)
    schedule.every().sunday.at("02:45").do(run_drift_detection)

    logger.info("Schedule configured:")
    logger.info("- Scraper: daily at 05:00 (analyzer daemon kicked after each scrape)")
    logger.info("- Analyzer crash recovery: hourly (only if >=50 articles pending)")
    logger.info("- Sentiment statistics: every hour")
    logger.info("- Entity merge: Sundays at 01:00")
    logger.info("- Entity pruning: Sundays at 01:15")
    logger.info("- Similarity computation: Sundays at 2 AM")
    logger.info("- Entity embeddings: Sundays at 02:30")
    logger.info("- Drift detection: Sundays at 02:45")
    logger.info("- Clustering: 1st of month at 3 AM")
    logger.info("- Materialized view refresh: Daily at 00:30")
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