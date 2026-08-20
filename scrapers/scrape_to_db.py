"""
Database integration module for the news scraper.
Handles batch insertion of articles into the database.
"""

import os
import sys
import logging
import datetime
import json
import signal
from typing import List, Dict, Any
import traceback
from dotenv import load_dotenv

# Configure logging (this module is the scraper entrypoint, so the root
# logger is configured here before the library imports below run).
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import DatabaseManager
from database.models import NewsArticle, NewsSource, MIN_ARTICLE_CHARS
from scrapers.news_sources import get_news_sources
from scrapers.parallel_scraper import scrape_feeds, scrape_feeds_generator

# Set by SIGTERM/SIGINT: the batch loop finishes the current batch (batches
# commit incrementally) and exits cleanly instead of dying mid-write. The
# scheduler sends SIGTERM before SIGKILL when the run overshoots its budget.
shutdown_requested = False


def _handle_shutdown_signal(sig, frame):
    global shutdown_requested
    shutdown_requested = True
    logger.info(f"Signal {sig} received; will stop after the current batch (committed work is saved)")


# Create a mapping of source names to country information
def get_source_country_mapping():
    """Create a mapping of source names to their countries from the configuration."""
    news_sources = get_news_sources()
    return {source['name']: source.get('country', 'Unknown') for source in news_sources}


def _clean_str(value) -> str:
    """Strip NUL bytes (Postgres text columns reject them) and whitespace."""
    if not value:
        return ''
    return value.replace('\x00', '').strip()


def _get_or_create_source(session, source_cache: Dict[str, int],
                          country_mapping: Dict[str, str], article: Dict[str, Any]) -> int:
    """Resolve the article's source id, creating the source row if needed.

    Runs in its own savepoint so the created row is safely part of the outer
    transaction before the id is cached - a later article failure can't roll
    it back underneath the cache.
    """
    source_name = article['source_name']
    if source_name in source_cache:
        return source_cache[source_name]

    with session.begin_nested():
        source = session.query(NewsSource).filter_by(name=source_name).first()
        if not source:
            source_country = country_mapping.get(source_name, 'Unknown')
            source = NewsSource(
                name=source_name,
                base_url=article.get('feed_url', ''),
                country=source_country,
                language=article.get('language', None)
            )
            session.add(source)
            session.flush()
            logger.info(f"Created new source: {source_name} with country: {source_country}")
        elif not source.country or source.country == 'Unknown':
            source.country = country_mapping.get(source_name, 'Unknown')
            logger.info(f"Updated source country for: {source_name} -> {source.country}")
        source_id = source.id

    source_cache[source_name] = source_id
    return source_id


def insert_articles_batch(db_manager: DatabaseManager, articles: List[Dict[str, Any]]) -> int:
    """
    Insert a batch of articles into the database in a single transaction.

    Each article gets its own savepoint, so one bad row (a NUL byte, an
    oversized field, a constraint violation) rolls back alone - it used to
    poison the session and lose every article after it in the batch.

    Args:
        db_manager: Database manager instance
        articles: List of article dictionaries

    Returns:
        Number of articles successfully inserted
    """
    if not articles:
        return 0

    session = db_manager.get_session()
    inserted_count = 0
    skipped_count = 0
    failed_count = 0

    source_cache = {}
    country_mapping = get_source_country_mapping()

    try:
        for i, article in enumerate(articles):
            article_id = article.get('id')
            article_url = article.get('url')

            if not article_id or not article_url or not article.get('source_name'):
                logger.warning(f"SKIPPING: article missing id/url/source_name: {article_url or article_id or '?'}")
                skipped_count += 1
                continue

            if len(article_url) > 1024:  # column limit; a URL this long is junk anyway
                logger.warning(f"SKIPPING: URL exceeds 1024 chars: {article_url[:120]}...")
                skipped_count += 1
                continue

            text = _clean_str(article.get('text'))
            if len(text) < MIN_ARTICLE_CHARS:  # paywall/JS stubs and headline-only fragments
                logger.info(f"Skipping short article ({len(text)} chars): {article_url}")
                skipped_count += 1
                continue

            try:
                source_id = _get_or_create_source(session, source_cache, country_mapping, article)

                already_exists = False
                with session.begin_nested():
                    # id is md5(url), so the id check covers the URL as well
                    if session.query(NewsArticle.id).filter_by(id=article_id).first() is not None:
                        already_exists = True
                    else:
                        # Ensure publish_date is a datetime object
                        publish_date = article.get('publish_date')
                        if publish_date and not isinstance(publish_date, datetime.datetime):
                            try:
                                publish_date = datetime.datetime.fromisoformat(str(publish_date))
                            except (ValueError, TypeError):
                                logger.warning(f"Could not parse publish_date for {article_url}, using current time")
                                publish_date = datetime.datetime.now()
                        elif not publish_date:
                            publish_date = datetime.datetime.now()

                        # Convert authors to a list if needed
                        if article.get('authors') and not isinstance(article.get('authors'), list):
                            authors = [str(article.get('authors'))]
                        else:
                            authors = article.get('authors', [])

                        # Convert extraction_info to dict if needed
                        extraction_info = article.get('extraction_info', {})
                        if isinstance(extraction_info, str):
                            try:
                                extraction_info = json.loads(extraction_info)
                            except json.JSONDecodeError:
                                extraction_info = {'error': 'Could not parse extraction_info JSON',
                                                   'raw': extraction_info}

                        new_article = NewsArticle(
                            id=article_id,
                            source_id=source_id,
                            url=article_url,
                            title=_clean_str(article.get('title'))[:512],  # column limit
                            text=text,
                            html=_clean_str(article.get('html')),
                            publish_date=publish_date,
                            authors=authors,
                            language=article.get('language', 'en'),
                            top_image=article.get('top_image', None),
                            scraped_at=article.get('scraped_at', datetime.datetime.now()),
                            extraction_info=extraction_info
                        )
                        session.add(new_article)
                        session.flush()  # surface bad-row errors inside the savepoint

                if already_exists:
                    logger.debug(f"Article already exists: {article_id}")
                    skipped_count += 1
                else:
                    inserted_count += 1

            except Exception as article_error:
                # The savepoint rolled back just this article; the session
                # stays healthy for the rest of the batch.
                failed_count += 1
                logger.error(f"ERROR processing article {i} ({article_url}): {article_error}")
                logger.error(traceback.format_exc())

        if inserted_count > 0:
            session.commit()

        logger.info(f"Batch insert: {inserted_count} inserted, {skipped_count} skipped, {failed_count} failed")
        return inserted_count

    except Exception as commit_error:
        logger.error(f"COMMIT ERROR: {commit_error}")
        logger.error(traceback.format_exc())
        session.rollback()
        raise

    finally:
        session.close()


def run_scraper_with_db() -> int:
    """
    Run the scraper and save results to the database.
    Uses a streaming approach to save articles in batches as they are processed.

    Returns:
        Total number of articles inserted
    """
    # Graceful shutdown on SIGTERM (scheduler budget overrun, docker stop)
    # and SIGINT (Ctrl+C): stop between batches, keeping committed work.
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)

    # Get limit from environment variable
    limit_per_feed = int(os.getenv('SCRAPER_LIMIT_PER_FEED', 5))

    logger.info("Initializing database connection")
    db_manager = DatabaseManager()

    # Verify database connection before doing any network work
    test_session = db_manager.get_session()
    try:
        from sqlalchemy import text
        test_session.execute(text("SELECT 1")).fetchone()
        initial_count = test_session.query(NewsArticle).count()
        logger.info(f"Database connection verified: {initial_count} articles currently stored")
    finally:
        test_session.close()

    # Get news sources
    news_sources = get_news_sources()

    # Convert to feed configs
    feed_configs = []
    for source in news_sources:
        for feed_url in source.get('rss_feeds', []):
            feed_configs.append({
                'url': feed_url,
                'source_name': source['name'],
                'country': source.get('country', None),
                'language': source.get('language', None)
            })

    logger.info(f"Starting scraper with {len(feed_configs)} feeds (limit: {limit_per_feed} articles per feed)")

    total_inserted = 0
    batch_counter = 0

    for article_batch in scrape_feeds_generator(feed_configs, limit_per_feed):
        if shutdown_requested:
            logger.info("Shutdown requested; stopping cleanly (committed batches are saved)")
            break
        if not article_batch:
            continue

        batch_counter += 1
        logger.info(f"BATCH {batch_counter}: inserting {len(article_batch)} articles")
        try:
            batch_inserted = insert_articles_batch(db_manager, article_batch)
            total_inserted += batch_inserted
            logger.info(f"BATCH {batch_counter} done: {batch_inserted}/{len(article_batch)} inserted "
                        f"(running total: {total_inserted})")
        except Exception as batch_error:
            # One failed batch loses only itself; the run continues.
            logger.error(f"BATCH {batch_counter} failed entirely: {batch_error}")
            logger.error(traceback.format_exc())

    # Verify final article count to confirm inserts worked
    count_session = db_manager.get_session()
    try:
        final_count = count_session.query(NewsArticle).count()
        change = final_count - initial_count
        logger.info(f"DATABASE VERIFICATION: before: {initial_count}, after: {final_count}, "
                    f"change: {change}, reported inserted: {total_inserted}")
        if change != total_inserted:
            logger.warning(f"INCONSISTENCY DETECTED: expected {total_inserted} new articles, "
                           f"database shows {change}")
    except Exception as count_error:
        logger.error(f"Failed to get final article count: {count_error}")
    finally:
        count_session.close()

    logger.info(f"Scraping completed. Total articles inserted: {total_inserted}")
    return total_inserted


if __name__ == "__main__":
    try:
        run_scraper_with_db()
    except KeyboardInterrupt:
        logger.info("Interrupted; committed batches are saved")
        sys.exit(130)
    except Exception:
        # A systemic failure must exit nonzero - it used to be swallowed here,
        # and the scheduler logged "completed successfully" on a half-done run.
        logger.error("Scraper run failed:")
        logger.error(traceback.format_exc())
        sys.exit(1)
