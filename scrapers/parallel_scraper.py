"""
Two-stage parallel scraper for news articles.
Handles RSS feed fetching and article extraction with batching for efficiency.
"""

import asyncio
import logging
import time
import random
import hashlib
import json
import os
import sys
import datetime
import traceback
import aiohttp
import feedparser
from typing import List, Dict, Any, Tuple, Optional
import subprocess
import tempfile
from urllib.parse import urlparse
import importlib.util
import requests
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Constants
RSS_TIMEOUT = int(os.getenv('SCRAPER_TIMEOUT', 20))  # seconds
ARTICLE_TIMEOUT = int(os.getenv('SCRAPER_TIMEOUT', 30))  # seconds
BATCH_SIZE = int(os.getenv('SCRAPER_BATCH_SIZE', 20))  # Process 20 feeds at a time
MIN_DELAY = float(os.getenv('SCRAPER_MIN_DELAY', 1))  # Minimum delay between requests to same domain (seconds)
MAX_DELAY = float(os.getenv('SCRAPER_MAX_DELAY', 3))  # Maximum delay between requests to same domain (seconds)
MAX_RETRIES = 2  # Maximum retry attempts for failed requests
DEFAULT_LIMIT_PER_FEED = int(os.getenv('SCRAPER_LIMIT_PER_FEED', 5))  # Default limit of articles per feed
USER_AGENT = os.getenv('SCRAPER_USER_AGENT', 'News Bias Analyzer Bot/1.0')

# Track last request time per domain to respect rate limits
domain_last_request = {}

def get_domain(url: str) -> str:
    """Extract domain from URL for rate limiting purposes."""
    parsed = urlparse(url)
    return parsed.netloc

async def fetch_rss_feed(session: aiohttp.ClientSession, feed_url: str, source_name: str) -> List[Dict[str, Any]]:
    """
    Fetch and parse an RSS feed.
    
    Args:
        session: aiohttp client session
        feed_url: URL of the RSS feed
        source_name: Name of the news source
        
    Returns:
        List of article entries from the feed
    """
    domain = get_domain(feed_url)
    
    # Respect rate limits
    now = time.time()
    if domain in domain_last_request:
        elapsed = now - domain_last_request[domain]
        if elapsed < MIN_DELAY:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            logger.debug(f"Rate limiting {domain}, waiting {delay:.2f}s")
            await asyncio.sleep(delay)
    
    domain_last_request[domain] = time.time()
    
    articles = []
    retry_count = 0
    
    while retry_count <= MAX_RETRIES:
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")
            headers = {
                'User-Agent': USER_AGENT
            }
            async with session.get(feed_url, timeout=RSS_TIMEOUT, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch RSS feed {feed_url}: Status {response.status}")
                    break
                
                content = await response.text()
                feed = feedparser.parse(content)
                
                if not feed.entries:
                    logger.warning(f"No entries found in RSS feed: {feed_url}")
                    break
                
                for entry in feed.entries:
                    if 'link' not in entry:
                        continue
                    
                    url = entry.link
                    
                    # Skip URLs that don't have enough path segments
                    # These are likely homepage URLs rather than article URLs
                    if url.count('/') < 3:
                        logger.debug(f"Skipping URL with insufficient path segments: {url}")
                        continue
                    
                    # Skip URLs ending with / (likely section/category pages)
                    if url.rstrip().endswith('/'):
                        logger.debug(f"Skipping URL ending with slash (likely section page): {url}")
                        continue
                        
                    # Skip common non-article URL patterns
                    non_article_patterns = [
                        '/tag/', '/tags/', '/topic/', '/topics/', 
                        '/category/', '/categories/',
                        '/author/', '/authors/',
                        '/search/', '/video/', '/videos/',
                        '/live/', '/gallery/', '/galleries/',
                        '/section/', '/sections/',
                        '/login', '/subscribe', '/comments',
                    ]
                    
                    if any(pattern in url.lower() for pattern in non_article_patterns):
                        logger.debug(f"Skipping URL with non-article pattern: {url}")
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
                    
                    # Convert publish_date to datetime if available
                    if article['publish_date']:
                        article['publish_date'] = datetime.datetime.fromtimestamp(
                            time.mktime(article['publish_date']))
                    
                    articles.append(article)
                
                logger.info(f"Found {len(articles)} articles in feed: {feed_url}")
                break
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout while fetching RSS feed: {feed_url}")
            retry_count += 1
            if retry_count <= MAX_RETRIES:
                await asyncio.sleep(1)  # Brief pause before retry
            
        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {str(e)}")
            break
    
    return articles

def fallback_extract_with_requests(url: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Fallback extraction method using requests + trafilatura.
    
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
    
    try:
        logger.info(f"Using fallback extractor for: {url}")
        
        # Check if trafilatura is available
        if importlib.util.find_spec("trafilatura") is None:
            extraction_info['error'] = "Trafilatura module not found"
            return None, None, extraction_info
        
        import trafilatura
        from trafilatura.metadata import extract_metadata
        
        # Make request with timeout
        headers = {
            'User-Agent': USER_AGENT
        }
        
        response = requests.get(url, headers=headers, timeout=ARTICLE_TIMEOUT)
        if response.status_code != 200:
            extraction_info['error'] = f"HTTP error: {response.status_code}"
            return None, None, extraction_info
            
        html_content = response.text
        
        # Extract content with trafilatura
        extracted_text = trafilatura.extract(html_content, include_comments=False)
        extracted_html = trafilatura.extract(html_content, output_format='html')
        
        if not extracted_text:
            extraction_info['error'] = "No content extracted"
            return None, None, extraction_info
            
        # Extract metadata
        metadata = extract_metadata(html_content)
        
        # Prepare result
        extraction_info['title'] = metadata.title if metadata else ''
        extraction_info['author'] = metadata.author if metadata else ''
        extraction_info['date'] = metadata.date if metadata else ''
        extraction_info['success'] = True
        extraction_info['text_length'] = len(extracted_text)
        
        return extracted_text, extracted_html, extraction_info
        
    except Exception as e:
        logger.error(f"Error in fallback extraction for {url}: {str(e)}")
        extraction_info['error'] = str(e)
        return None, None, extraction_info

async def extract_article_content_async(url: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Extract article content using wget and trafilatura asynchronously.
    Falls back to requests+trafilatura if the primary method fails.
    
    Args:
        url: URL of the article
        
    Returns:
        Tuple of (text content, HTML content, extraction info)
    """
    # Primary extraction method
    extraction_info = {
        'extractor': 'wget+trafilatura',
        'success': False,
        'timestamp': datetime.datetime.now().isoformat(),
        'error': None
    }
    
    try:
        # Create a unique temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.html')
        os.close(temp_fd)  # Close the file descriptor
        
        try:
            # Use wget to download the article with a timeout
            wget_cmd = [
                'wget', 
                '--timeout=30',
                '--tries=2',
                '--quiet',
                '-O', temp_path,
                url
            ]
            
            # Run wget as a subprocess
            process = await asyncio.create_subprocess_exec(
                *wget_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), ARTICLE_TIMEOUT)
                
                if process.returncode != 0:
                    logger.warning(f"wget failed for {url}: {stderr.decode()}")
                    extraction_info['error'] = f"wget failed: {stderr.decode()}"
                    # Fall back to requests+trafilatura
                    return await run_in_executor(fallback_extract_with_requests, url)
                
                # Check if trafilatura is available as a Python module
                if importlib.util.find_spec("trafilatura") is not None:
                    try:
                        import trafilatura
                        from trafilatura.metadata import extract_metadata
                        
                        # Read the HTML file
                        with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                            html_content = f.read()
                        
                        # Extract the main content and metadata
                        extracted_text = trafilatura.extract(html_content, include_comments=False)
                        extracted_html = trafilatura.extract(html_content, output_format='html')
                        metadata = extract_metadata(html_content)
                        
                        if not extracted_text:
                            logger.warning(f"Trafilatura could not extract content from {url}")
                            extraction_info['error'] = "No content extracted"
                            # Fall back to requests+trafilatura
                            return await run_in_executor(fallback_extract_with_requests, url)
                        
                        # Prepare the result
                        extraction_info['title'] = metadata.title if metadata else ''
                        extraction_info['author'] = metadata.author if metadata else ''
                        extraction_info['date'] = metadata.date if metadata else ''
                        extraction_info['success'] = True
                        extraction_info['text_length'] = len(extracted_text)
                        
                        return extracted_text, extracted_html, extraction_info
                        
                    except Exception as e:
                        logger.error(f"Error using trafilatura module: {str(e)}")
                        extraction_info['error'] = f"Trafilatura module error: {str(e)}"
                        # Fall back to requests+trafilatura
                        return await run_in_executor(fallback_extract_with_requests, url)
                
                # Fallback: Use subprocess method with proper Python module call
                trafilatura_cmd = [
                    sys.executable,  # Use the current Python interpreter
                    '-m', 'trafilatura',  # Call as module
                    '--inputfile', temp_path,
                    '--json',
                    '--with-metadata'
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *trafilatura_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(process.communicate(), ARTICLE_TIMEOUT)
                
                if process.returncode != 0 or not stdout:
                    logger.warning(f"Trafilatura failed for {url}: {stderr.decode()}")
                    extraction_info['error'] = f"trafilatura failed: {stderr.decode()}"
                    # Fall back to requests+trafilatura
                    return await run_in_executor(fallback_extract_with_requests, url)
                
                try:
                    # Parse the JSON output
                    result = json.loads(stdout.decode())
                    text = result.get('text', '')
                    html = result.get('html', '')
                    
                    if not text:
                        logger.warning(f"No text extracted from {url}")
                        # Fall back to requests+trafilatura
                        return await run_in_executor(fallback_extract_with_requests, url)
                    
                    # Get additional metadata
                    extraction_info['title'] = result.get('title', '')
                    extraction_info['author'] = result.get('author', '')
                    extraction_info['date'] = result.get('date', '')
                    extraction_info['success'] = True
                    extraction_info['text_length'] = len(text)
                    
                    return text, html, extraction_info
                    
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse trafilatura JSON output for {url}")
                    extraction_info['error'] = "JSON parse error for trafilatura output"
                    # Fall back to requests+trafilatura
                    return await run_in_executor(fallback_extract_with_requests, url)
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout while extracting content from {url}")
                extraction_info['error'] = "Subprocess timeout"
                # Fall back to requests+trafilatura
                return await run_in_executor(fallback_extract_with_requests, url)
                
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {str(e)}")
        extraction_info['error'] = str(e)
        # Fall back to requests+trafilatura
        return await run_in_executor(fallback_extract_with_requests, url)

async def run_in_executor(func, *args):
    """Run a blocking function in an executor."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, func, *args)

async def process_article(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single article by extracting its content.
    
    Args:
        article_data: Dictionary with article metadata
        
    Returns:
        Updated article data with content
    """
    url = article_data['url']
    domain = get_domain(url)
    
    # Double-check the URL to ensure it's an article URL
    # This provides a second layer of filtering in case some non-articles slipped through
    if url.count('/') < 3:
        logger.warning(f"Skipping URL with insufficient path segments: {url}")
        article_data['text'] = None
        article_data['html'] = None
        article_data['extraction_info'] = {"error": "URL appears to be non-article (insufficient path segments)"}
        return article_data
        
    # Respect rate limits
    now = time.time()
    if domain in domain_last_request:
        elapsed = now - domain_last_request[domain]
        if elapsed < MIN_DELAY:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            logger.debug(f"Rate limiting {domain}, waiting {delay:.2f}s")
            await asyncio.sleep(delay)
    
    domain_last_request[domain] = time.time()
    
    logger.info(f"Processing article: {url}")
    text, html, extraction_info = await extract_article_content_async(url)
    
    # Update article data with extracted content
    article_data['text'] = text
    article_data['html'] = html
    article_data['extraction_info'] = extraction_info
    article_data['scraped_at'] = datetime.datetime.now()
    
    return article_data

async def fetch_feed_batch(
    session: aiohttp.ClientSession, 
    feed_configs: List[Dict[str, Any]]
) -> List[List[Dict[str, Any]]]:
    """
    Fetch a batch of RSS feeds in parallel.
    
    Args:
        session: aiohttp client session
        feed_configs: List of feed configuration dictionaries
        
    Returns:
        List of article lists from each feed
    """
    tasks = []
    for feed in feed_configs:
        tasks.append(fetch_rss_feed(session, feed['url'], feed['source_name']))
    
    # Fetch all feeds in parallel using asyncio.gather
    return await asyncio.gather(*tasks)

async def process_article_batch(articles_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process a batch of articles in parallel.
    
    Args:
        articles_batch: List of article data dictionaries
        
    Returns:
        List of processed articles
    """
    if not articles_batch:
        return []
        
    # Process all articles in the batch concurrently using asyncio.gather
    return await asyncio.gather(*[process_article(article) for article in articles_batch])

async def run_scraper(feed_configs: List[Dict[str, Any]], limit_per_feed: int = None) -> List[Dict[str, Any]]:
    """
    Run the two-stage scraper process.
    
    Args:
        feed_configs: List of feed configuration dictionaries
        limit_per_feed: Maximum number of articles to process per feed
        
    Returns:
        List of processed articles
    """
    # Use default limit from environment variable if not specified
    if limit_per_feed is None:
        limit_per_feed = DEFAULT_LIMIT_PER_FEED
    
    all_processed_articles = []
    
    # Process feeds in batches of BATCH_SIZE
    for i in range(0, len(feed_configs), BATCH_SIZE):
        batch_feeds = feed_configs[i:i+BATCH_SIZE]
        batch_size = len(batch_feeds)
        logger.info(f"Processing batch of {batch_size} feeds (batch {i//BATCH_SIZE + 1}/{(len(feed_configs) + BATCH_SIZE - 1)//BATCH_SIZE})")
        
        async with aiohttp.ClientSession() as session:
            # Stage 1: Fetch all RSS feeds in the batch in parallel
            feeds_articles = await fetch_feed_batch(session, batch_feeds)
            
            # Apply limit per feed if specified
            if limit_per_feed:
                feeds_articles = [feed_articles[:limit_per_feed] for feed_articles in feeds_articles]
            
            # Count total articles in this batch of feeds
            total_articles = sum(len(feed_articles) for feed_articles in feeds_articles)
            logger.info(f"Found {total_articles} articles across {len(feeds_articles)} feeds")
            
            # Find the maximum number of articles in any feed
            max_articles = max((len(feed_articles) for feed_articles in feeds_articles), default=0)
            
            # Stage 2: Process articles in parallel, one from each feed at a time
            for article_index in range(max_articles):
                # Collect one article from each feed that has enough articles
                current_batch = []
                
                for feed_articles in feeds_articles:
                    if article_index < len(feed_articles):
                        current_batch.append(feed_articles[article_index])
                
                if not current_batch:
                    break  # No more articles to process
                
                logger.info(f"Processing batch of {len(current_batch)} articles (one from each feed)")
                
                # Process all articles in current batch in parallel
                processed_batch = await process_article_batch(current_batch)
                
                # Filter out articles that failed to extract
                valid_articles = []
                skipped_articles = []
                
                # Check each article and provide detailed feedback
                for a in processed_batch:
                    if a.get('text'):
                        text_length = len(a.get('text', ''))
                        if text_length > 100:  # Only accept articles with meaningful content
                            valid_articles.append(a)
                            logger.info(f"Valid article: {a.get('title', '')[:40]}... ({text_length} chars)")
                        else:
                            skipped_articles.append(a)
                            logger.warning(f"Skipping article with short text ({text_length} chars): {a.get('title', '')[:40]}...")
                    else:
                        skipped_articles.append(a)
                        error = a.get('extraction_info', {}).get('error', 'Unknown error')
                        logger.warning(f"Failed to extract article: {a.get('url', 'unknown')} - {error}")
                
                if valid_articles:
                    all_processed_articles.extend(valid_articles)
                    logger.info(f"Successfully processed {len(valid_articles)} articles in this batch")
                    logger.info(f"Skipped {len(skipped_articles)} articles in this batch")
                else:
                    logger.warning(f"ALL {len(processed_batch)} ARTICLES SKIPPED in this batch!")
                
                # Brief pause between article batches
                await asyncio.sleep(2)
    
    return all_processed_articles

def scrape_feeds(feed_configs: List[Dict[str, Any]], limit_per_feed: int = None) -> List[Dict[str, Any]]:
    """
    Main entry point for the scraper.
    
    Args:
        feed_configs: List of feed configurations with 'url' and 'source_name'
        limit_per_feed: Maximum number of articles to process per feed
        
    Returns:
        List of processed articles
    """
    try:
        return asyncio.run(run_scraper(feed_configs, limit_per_feed))
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        return []
    except Exception as e:
        logger.error(f"Scraper error: {str(e)}")
        logger.error(traceback.format_exc())
        return []

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
    limit = DEFAULT_LIMIT_PER_FEED
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
    
    logger.info(f"Starting scraper with {len(feed_configs)} feeds (limit: {limit} articles per feed)")
    articles = scrape_feeds(feed_configs, limit_per_feed=limit)
    logger.info(f"Scraping completed. Processed {len(articles)} articles")