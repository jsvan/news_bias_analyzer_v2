#!/usr/bin/env python3
"""
Recovery script for OpenAI processed batches.

This script handles retrieving previously processed OpenAI batches and updating
existing articles that aren't marked as completed. It serves as a recovery mechanism
when the analyzer daemon fails.

Usage: ./run.sh restore_openai [options]
"""

import os
import sys
import logging
import argparse
import json
import time
import datetime
from pathlib import Path
import tempfile
import shutil
import openai
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("recover_openai")

# Add the parent directory to the path to import database modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention, NewsSource

def unix_to_datetime(ts):
    """Convert Unix timestamp to datetime.
    
    OpenAI API timestamps are in seconds as a float.
    This converts them to a datetime object in UTC time.
    """
    if isinstance(ts, str):
        # Try to parse string timestamp to float
        try:
            ts = float(ts)
        except ValueError:
            logger.warning(f"Could not convert timestamp string '{ts}' to float")
            # Return current time as fallback
            return datetime.datetime.now()
            
    # Fix for the deprecated utcfromtimestamp warning
    try:
        # Use timezone-aware approach if Python 3.11+
        if hasattr(datetime, 'UTC'):
            return datetime.datetime.fromtimestamp(ts, tz=datetime.UTC).replace(tzinfo=None)
        else:
            # Fallback for older Python versions
            return datetime.datetime.utcfromtimestamp(ts)
    except (ValueError, TypeError, OverflowError) as e:
        logger.error(f"Error converting timestamp {ts} (type: {type(ts)}): {e}")
        # Return current time as fallback
        return datetime.datetime.now()

def parse_article_id(custom_id):
    """Extract article_id from custom_id in batch request."""
    if custom_id.startswith('article_'):
        return custom_id[8:]  # Remove 'article_' prefix
    return custom_id

def extract_article_data(input_data):
    """Extract article title, content, source, and date from input request."""
    try:
        if 'body' in input_data and 'messages' in input_data['body']:
            messages = input_data['body']['messages']
            for message in messages:
                if message['role'] == 'user':
                    content = message['content']
                    
                    # Extract title
                    title_match = content.split('Title: ', 1)
                    if len(title_match) > 1:
                        title_line = title_match[1].split('\n', 1)[0]
                        title = title_line
                        source_name = None

                        # Extract content and look for source information
                        article_content = None

                        if '\n' in title_match[1]:
                            remaining = title_match[1].split('\n', 1)[1].strip()

                            # Check for Source: line (new format). When present it is
                            # authoritative — it must never be overridden by the
                            # "Title - Source" suffix heuristic below, which misreads
                            # headlines that merely contain " - " (that override once
                            # registered headline fragments as news sources).
                            if "Source: " in remaining:
                                source_parts = remaining.split("Source: ", 1)
                                if len(source_parts) > 1 and '\n' in source_parts[1]:
                                    source_line = source_parts[1].split('\n', 1)[0].strip()
                                    source_name = source_line
                                    # Get the rest as content
                                    article_content = source_parts[1].split('\n', 1)[1].strip()
                                else:
                                    article_content = remaining
                            # Check for Source ID: line
                            elif "Source ID: " in remaining:
                                source_id_parts = remaining.split("Source ID: ", 1)
                                source_id = None
                                if len(source_id_parts) > 1 and '\n' in source_id_parts[1]:
                                    source_id_line = source_id_parts[1].split('\n', 1)[0].strip()
                                    try:
                                        source_id = int(source_id_line)
                                    except ValueError:
                                        pass
                                    # Get the rest as content
                                    article_content = source_id_parts[1].split('\n', 1)[1].strip()
                                else:
                                    article_content = remaining
                            else:
                                article_content = remaining

                        if source_name is None and " - " in title_line:
                            # Old-format fallback (no Source: line): "Title - Source"
                            title_parts = title_line.rsplit(" - ", 1)
                            title = title_parts[0].strip()
                            source_name = title_parts[1].strip()

                        return {
                            "title": title,
                            "content": article_content,
                            "source_name": source_name,
                        }
    except Exception as e:
        logger.error(f"Error extracting article data: {e}")
    
    return {
        "title": None,
        "content": None,
        "source_name": None,
    }

def extract_entities(output_data):
    """Extract entities from OpenAI output response."""
    try:
        if 'response' in output_data and 'body' in output_data['response'] and 'choices' in output_data['response']['body']:
            # This is the format in batch_req_XXXX structure
            choices = output_data['response']['body']['choices']
            if choices and 'message' in choices[0] and 'content' in choices[0]['message']:
                content = choices[0]['message']['content']
                # Parse the JSON content
                entity_data = json.loads(content)
                if 'entities' in entity_data:
                    return entity_data['entities']
        elif 'body' in output_data and 'choices' in output_data['body']:
            # This is the format for direct API responses
            choices = output_data['body']['choices']
            if choices and 'message' in choices[0] and 'content' in choices[0]['message']:
                content = choices[0]['message']['content']
                # Parse the JSON content
                entity_data = json.loads(content)
                if 'entities' in entity_data:
                    return entity_data['entities']
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        logger.error(f"Output data structure: {json.dumps(output_data, indent=2)[:500]}...")
    return []

def check_existing_articles(db_manager, article_ids):
    """
    Check which articles exist in the database and their current status.
    
    Args:
        db_manager: Database manager instance
        article_ids: List of article IDs to check
    
    Returns:
        Dictionary mapping article IDs to their status
    """
    session = db_manager.get_session()
    try:
        existing_articles = {}
        for article in session.query(NewsArticle).filter(NewsArticle.id.in_(article_ids)).all():
            has_entities = session.query(EntityMention).filter_by(article_id=article.id).count() > 0
            existing_articles[article.id] = {
                'exists': True,
                'has_analysis': article.processed_at is not None and has_entities,
                'analysis_status': article.analysis_status,
                'processed_at': article.processed_at is not None,
                'url': article.url
            }
        
        # For articles not found, set default values
        for article_id in article_ids:
            if article_id not in existing_articles:
                existing_articles[article_id] = {
                    'exists': False,
                    'has_analysis': False,
                    'analysis_status': None,
                    'processed_at': False,
                    'url': None
                }
        
        return existing_articles
    finally:
        session.close()

def ensure_default_source(db_manager, source_id=1):
    """Ensure that a default news source with ID 1 exists."""
    session = db_manager.get_session()
    try:
        # Check if source with ID 1 exists
        source = session.query(NewsSource).filter_by(id=source_id).first()
        
        if not source:
            logger.info(f"Creating default news source with ID {source_id}")
            # Create default source with ID 1
            source = NewsSource(
                id=source_id,
                name="Default Source",
                base_url="https://default.example.com",
                country="Unknown",
                language="en"
            )
            session.add(source)
            session.commit()
            logger.info(f"Successfully created default news source with ID {source_id}")
            return True
        else:
            logger.info(f"Default news source with ID {source_id} already exists")
            return True
    except Exception as e:
        logger.error(f"Error ensuring default news source: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def resolve_source_id(db_manager, source_name, default_id=1):
    """Find or create a NewsSource by name; fall back to default_id."""
    if not source_name:
        return default_id
    session = db_manager.get_session()
    try:
        source = session.query(NewsSource).filter_by(name=source_name).first()
        if source:
            return source.id
        source = NewsSource(
            name=source_name,
            base_url=f"https://{source_name.lower().replace(' ', '')}.example.com",
            country="Unknown",
            language="en",
        )
        session.add(source)
        session.commit()
        logger.info(f"Created new source '{source_name}' (ID: {source.id})")
        return source.id
    except Exception as e:
        logger.error(f"Error resolving source '{source_name}': {e}")
        session.rollback()
        return default_id
    finally:
        session.close()

def update_or_create_article(db_manager, article_id, article_data, source_id=1, create_missing=False):
    """
    Update existing article or create a new one, handling incomplete articles.
    Only updates articles that are not already marked as 'completed' to avoid
    unnecessary processing.

    IMPORTANT: By default this function will ONLY update existing articles.
    With create_missing=True it also rebuilds missing rows from batch input data
    (disaster recovery after database loss). Rebuilt rows get the placeholder URL
    'restored_article_<id>' — the same convention remove_restored_articles.py
    targets — while keeping the original id (md5 of the real URL), so hash-based
    lookups still match.

    Args:
        db_manager: Database manager instance
        article_id: Article ID
        article_data: Dictionary with article data (title, content, etc.)
        source_id: Source ID for the article
        create_missing: If True, create article rows that don't exist

    Returns:
        Updated article object, or None if failed or article doesn't exist
    """
    title = article_data.get('title')
    content = article_data.get('content')
    source_name = article_data.get('source_name')
    
    # Get OpenAI analysis date, if available
    openai_date = None
    if 'original_openai_data' in article_data and 'created_at' in article_data['original_openai_data']:
        openai_timestamp = article_data['original_openai_data']['created_at']
        openai_date = unix_to_datetime(openai_timestamp)
    
    if not title or not content:
        logger.warning(f"Article {article_id} missing title or content, skipping")
        return None
    
    # Use dates in this priority order:
    # 1. OpenAI analysis date
    # 2. Current time as last resort
    if openai_date:
        publish_date = openai_date
        logger.info(f"Using OpenAI analysis date as publish date: {publish_date}")
    else:
        publish_date = datetime.datetime.now()
        logger.info(f"No date available, using current time: {publish_date}")
    
    # Default scrape time (use OpenAI date if available, otherwise current time minus 10 minutes)
    scrape_time = openai_date if openai_date else (datetime.datetime.now() - datetime.timedelta(minutes=10))
    
    session = db_manager.get_session()
    try:
        # Check if article exists
        article = session.query(NewsArticle).filter_by(id=article_id).first()
        
        if article:
            logger.info(f"Article {article_id} exists, checking if update needed")
            
            # Only update if article is not marked as completed
            needs_update = (
                article.analysis_status != "completed" or 
                not article.processed_at
            )
            
            if needs_update:
                logger.info(f"Updating article {article_id} - Current status: {article.analysis_status}")
                
                # Update basic info if missing
                if title and not article.title:
                    article.title = title
                # Note: We intentionally don't restore article text for completed articles
                # to save storage space. Text is cleared after successful analysis.
                    
                # Try to use source name from article data if available
                if source_name:
                    session2 = db_manager.get_session()
                    try:
                        # Look up source by name
                        source = session2.query(NewsSource).filter_by(name=source_name).first()
                        if source:
                            logger.info(f"Found source '{source_name}' (ID: {source.id}) from batch data")
                            article.source_id = source.id
                        else:
                            # Create new source
                            new_source = NewsSource(
                                name=source_name,
                                base_url=f"https://{source_name.lower().replace(' ', '')}.example.com",
                                country="Unknown",
                                language="en"
                            )
                            session2.add(new_source)
                            session2.commit()
                            logger.info(f"Created new source '{source_name}' (ID: {new_source.id}) from batch data")
                            article.source_id = new_source.id
                    except Exception as e:
                        logger.error(f"Error processing source '{source_name}': {e}")
                    finally:
                        session2.close()
                # Fallback to provided source_id
                elif source_id and (article.source_id is None or article.source_id == 1):
                    article.source_id = source_id
                    
                if not article.publish_date:
                    article.publish_date = publish_date
                
                # Always update processing status
                article.processed_at = datetime.datetime.now()
                article.analysis_status = "completed"
                article.batch_id = None  # Clear any previous batch ID
                
                session.commit()
                logger.info(f"Updated article {article_id} to completed status")
                return article
            else:
                logger.info(f"Article {article_id} is already completed, skipping update")
                return article
        elif create_missing:
            article = NewsArticle(
                id=article_id,  # md5 of the real URL, preserved via custom_id
                url=f"restored_article_{article_id}",  # real URL not present in batch data
                title=title,
                text=None,  # match analyzer behavior: text is cleared after analysis
                source_id=resolve_source_id(db_manager, source_name, source_id),
                publish_date=publish_date,
                scraped_at=scrape_time,
                processed_at=datetime.datetime.now(),
                analysis_status="completed",
            )
            session.add(article)
            session.commit()
            logger.info(f"Created restored article {article_id}")
            return article
        else:
            # CHANGE: We no longer create new articles, just log that it wasn't found
            logger.info(f"Article {article_id} not found in database, skipping")
            return None
    except Exception as e:
        logger.error(f"Error updating article {article_id}: {e}")
        session.rollback()
        return None
    finally:
        session.close()

def save_entities(db_manager, article_id, entities):
    """
    Save extracted entities to the database. Only saves entities if none exist
    for the article to avoid duplicate processing.
    
    Args:
        db_manager: Database manager instance
        article_id: Article ID
        entities: List of entity data to save
        
    Returns:
        True if successful, False otherwise
    """
    session = db_manager.get_session()
    try:
        # Check if entity mentions already exist
        existing_mentions = session.query(EntityMention).filter_by(article_id=article_id).count()
        
        if existing_mentions > 0:
            logger.info(f"Article {article_id} already has {existing_mentions} entity mentions, skipping")
            return True
        
        # Use service layer to process entities
        from database.services import DatabaseService
        
        db_service = DatabaseService(session)
        mention_count = 0
        
        try:
            # Process all entities for this article using the service
            entity_results = db_service.entities.process_article_entities(
                article_id=article_id,
                entity_data_list=entities
            )
            mention_count = len(entity_results)
            
        except ValueError as e:
            logger.warning(f"Error processing entities for article {article_id}: {e}")
            mention_count = 0
        
        session.commit()
        logger.info(f"Saved {mention_count} entity mentions for article {article_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving entities for article {article_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def process_batch_file(input_file, output_file, db_manager, stats, default_source_id=1,
                       create_missing=False, max_articles=None):
    """
    Process a single batch input/output file pair for recovery.
    Only updates EXISTING articles that don't have a completed status.
    Will never create new articles that don't already exist in the database.
    
    Args:
        input_file: Path to input JSONL file
        output_file: Path to output JSONL file
        db_manager: Database manager instance
        stats: Dictionary to track processing statistics
        default_source_id: Default source ID to use if not specified
        
    Returns:
        Updated stats dictionary
    """
    logger.info(f"Processing batch files for recovery:")
    logger.info(f"  Input: {input_file}")
    logger.info(f"  Output: {output_file}")
    
    # Load input data
    input_data = []
    with open(input_file, 'r') as f:
        for line in f:
            try:
                input_data.append(json.loads(line))
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in input file: {line[:100]}...")
    
    # Load output data
    output_data = []
    with open(output_file, 'r') as f:
        for line in f:
            try:
                output_data.append(json.loads(line))
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in output file: {line[:100]}...")
    
    # Match input and output by custom_id
    matched_data = {}
    for input_item in input_data:
        custom_id = input_item.get('custom_id')
        if custom_id:
            matched_data[custom_id] = {'input': input_item}
    
    for output_item in output_data:
        custom_id = output_item.get('custom_id')
        if custom_id and custom_id in matched_data:
            matched_data[custom_id]['output'] = output_item
    
    # Extract article IDs
    article_ids = []
    for custom_id in matched_data.keys():
        article_id = parse_article_id(custom_id)
        article_ids.append(article_id)
    
    # Check which articles already exist in the database and their status
    existing_articles = check_existing_articles(db_manager, article_ids)
    
    # Process each article
    recovered_count = 0
    total_processed = 0
    already_complete = 0
    not_found = 0
    
    for custom_id, data in matched_data.items():
        if 'input' not in data or 'output' not in data:
            logger.warning(f"Incomplete data for {custom_id}")
            stats['incomplete'] += 1
            continue
        
        article_id = parse_article_id(custom_id)
        article_status = existing_articles.get(article_id, {'exists': False, 'has_analysis': False})
        
        # Skip if article doesn't exist in database (unless we're rebuilding)
        if not article_status['exists']:
            if not create_missing:
                logger.info(f"Article {article_id} does not exist in database, skipping")
                stats['skipped'] += 1
                not_found += 1
                continue
            if max_articles is not None and stats['created'] >= max_articles:
                logger.info(f"Article {article_id} missing but --max-articles cap reached, skipping")
                stats['skipped'] += 1
                continue
        
        # Skip if article is already completed
        if (article_status['has_analysis'] and 
            article_status['analysis_status'] == 'completed'):
            logger.info(f"Article {article_id} already has completed analysis, skipping")
            stats['skipped'] += 1
            already_complete += 1
            continue
        
        # Extract data
        article_data = extract_article_data(data['input'])
        raw_entities = extract_entities(data['output'])
        
        # Filter out entities with empty names or types
        entities = []
        for entity in raw_entities:
            if not entity.get('entity') or not entity.get('entity_type'):
                logger.warning(f"Skipping entity with empty name or type: {entity}")
                continue
            entities.append(entity)
        
        # Add OpenAI timestamp if available
        try:
            # The timestamp could be in different places depending on the response format
            created_at = None
            
            # Try to find the timestamp in the output data
            if 'created_at' in data['output']:
                created_at = data['output']['created_at']
            elif 'response' in data['output'] and 'created_at' in data['output']['response']:
                created_at = data['output']['response']['created_at']
            elif 'response' in data['output'] and 'body' in data['output']['response'] and 'created_at' in data['output']['response']['body']:
                created_at = data['output']['response']['body']['created_at']
            elif 'response' in data['output'] and 'body' in data['output']['response'] and 'created' in data['output']['response']['body']:
                # chat completion bodies use 'created', not 'created_at'
                created_at = data['output']['response']['body']['created']
                
            if created_at:
                article_data['original_openai_data'] = {'created_at': created_at}
                logger.info(f"Found OpenAI timestamp: {created_at}")
        except Exception as e:
            logger.warning(f"Error extracting OpenAI timestamp: {e}")
        
        title_display = article_data.get('title', '')[:50] + ('...' if len(article_data.get('title', '')) > 50 else '')
        logger.info(f"Processing article ID: {article_id}, Title: {title_display}")
        
        # Update existing article (creates missing rows only with create_missing)
        article = update_or_create_article(
            db_manager,
            article_id,
            article_data,
            default_source_id,
            create_missing=create_missing
        )

        if not article:
            logger.error(f"Failed to update article {article_id}")
            stats['errors'] += 1
            continue

        total_processed += 1
        if not article_status['exists']:
            stats['created'] += 1
        
        # Was this a recovery? (existing article with incomplete status)
        if not article_status['processed_at'] or article_status['analysis_status'] != 'completed':
            recovered_count += 1
        
        # Save entities
        if entities:
            success = save_entities(db_manager, article_id, entities)
            if success:
                logger.info(f"Saved {len(entities)} entities for article {article_id}")
                stats['processed'] += 1
            else:
                logger.error(f"Failed to save entities for article {article_id}")
                stats['errors'] += 1
        else:
            logger.warning(f"No entities found for article {article_id}")
            stats['processed'] += 1
    
    # Update recovery stats
    stats['recovered'] = recovered_count
    stats['total_processed'] = total_processed
    stats['already_complete'] = already_complete
    stats['not_found'] = not_found
    
    return stats

def download_file_with_retry(file_id, dest_path, max_retries=6):
    """Download an OpenAI file, backing off on 429s (files API: 300 req/min).

    Returns True on success. A 404 (file purged by OpenAI retention) or other
    hard error returns False immediately — only rate limits are retried.
    """
    for attempt in range(max_retries):
        try:
            stream = openai.files.content(file_id)
            with open(dest_path, "wb") as f:
                f.write(stream.read())
            return True
        except openai.RateLimitError:
            wait = min(60, 5 * (2 ** attempt))
            logger.warning(f"Rate limited downloading {file_id}; sleeping {wait}s")
            time.sleep(wait)
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return False
    logger.error(f"Rate limit retries exhausted for {file_id}")
    return False

def download_openai_batches(output_dir, year=2025, limit=None, date=None, after_date=None, args=None):
    """
    Download OpenAI batch files for the specified year and date filters.
    
    Args:
        output_dir: Directory to save batch files
        year: Year to filter batches (default: 2025)
        limit: Maximum number of batches to download
        date: Specific date to filter (format: YYYY-MM-DD)
        after_date: Download batches after this date (format: YYYY-MM-DD)
        
    Returns:
        List of downloaded batch information
    """
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        logger.info("Available environment variables: " + ", ".join(sorted(os.environ.keys())))
        return []
    
    # Mask the API key for logging (show first 4 chars)
    masked_key = api_key[:4] + "*" * (len(api_key) - 4) if api_key else None
    logger.info(f"Using OpenAI API key starting with: {masked_key[:4]}...")
    
    openai.api_key = api_key
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Define date range for the specified year
    start_year = datetime.datetime(year, 1, 1)
    end_year = datetime.datetime(year + 1, 1, 1)
    
    logger.info(f"Downloading OpenAI batches for {year}...")
    
    # Get all batches
    batches = []
    try:
        response = openai.batches.list(limit=100)
        batches.extend(response.data)
        
        while response.has_more:
            response = openai.batches.list(limit=100, after=response.data[-1].id)
            batches.extend(response.data)
    except Exception as e:
        logger.error(f"Error fetching batches: {e}")
        return []
    
    logger.info(f"Found {len(batches)} total batches")
    
    # Filter batches by year, date and status
    filtered_batches = []
    
    # Parse date filters if provided
    specific_date = None
    next_day = None
    date_after = None
    
    if date:
        try:
            specific_date = datetime.datetime.strptime(date, '%Y-%m-%d')
            next_day = specific_date + datetime.timedelta(days=1)
            logger.info(f"Filtering batches for specific date: {specific_date.strftime('%Y-%m-%d')}")
        except ValueError as e:
            logger.error(f"Invalid date format: {date}. Please use YYYY-MM-DD format.")
            logger.error(f"Error: {e}")
            return []
        
    if after_date:
        try:
            date_after = datetime.datetime.strptime(after_date, '%Y-%m-%d')
            logger.info(f"Filtering batches after date: {date_after.strftime('%Y-%m-%d')}")
        except ValueError as e:
            logger.error(f"Invalid after_date format: {after_date}. Please use YYYY-MM-DD format.")
            logger.error(f"Error: {e}")
            return []
    
    # Debug data for sample batches
    if len(batches) > 0:
        sample_batch = batches[0]
        logger.info(f"Sample batch data structure:")
        logger.info(f"  ID: {sample_batch.id}")
        logger.info(f"  Status: {sample_batch.status}")
        logger.info(f"  Created at: {sample_batch.created_at}")
        logger.info(f"  Timestamp type: {type(sample_batch.created_at)}")
        logger.info(f"  Created datetime: {unix_to_datetime(sample_batch.created_at)}")
    
    # Apply filters
    for batch in batches:
        # Skip non-completed batches
        if batch.status != "completed":
            continue
            
        # Convert timestamp to datetime
        created_at_dt = unix_to_datetime(batch.created_at)
        batch_date = created_at_dt.date()
        
        # Debug log for batches
        if specific_date or ('today_filter' in locals() and today_filter):
            logger.info(f"Checking batch {batch.id}: created={created_at_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            if specific_date:
                logger.info(f"  Looking for date: {specific_date.strftime('%Y-%m-%d')}")
            
        # Special handling for today filter (accounts for timezone differences)
        if hasattr(args, 'today_filter') and args.today_filter:
            # Convert dates to proper objects
            today_local_date = datetime.datetime.strptime(args.today_local, '%Y-%m-%d').date()
            tomorrow_local_date = datetime.datetime.strptime(args.tomorrow_local, '%Y-%m-%d').date()
            
            # Check if batch date is either today or early hours of tomorrow in UTC
            # (which might still be "today" in local time)
            if batch_date == today_local_date or batch_date == tomorrow_local_date:
                logger.info(f"  ✓ Today match: {batch_date} is within today's range")
                filtered_batches.append(batch)
                continue
            else:
                logger.info(f"  Skipping batch {batch.id}: {batch_date} is not today or early tomorrow in UTC")
                continue
        
        # Filter by year (if not overridden by specific date or after_date)
        if not specific_date and not date_after and not (start_year <= created_at_dt < end_year):
            continue
            
        # Filter by specific date if provided
        if specific_date:
            # Compare just the date parts (year, month, day)
            target_date = specific_date.date()
            
            if batch_date != target_date:
                logger.info(f"  Skipping batch {batch.id}: {batch_date} != {target_date}")
                continue
            else:
                logger.info(f"  ✓ Date match: {batch_date} == {target_date}")
            
        # Filter by after_date if provided
        if date_after and created_at_dt < date_after:
            continue
            
        # If we get here, the batch passed all filters
        batch_time = created_at_dt
        logger.info(f"✓ Batch {batch.id} from {batch_time.strftime('%Y-%m-%d %H:%M:%S')} passed all filters")
        filtered_batches.append(batch)
    
    logger.info(f"Found {len(filtered_batches)} completed batches matching filters")
    
    # Apply limit if specified
    if limit and len(filtered_batches) > limit:
        filtered_batches = filtered_batches[:limit]
        logger.info(f"Limited to {limit} batches")
    
    # Download batch files
    downloaded_batches = []
    for batch in filtered_batches:
        batch_id = batch.id
        created_str = unix_to_datetime(batch.created_at).strftime("%Y-%m-%d %H:%M:%S UTC")
        input_file_id = batch.input_file_id
        output_file_id = batch.output_file_id
        
        logger.info(f"\nProcessing Batch ID: {batch_id}")
        logger.info(f"Uploaded on: {created_str}")
        
        # Skip if both files already exist
        input_path = output_path / f"{batch_id}_input.jsonl"
        output_path_file = output_path / f"{batch_id}_output.jsonl"
        
        if input_path.exists() and output_path_file.exists():
            logger.info(f"Batch {batch_id} already downloaded, skipping")
            downloaded_batches.append({
                'batch_id': batch_id,
                'input_file': str(input_path),
                'output_file': str(output_path_file)
            })
            continue
        
        # Pace requests: 2 file downloads per batch against a 300 req/min cap.
        time.sleep(0.5)

        # Download input file
        if input_file_id:
            if download_file_with_retry(input_file_id, input_path):
                logger.info(f"Downloaded input file to {input_path}")
            else:
                continue
        else:
            logger.warning("No input file found.")
            continue

        # Download output file
        if output_file_id:
            if download_file_with_retry(output_file_id, output_path_file):
                logger.info(f"Downloaded output file to {output_path_file}")
            else:
                continue
        else:
            logger.warning("No output file found.")
            continue
        
        downloaded_batches.append({
            'batch_id': batch_id,
            'input_file': str(input_path),
            'output_file': str(output_path_file)
        })
    
    logger.info(f"\nDownloaded {len(downloaded_batches)} successful batches")
    return downloaded_batches

def recover_openai_batches(args):
    """
    Main function to recover OpenAI batches and update incomplete articles.
    Only updates EXISTING articles that are not already marked as 'completed'.
    Will NEVER create new articles that don't already exist in the database.
    
    Args:
        args: Command-line arguments
    """
    # Log key parameters being used
    logger.info("Starting batch recovery with parameters:")
    logger.info(f"  Date filter: {args.date or 'None'}")
    logger.info(f"  After date filter: {args.after_date or 'None'}")
    logger.info(f"  Year filter: {args.year}")
    logger.info(f"  Batch limit: {args.limit or 'No limit'}")
    logger.info(f"  Skip download: {args.skip_download}")
    logger.info(f"  Dry run: {args.dry_run}")
    
    # Print an important notice about the recovery behavior
    if getattr(args, 'create_missing', False):
        logger.info("\n===== RESTORE MODE (--create-missing) =====")
        logger.info("Missing articles will be REBUILT from batch input data.")
        logger.info("Rebuilt rows use placeholder URLs 'restored_article_<id>'.")
        logger.info("Undo with: ./run.sh custom analyzer/tools/remove_restored_articles.py")
        if getattr(args, 'max_articles', None):
            logger.info(f"Capped at {args.max_articles} created articles.")
        logger.info("===========================================\n")
    else:
        logger.info("\n===== IMPORTANT NOTICE =====")
        logger.info("This tool will ONLY update EXISTING articles in the database.")
        logger.info("It will NEVER create new articles or use placeholder URLs.")
        logger.info("Articles not found in the database will be skipped.")
        logger.info("=============================\n")
    
    # Initialize database manager
    db_manager = DatabaseManager()
    
    # Ensure default source exists
    ensure_default_source(db_manager, args.source_id)
    
    # Setup temporary directory if needed
    temp_dir = None
    if args.batch_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="openai_recovery_")
        batch_dir = temp_dir
        logger.info(f"Created temporary directory: {batch_dir}")
    else:
        batch_dir = args.batch_dir
        Path(batch_dir).mkdir(exist_ok=True)
    
    try:
        batches = []
        
        # Download batches if not skipped
        if not args.skip_download:
            # Set API key in environment if provided
            if args.api_key:
                os.environ["OPENAI_API_KEY"] = args.api_key
            
            # Download batches
            if "OPENAI_API_KEY" in os.environ:
                batches = download_openai_batches(
                    batch_dir, 
                    args.year, 
                    args.limit,
                    args.date,
                    args.after_date,
                    args
                )
            else:
                logger.error("OPENAI_API_KEY not set, cannot download batches")
                return
        
        # Find existing batch files if skip_download or no batches were downloaded
        if args.skip_download or not batches:
            logger.info(f"Looking for existing batch files in {batch_dir}")
            input_files = list(Path(batch_dir).glob('*_input.jsonl'))
            
            for input_file in input_files:
                batch_id = input_file.stem.split('_input')[0]
                output_file = input_file.parent / f"{batch_id}_output.jsonl"
                
                if output_file.exists():
                    batches.append({
                        'batch_id': batch_id,
                        'input_file': str(input_file),
                        'output_file': str(output_file)
                    })
            
            logger.info(f"Found {len(batches)} existing batch file pairs")
        
        if args.dry_run:
            logger.info("Dry run mode - not modifying database")
            return
        
        # Process each batch
        stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'incomplete': 0,
            'recovered': 0,
            'total_processed': 0,
            'already_complete': 0,
            'not_found': 0,
            'created': 0
        }

        create_missing = getattr(args, 'create_missing', False)
        max_articles = getattr(args, 'max_articles', None)

        if not batches:
            logger.warning("No batch files to process")
        else:
            for batch in batches:
                if create_missing and max_articles is not None and stats['created'] >= max_articles:
                    logger.info(f"--max-articles cap ({max_articles}) reached, stopping")
                    break
                process_batch_file(
                    batch['input_file'],
                    batch['output_file'],
                    db_manager,
                    stats,
                    args.source_id,
                    create_missing=create_missing,
                    max_articles=max_articles
                )
        
        # Print summary
        logger.info("\n--- Recovery Summary ---")
        logger.info(f"Total batches processed: {len(batches)}")
        logger.info(f"Articles created (restored from batch data): {stats['created']}")
        logger.info(f"Articles recovered (incomplete → complete): {stats['recovered']}")
        logger.info(f"Total articles processed: {stats['total_processed']}")
        logger.info(f"Articles already complete: {stats['already_complete']}")
        logger.info(f"Articles not found in database: {stats.get('not_found', 0)}")
        logger.info(f"Articles skipped: {stats['skipped']}")
        logger.info(f"Errors encountered: {stats['errors']}")
        logger.info(f"Incomplete data entries: {stats['incomplete']}")
    
    finally:
        # Clean up temporary directory if created
        if temp_dir and not args.keep_files:
            logger.info(f"Removing temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)

def main():
    parser = argparse.ArgumentParser(description='Recover OpenAI processed batches and update incomplete articles')
    parser.add_argument('--batch-dir', type=str, default=None,
                        help='Directory for batch files (default: temporary directory)')
    parser.add_argument('--year', type=int, default=2025,
                        help='Year to filter batches (default: 2025)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of batches to process')
    parser.add_argument('--source-id', type=int, default=1,
                        help='Default news source ID for new articles (default: 1)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Download batches but don\'t modify the database')
    parser.add_argument('--keep-files', action='store_true',
                        help='Keep downloaded batch files (only relevant if using temp directory)')
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip downloading batches, just process existing files in batch-dir')
    parser.add_argument('--api-key', type=str, default=None,
                        help='OpenAI API key (if not set in environment)')
    parser.add_argument('--date', type=str, default=None,
                        help='Only process batches from this date (format: YYYY-MM-DD)')
    parser.add_argument('--after-date', type=str, default=None,
                        help='Only process batches after this date (format: YYYY-MM-DD)')
    parser.add_argument('--today', action='store_true',
                        help='Only process batches from today (auto-adjusts for timezone differences)')
    parser.add_argument('--create-missing', action='store_true',
                        help='Rebuild articles that no longer exist in the database from batch input data '
                             '(disaster recovery). Rebuilt rows get placeholder URLs restored_article_<id>.')
    parser.add_argument('--max-articles', type=int, default=None,
                        help='With --create-missing: stop after creating this many articles (for sample runs)')
    
    args = parser.parse_args()
    
    # Handle --today flag
    if args.today:
        # Get today's date and tomorrow's date to account for timezone differences
        # This allows matching batches that are created today in any timezone
        today_date = datetime.datetime.now().strftime('%Y-%m-%d')
        tomorrow_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info(f"Using today's date: {today_date} and considering timezone differences")
        logger.info(f"Will include batches from today ({today_date}) and early hours of tomorrow ({tomorrow_date}) UTC")
        
        # Use after_date instead of specific date to catch batches that appear as tomorrow in UTC
        args.after_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        # Set a custom filter for today's batches
        args.today_filter = True
        args.today_local = today_date
        args.tomorrow_local = tomorrow_date
        
    recover_openai_batches(args)

if __name__ == "__main__":
    main()