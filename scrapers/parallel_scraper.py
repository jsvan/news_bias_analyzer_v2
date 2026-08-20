"""
Two-stage parallel scraper for news articles.

Stage 1 fetches all RSS feeds concurrently (bounded by SCRAPER_WORKERS, spaced
per domain). Stage 2 runs a worker pool over one flat article queue, so a slow
host only ever costs its own worker slot - never a whole batch of feeds.
"""

import asyncio
import calendar
import datetime
import hashlib
import logging
import os
import random
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
import feedparser
import requests
import trafilatura
from trafilatura.metadata import extract_metadata

# No basicConfig here: this module is imported as a library, and configuring
# the root logger at import time silently overrides the entrypoint's config.
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Constants
# SCRAPER_TIMEOUT is the legacy shared knob; the split vars win when set.
RSS_TIMEOUT = int(os.getenv('SCRAPER_RSS_TIMEOUT', os.getenv('SCRAPER_TIMEOUT', 20)))  # seconds
ARTICLE_TIMEOUT = int(os.getenv('SCRAPER_ARTICLE_TIMEOUT', os.getenv('SCRAPER_TIMEOUT', 30)))  # seconds
# Hard wall-clock ceiling for one article fetch including the requests
# fallback, whose `timeout=` only bounds gaps between bytes - a tarpit host
# dripping one byte every few seconds otherwise holds a worker indefinitely.
FETCH_DEADLINE = ARTICLE_TIMEOUT + 15
MAX_FETCH_BYTES = 5 * 1024 * 1024  # cap article downloads; news pages are far smaller
WORKERS = int(os.getenv('SCRAPER_WORKERS', 16))  # concurrent fetch/extract slots
YIELD_BATCH_SIZE = int(os.getenv('SCRAPER_BATCH_SIZE', 20))  # articles per yielded DB batch
MIN_DELAY = float(os.getenv('SCRAPER_MIN_DELAY', 1))  # Minimum delay between requests to same domain (seconds)
MAX_DELAY = float(os.getenv('SCRAPER_MAX_DELAY', 3))  # Maximum delay between requests to same domain (seconds)
MAX_RETRIES = 2  # Maximum retry attempts for failed requests
SCRAPER_LIMIT_PER_FEED = int(os.getenv('SCRAPER_LIMIT_PER_FEED', 5))  # Default limit of articles per feed
USER_AGENT = os.getenv('SCRAPER_USER_AGENT', 'News Bias Analyzer Bot/1.0')

# One shared executor for blocking work (trafilatura parsing, requests
# fallback, DB checks). Sized above WORKERS so parse jobs aren't starved
# when every worker's fallback fetch occupies a thread.
_EXECUTOR = ThreadPoolExecutor(max_workers=WORKERS + 4)

_SENTINEL = object()

NON_ARTICLE_PATTERNS = [
    '/tag/', '/tags/', '/topic/', '/topics/',
    '/category/', '/categories/',
    '/author/', '/authors/',
    '/search/', '/video/', '/videos/',
    '/live/', '/gallery/', '/galleries/',
    '/section/', '/sections/',
    '/login', '/subscribe', '/comments',
]


def get_domain(url: str) -> str:
    """Extract domain from URL for rate limiting purposes."""
    parsed = urlparse(url)
    return parsed.netloc


def looks_like_article(url: str) -> bool:
    """Filter section/category pages out of feed entries.

    Section pages ("/world/") are shallow trailing-slash paths whose last
    segment is a plain word; article permalinks that end in '/' (WordPress,
    Arc CMS) are deeper or slug-like. The old blanket endswith('/') test threw
    away every article from such sites - whole feeds yielded zero for weeks.
    """
    path_segments = [s for s in urlparse(url).path.split('/') if s]
    if not path_segments:
        return False  # homepage
    if url.rstrip().endswith('/') and len(path_segments) < 2 and '-' not in path_segments[-1]:
        return False
    if any(pattern in url.lower() for pattern in NON_ARTICLE_PATTERNS):
        return False
    return True


class DomainThrottle:
    """Spaces requests per domain.

    Reservation-based: each task books the next free slot under the domain's
    lock, then sleeps outside it. The old check-then-act version let every
    concurrent same-domain task read the same stale timestamp and fire at
    once - burst traffic plus pointless sleeps.
    """

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._next_ok: Dict[str, float] = {}

    async def wait(self, domain: str):
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            start = max(now, self._next_ok.get(domain, now))
            self._next_ok[domain] = start + random.uniform(MIN_DELAY, MAX_DELAY)
            delay = start - now
        if delay > 0:
            logger.debug(f"Rate limiting {domain}, waiting {delay:.2f}s")
            await asyncio.sleep(delay)


async def run_in_executor(func, *args):
    """Run a blocking function in the shared executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, func, *args)


async def fetch_rss_feed(
    session: aiohttp.ClientSession,
    feed_url: str,
    source_name: str,
    throttle: DomainThrottle,
) -> List[Dict[str, Any]]:
    """
    Fetch and parse an RSS feed.

    Args:
        session: aiohttp client session
        feed_url: URL of the RSS feed
        source_name: Name of the news source
        throttle: per-domain request spacer

    Returns:
        List of article entries from the feed
    """
    articles = []

    for attempt in range(MAX_RETRIES + 1):
        try:
            await throttle.wait(get_domain(feed_url))
            logger.info(f"Fetching RSS feed: {feed_url}")
            headers = {
                'User-Agent': USER_AGENT
            }
            async with session.get(feed_url, timeout=RSS_TIMEOUT, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch RSS feed {feed_url}: Status {response.status}")
                    return articles

                # Raw bytes: feedparser does its own encoding detection, and
                # response.text() raised UnicodeDecodeError on feeds whose
                # declared charset lies - which used to drop the whole feed.
                content = await response.read()

            feed = await run_in_executor(feedparser.parse, content)

            if not feed.entries:
                logger.warning(f"No entries found in RSS feed: {feed_url}")
                return articles

            for entry in feed.entries:
                if 'link' not in entry:
                    continue

                url = entry.link
                if not looks_like_article(url):
                    logger.debug(f"Skipping non-article URL: {url}")
                    continue

                article = {
                    'url': url,
                    'title': entry.get('title', ''),
                    'publish_date': entry.get('published_parsed') or entry.get('updated_parsed'),
                    'source_name': source_name,
                    'feed_url': feed_url
                }

                # Generate a unique ID based on the URL
                article['id'] = hashlib.md5(article['url'].encode()).hexdigest()

                # published_parsed is UTC; calendar.timegm reads it as such.
                # (time.mktime read it as local and shifted every date 7-8h.)
                if article['publish_date']:
                    article['publish_date'] = datetime.datetime.fromtimestamp(
                        calendar.timegm(article['publish_date']))

                articles.append(article)

            logger.info(f"Found {len(articles)} articles in feed: {feed_url}")
            return articles

        except asyncio.TimeoutError:
            logger.warning(f"Timeout while fetching RSS feed: {feed_url} (attempt {attempt + 1}/{MAX_RETRIES + 1})")
            await asyncio.sleep(1)  # Brief pause before retry

        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {str(e)}")
            return articles

    return articles


def _parse_article_html(html_content: str, extraction_info: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """Extract text, html and metadata from raw page HTML (blocking; run in executor)."""
    extracted_text = trafilatura.extract(html_content, include_comments=False)
    if not extracted_text:
        extraction_info['error'] = "No content extracted"
        return None, None, extraction_info

    extracted_html = trafilatura.extract(html_content, output_format='html')
    metadata = extract_metadata(html_content)

    extraction_info['title'] = metadata.title if metadata else ''
    extraction_info['author'] = metadata.author if metadata else ''
    extraction_info['date'] = metadata.date if metadata else ''
    extraction_info['success'] = True
    extraction_info['text_length'] = len(extracted_text)

    return extracted_text, extracted_html, extraction_info


def extract_with_requests(url: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Extract an article using requests + trafilatura (blocking; run in executor).

    Args:
        url: URL of the article

    Returns:
        Tuple of (text content, HTML content, extraction info)
    """
    extraction_info = {
        'extractor': 'requests+trafilatura',
        'success': False,
        'timestamp': datetime.datetime.now().isoformat(),
        'error': None
    }

    response = None
    try:
        headers = {
            'User-Agent': USER_AGENT
        }

        # requests' timeout only bounds connect time and gaps between bytes;
        # the manual deadline bounds the whole download against drip-feeding
        # anti-bot hosts.
        response = requests.get(url, headers=headers, timeout=ARTICLE_TIMEOUT, stream=True)
        if response.status_code != 200:
            extraction_info['error'] = f"HTTP error: {response.status_code}"
            return None, None, extraction_info

        deadline = time.monotonic() + FETCH_DEADLINE
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=65536):
            chunks.append(chunk)
            size += len(chunk)
            if time.monotonic() > deadline:
                raise TimeoutError(f"fetch exceeded {FETCH_DEADLINE}s total")
            if size > MAX_FETCH_BYTES:
                break

        html_content = b''.join(chunks).decode(response.encoding or 'utf-8', errors='ignore')
        return _parse_article_html(html_content, extraction_info)

    except Exception as e:
        logger.error(f"Error extracting {url}: {str(e)}")
        extraction_info['error'] = str(e)
        return None, None, extraction_info

    finally:
        if response is not None:
            response.close()


async def extract_article_content_async(url: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Extract article content in the shared executor under a hard overall deadline.

    (A wget-based primary path existed here for years, but the production image
    never shipped wget - every article has always taken the requests path, so
    the dead branch is gone.)

    Args:
        url: URL of the article

    Returns:
        Tuple of (text content, HTML content, extraction info)
    """
    try:
        return await asyncio.wait_for(
            run_in_executor(extract_with_requests, url),
            FETCH_DEADLINE + 30,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Extraction deadline exceeded for {url}")
        return None, None, {
            'extractor': 'requests+trafilatura',
            'success': False,
            'timestamp': datetime.datetime.now().isoformat(),
            'error': 'fetch deadline exceeded',
        }


async def process_article(article_data: Dict[str, Any], throttle: DomainThrottle) -> Dict[str, Any]:
    """
    Process a single article by extracting its content.

    Args:
        article_data: Dictionary with article metadata
        throttle: per-domain request spacer

    Returns:
        Updated article data with content
    """
    url = article_data['url']
    await throttle.wait(get_domain(url))

    logger.info(f"Processing article: {url}")
    text, html, extraction_info = await extract_article_content_async(url)

    article_data['text'] = text
    article_data['html'] = html
    article_data['extraction_info'] = extraction_info
    article_data['scraped_at'] = datetime.datetime.now()

    return article_data


def _check_urls_in_database_sync(urls: List[str]) -> Dict[str, bool]:
    """Check which URLs already exist in the database (blocking; run in executor)."""
    # Import here to avoid circular imports
    from database.db import DatabaseManager
    from database.models import NewsArticle

    results = {url: False for url in urls}

    db_manager = DatabaseManager()
    session = db_manager.get_session()
    try:
        chunk_size = 100
        for i in range(0, len(urls), chunk_size):
            chunk = urls[i:i + chunk_size]
            for (url,) in session.query(NewsArticle.url).filter(NewsArticle.url.in_(chunk)).all():
                results[url] = True

        logger.info(f"URL database check: {sum(results.values())} of {len(urls)} URLs already exist in database")
        return results
    finally:
        session.close()


async def check_urls_in_database(urls: List[str]) -> Dict[str, bool]:
    """Check if URLs already exist in the database.

    A failure here propagates: if the database is unreachable the run cannot
    store anything anyway, so aborting loudly beats silently re-extracting
    every already-stored article (the old "assume none exist" behavior).
    """
    return await run_in_executor(_check_urls_in_database_sync, urls)


async def run_scraper(feed_configs: List[Dict[str, Any]], limit_per_feed: int = None):
    """
    Run the two-stage scraper process.

    Args:
        feed_configs: List of feed configuration dictionaries
        limit_per_feed: Maximum number of articles to process per feed

    Yields:
        Batches of processed articles as they are completed
    """
    if limit_per_feed is None:
        limit_per_feed = SCRAPER_LIMIT_PER_FEED

    throttle = DomainThrottle()

    feed_configs = list(feed_configs)
    # Shuffle so an aborted run doesn't starve the same tail of the config
    # every day - the fixed order plus daily timeouts silently dropped the
    # last ~35 feeds for days at a time.
    random.shuffle(feed_configs)

    stats = {'feeds_ok': 0, 'feeds_failed': 0, 'entries_found': 0,
             'articles_new': 0, 'articles_yielded': 0, 'articles_failed': 0}

    async with aiohttp.ClientSession() as session:
        # Stage 1: fetch every RSS feed, bounded by WORKERS. One bad feed
        # only loses itself (return_exceptions), never the run.
        sem = asyncio.Semaphore(WORKERS)

        async def fetch_one(feed):
            async with sem:
                return await fetch_rss_feed(session, feed['url'], feed['source_name'], throttle)

        feed_results = await asyncio.gather(
            *[fetch_one(feed) for feed in feed_configs], return_exceptions=True)

        # Collect, cap per feed, and dedupe in flight: the same story often
        # appears in several section feeds of one outlet and used to be
        # extracted once per feed.
        seen_urls = set()
        work_items = []
        for feed, result in zip(feed_configs, feed_results):
            if isinstance(result, BaseException):
                stats['feeds_failed'] += 1
                logger.error(f"Feed failed: {feed['url']}: {result}")
                continue
            stats['feeds_ok'] += 1
            stats['entries_found'] += len(result)
            capped = result[:limit_per_feed] if limit_per_feed else result
            for article in capped:
                if article['url'] in seen_urls:
                    continue
                seen_urls.add(article['url'])
                work_items.append(article)

        logger.info(f"RSS stage done: {stats['feeds_ok']} feeds ok, {stats['feeds_failed']} failed, "
                    f"{len(work_items)} distinct articles (of {stats['entries_found']} feed entries)")

        if work_items:
            existing_urls = await check_urls_in_database([a['url'] for a in work_items])
            work_items = [a for a in work_items if not existing_urls.get(a['url'], False)]
        stats['articles_new'] = len(work_items)
        logger.info(f"{stats['articles_new']} articles are new; extracting with {WORKERS} workers")

        if work_items:
            # Spread domains through the queue so per-domain spacing doesn't
            # stall a cluster of same-site articles at the front.
            random.shuffle(work_items)

            # Stage 2: worker pool over one flat queue. The old design
            # processed articles in lockstep rounds gated by the slowest
            # fetch, with a mandatory 2s sleep per round - a ~33/min ceiling.
            queue = asyncio.Queue()
            for article in work_items:
                queue.put_nowait(article)
            results = asyncio.Queue()

            async def worker():
                while True:
                    try:
                        article = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        await results.put(_SENTINEL)
                        return
                    try:
                        processed = await process_article(article, throttle)
                    except Exception as e:
                        # One bad article loses itself, not the worker.
                        logger.error(f"Worker error on {article.get('url', 'unknown')}: {e}")
                        logger.error(traceback.format_exc())
                        article['text'] = None
                        article['html'] = None
                        article['extraction_info'] = {'error': f'worker error: {e}'}
                        processed = article
                    await results.put(processed)

            worker_tasks = [
                asyncio.ensure_future(worker())
                for _ in range(min(WORKERS, len(work_items)))
            ]

            finished_workers = 0
            processed_count = 0
            batch = []
            try:
                while finished_workers < len(worker_tasks):
                    item = await results.get()
                    if item is _SENTINEL:
                        finished_workers += 1
                        continue

                    processed_count += 1
                    text = item.get('text') or ''
                    if len(text) > 100:  # Only accept articles with meaningful content
                        batch.append(item)
                        stats['articles_yielded'] += 1
                    else:
                        stats['articles_failed'] += 1
                        error = (item.get('extraction_info') or {}).get('error', 'short or empty text')
                        logger.warning(f"Skipping article {item.get('url', 'unknown')}: {error}")

                    if processed_count % 100 == 0:
                        logger.info(f"Progress: {processed_count}/{stats['articles_new']} articles processed "
                                    f"({stats['articles_yielded']} extracted)")

                    if len(batch) >= YIELD_BATCH_SIZE:
                        yield batch
                        batch = []
            finally:
                for task in worker_tasks:
                    task.cancel()

            if batch:
                yield batch

    logger.info(f"Scrape summary: {stats['feeds_ok']}/{stats['feeds_ok'] + stats['feeds_failed']} feeds fetched, "
                f"{stats['articles_new']} new articles, "
                f"{stats['articles_yielded']} extracted, {stats['articles_failed']} failed")


def scrape_feeds_generator(feed_configs: List[Dict[str, Any]], limit_per_feed: int = None):
    """
    Main entry point for the scraper that yields article batches as they are processed.

    Args:
        feed_configs: List of feed configurations with 'url' and 'source_name'
        limit_per_feed: Maximum number of articles to process per feed

    Yields:
        Batches of processed articles as they are completed
    """
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    generator = run_scraper(feed_configs, limit_per_feed)
    try:
        while True:
            try:
                batch = event_loop.run_until_complete(generator.__anext__())
            except StopAsyncIteration:
                break
            yield batch
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        return
    except GeneratorExit:
        # Caller stopped consuming (e.g. graceful shutdown): let the async
        # generator's cleanup cancel its worker tasks.
        event_loop.run_until_complete(generator.aclose())
        raise
    except Exception as e:
        # Systemic failure - per-feed and per-article errors are contained
        # upstream. Swallowing this used to skip the rest of the run and
        # still report success with exit code 0.
        logger.error(f"Scraper error: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    finally:
        try:
            event_loop.close()
        except Exception:
            pass


def scrape_feeds(feed_configs: List[Dict[str, Any]], limit_per_feed: int = None) -> List[Dict[str, Any]]:
    """
    Legacy entry point for the scraper that returns all articles at once.
    Use scrape_feeds_generator for more efficient streaming approach.

    Args:
        feed_configs: List of feed configurations with 'url' and 'source_name'
        limit_per_feed: Maximum number of articles to process per feed

    Returns:
        List of processed articles
    """
    logger.warning(
        "Using legacy scrape_feeds() function that accumulates all articles in memory. "
        "Consider using scrape_feeds_generator() instead for streaming efficiency."
    )
    all_articles = []
    for batch in scrape_feeds_generator(feed_configs, limit_per_feed):
        all_articles.extend(batch)
    return all_articles


if __name__ == "__main__":
    # Example usage when run directly
    from scrapers.news_sources import get_news_sources

    # Get news sources
    news_sources = get_news_sources()

    # Convert to feed configs
    feed_configs = []
    for source in news_sources:
        for feed_url in source.get('rss_feeds', []):
            feed_configs.append({
                'url': feed_url,
                'source_name': source['name']
            })

    # Get limit from environment or command line
    limit = SCRAPER_LIMIT_PER_FEED
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass

    logger.info(f"Starting scraper with {len(feed_configs)} feeds (limit: {limit} articles per feed)")
    articles = scrape_feeds(feed_configs, limit_per_feed=limit)
    logger.info(f"Scraping completed. Processed {len(articles)} articles")
