#!/usr/bin/env python3
"""
Comprehensive script to download OpenAI batch data and restore missing articles.
This script combines downloading, checking, and restoring in one operation.

Usage:
./run.sh custom database/hard_openai_extraction/restore_openai_data.py
"""

import os
import sys
import logging
import argparse
import json
import datetime
from pathlib import Path
import tempfile
import shutil
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")
    print(f"Environment variables loaded: {list(os.environ.keys())}")
    print(f"OPENAI_API_KEY exists: {'OPENAI_API_KEY' in os.environ}")
    if 'OPENAI_API_KEY' in os.environ:
        key = os.environ['OPENAI_API_KEY']
        print(f"API key length: {len(key)}, First 4 chars: {key[:4]}" if key else "API key is empty")

# Add the parent directory to the path to import database modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention, NewsSource
from database.hard_openai_extraction.source_detector import SourceDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for OpenAI package
try:
    import openai
except ImportError:
    logger.error("OpenAI package not installed. Install with: pip install openai")
    sys.exit(1)

def parse_article_id(custom_id):
    """Extract article_id from custom_id in batch request."""
    if custom_id.startswith('article_'):
        return custom_id[8:]  # Remove 'article_' prefix
    return custom_id

def unix_to_datetime(ts):
    """Convert Unix timestamp to datetime."""
    return datetime.datetime.utcfromtimestamp(ts)

def extract_date_from_text(text):
    """Try to extract date from text using various formats."""
    import re
    from datetime import datetime
    
    date_patterns = [
        # Common date formats
        r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',                   # DD/MM/YYYY or MM/DD/YYYY
        r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',                     # YYYY/MM/DD
        r'([A-Z][a-z]{2,8} \d{1,2},? \d{4})',                 # Month DD, YYYY
        r'(\d{1,2} [A-Z][a-z]{2,8},? \d{4})',                 # DD Month YYYY
        r'(\d{1,2}(?:st|nd|rd|th) [A-Z][a-z]{2,8},? \d{4})',  # DDth Month YYYY
        
        # Published/Updated date strings
        r'(?:Published|Updated|Posted):? (?:on )?([A-Z][a-z]{2,8} \d{1,2},? \d{4})',
        r'(?:Published|Updated|Posted):? (?:on )?(\d{1,2} [A-Z][a-z]{2,8},? \d{4})',
        r'(?:Published|Updated|Posted):? (?:on )?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
    ]
    
    date_formats = [
        '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%d-%m-%Y',
        '%Y/%m/%d', '%Y-%m-%d',
        '%B %d, %Y', '%B %d %Y',
        '%d %B, %Y', '%d %B %Y',
        '%dst %B, %Y', '%dnd %B, %Y', '%drd %B, %Y', '%dth %B, %Y',
        '%dst %B %Y', '%dnd %B %Y', '%drd %B %Y', '%dth %B %Y',
    ]
    
    # First look for explicit date indicators
    for pattern in date_patterns:
        matches = re.search(pattern, text)
        if matches:
            date_str = matches.group(1)
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
    
    # Default to current date if no date is found
    return datetime.now()

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
                        
                        # Check if title contains source information
                        source_name = None
                        if " - " in title_line:
                            # Format might be "Title - Source"
                            title_parts = title_line.rsplit(" - ", 1)
                            if len(title_parts) > 1:
                                title = title_parts[0].strip()
                                source_name = title_parts[1].strip()
                            else:
                                title = title_line
                        else:
                            title = title_line
                        
                        # Extract content
                        article_content = None
                        if len(title_match) > 1 and '\n' in title_match[1]:
                            article_content = title_match[1].split('\n', 1)[1].strip()
                        
                        # Try to extract date from content
                        publish_date = None
                        if article_content:
                            # Look for a date in the first 500 characters
                            date_text = article_content[:500]
                            publish_date = extract_date_from_text(date_text)
                        
                        return {
                            "title": title,
                            "content": article_content,
                            "source_name": source_name,
                            "publish_date": publish_date
                        }
    except Exception as e:
        logger.error(f"Error extracting article data: {e}")
    
    return {
        "title": None,
        "content": None,
        "source_name": None,
        "publish_date": None
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
    """Check which articles exist in the database."""
    session = db_manager.get_session()
    try:
        existing_articles = {}
        for article in session.query(NewsArticle).filter(NewsArticle.id.in_(article_ids)).all():
            has_entities = session.query(EntityMention).filter_by(article_id=article.id).count() > 0
            existing_articles[article.id] = {
                'exists': True,
                'has_analysis': article.processed_at is not None and has_entities
            }
        
        # For articles not found, set default values
        for article_id in article_ids:
            if article_id not in existing_articles:
                existing_articles[article_id] = {
                    'exists': False,
                    'has_analysis': False
                }
        
        return existing_articles
    finally:
        session.close()

def get_or_create_source(session, source_name):
    """Get or create a news source by name."""
    if not source_name:
        # Default to a generic source if no name provided
        source_name = "Unknown Source"
    
    # Try to find existing source
    source = session.query(NewsSource).filter_by(name=source_name).first()
    
    if not source:
        logger.info(f"Creating new source: {source_name}")
        # Create new source if it doesn't exist
        source = NewsSource(
            name=source_name,
            base_url=f"https://{source_name.lower().replace(' ', '')}.example.com",  # Placeholder URL
            country="Unknown",
            language="en"
        )
        session.add(source)
        session.flush()  # Get the ID before commit
    
    return source

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

def update_or_create_article(db_manager, article_id, article_data, default_source_id=1, source_detector=None):
    """Update existing article or create a new one if it doesn't exist."""
    title = article_data.get('title')
    content = article_data.get('content')
    source_name = article_data.get('source_name')
    publish_date = article_data.get('publish_date')
    
    # Get OpenAI analysis date, if available
    openai_date = None
    if 'original_openai_data' in article_data and 'created_at' in article_data['original_openai_data']:
        openai_timestamp = article_data['original_openai_data']['created_at']
        openai_date = unix_to_datetime(openai_timestamp)
    
    if not title or not content:
        logger.warning(f"Article {article_id} missing title or content, skipping")
        return None
    
    # Use dates in this priority order:
    # 1. Extracted publish date from article content
    # 2. OpenAI analysis date
    # 3. Current time as last resort
    if not publish_date:
        if openai_date:
            publish_date = openai_date
            logger.info(f"Using OpenAI analysis date as publish date: {publish_date}")
        else:
            publish_date = datetime.datetime.now()
            logger.info(f"No date available, using current time: {publish_date}")
    
    # Default scrape time (use OpenAI date if available, otherwise a bit before processing time)
    scrape_time = openai_date if openai_date else (datetime.datetime.now() - datetime.timedelta(minutes=10))
    
    # Use source detector if available
    source_id = default_source_id
    if source_detector:
        try:
            # Prepare article data for source detection
            detect_data = {
                'id': article_id,
                'title': title,
                'text': content,
                'source_name': source_name,
                'url': f"restored_article_{article_id}"
            }
            source_id = source_detector.detect_source(detect_data)
            logger.info(f"Source detector identified source ID {source_id} for article {article_id}")
        except Exception as e:
            logger.error(f"Error detecting source for article {article_id}: {e}")
            # Fall back to default source ID
            source_id = default_source_id
    else:
        # Legacy method if source detector not available
        session = db_manager.get_session()
        try:
            if source_name:
                source = get_or_create_source(session, source_name)
                source_id = source.id
            session.close()
        except Exception as e:
            logger.error(f"Error getting source for {source_name}: {e}")
            session.close()
    
    session = db_manager.get_session()
    try:
        # Check if article exists
        article = session.query(NewsArticle).filter_by(id=article_id).first()
        
        if article:
            logger.info(f"Article {article_id} exists, updating data")
            if title and not article.title:
                article.title = title
            if content and not article.text:
                article.text = content
            # Update source only if it's not already set or it's the default
            if source_id and (article.source_id is None or article.source_id == default_source_id):
                article.source_id = source_id
            # Update publish date if not already set
            if publish_date and not article.publish_date:
                article.publish_date = publish_date
            # Mark as processed if not already processed
            if not article.processed_at:
                article.processed_at = datetime.datetime.now()
                article.analysis_status = "completed"
            session.commit()
            return article
        else:
            # Create a new article record
            logger.info(f"Creating new article record for {article_id}")
            
            new_article = NewsArticle(
                id=article_id,
                title=title,
                text=content,
                source_id=source_id,
                url=f"restored_article_{article_id}",  # Placeholder URL
                publish_date=publish_date,
                scraped_at=scrape_time,
                processed_at=datetime.datetime.now(),
                analysis_status="completed"
            )
            session.add(new_article)
            session.commit()
            return new_article
    except Exception as e:
        logger.error(f"Error updating/creating article {article_id}: {e}")
        session.rollback()
        return None
    finally:
        session.close()

def save_entities(db_manager, article_id, entities):
    """Save extracted entities to the database."""
    session = db_manager.get_session()
    try:
        for entity_info in entities:
            entity_name = entity_info.get('entity', '')
            entity_type = entity_info.get('entity_type', '')
            power_score = entity_info.get('power_score', 0)
            moral_score = entity_info.get('moral_score', 0)
            mentions = entity_info.get('mentions', [])
            
            # Get or create entity
            entity = session.query(Entity).filter_by(
                name=entity_name,
                entity_type=entity_type
            ).first()
            
            if not entity:
                entity = Entity(
                    name=entity_name,
                    entity_type=entity_type
                )
                session.add(entity)
                session.flush()
            
            # Check if entity mention exists
            existing_mention = session.query(EntityMention).filter_by(
                entity_id=entity.id,
                article_id=article_id
            ).first()
            
            # Skip if mention already exists
            if existing_mention:
                logger.info(f"Entity mention already exists for {entity_name} in article {article_id}")
                continue
            
            # Create entity mention
            mention = EntityMention(
                entity_id=entity.id,
                article_id=article_id,
                power_score=power_score,
                moral_score=moral_score,
                mentions=mentions
            )
            session.add(mention)
        
        session.commit()
        logger.info(f"Saved {len(entities)} entities for article {article_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving entities for article {article_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def download_openai_batches(output_dir, year=2025, limit=None):
    """Download OpenAI batch files for the specified year."""
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
    
    # Filter batches by year and status
    filtered_batches = []
    for batch in batches:
        created_at_dt = unix_to_datetime(batch.created_at)
        if (batch.status == "completed" and 
            start_year <= created_at_dt < end_year):
            filtered_batches.append(batch)
    
    logger.info(f"Found {len(filtered_batches)} completed batches from {year}")
    
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
        
        # Download input file
        if input_file_id:
            try:
                input_stream = openai.files.content(input_file_id)
                with open(input_path, "wb") as f:
                    f.write(input_stream.read())
                logger.info(f"Downloaded input file to {input_path}")
            except Exception as e:
                logger.error(f"Error downloading input file: {e}")
                continue
        else:
            logger.warning("No input file found.")
            continue
        
        # Download output file
        if output_file_id:
            try:
                output_stream = openai.files.content(output_file_id)
                with open(output_path_file, "wb") as f:
                    f.write(output_stream.read())
                logger.info(f"Downloaded output file to {output_path_file}")
            except Exception as e:
                logger.error(f"Error downloading output file: {e}")
                continue
        else:
            logger.warning("No output file found.")
            continue
        
        downloaded_batches.append({
            'batch_id': batch_id,
            'input_file': str(input_path),
            'output_file': str(output_path_file)
        })
    
    logger.info(f"\nDownloaded {len(downloaded_batches)} successful batches from {year}")
    return downloaded_batches

def process_batch_file(input_file, output_file, db_manager, stats, default_source_id=1, source_detector=None, web_search_limit=10, parallel_workers=5):
    """Process a single batch input/output file pair."""
    logger.info(f"Processing batch files:")
    logger.info(f"  Input: {input_file}")
    logger.info(f"  Output: {output_file}")
    logger.info(f"  Source Detection: {'Enabled' if source_detector else 'Disabled'}")
    
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
    
    # Check which articles already exist in the database
    existing_articles = check_existing_articles(db_manager, article_ids)
    
    # Prepare batched source detection
    articles_for_detection = []
    
    # Process each article
    for custom_id, data in matched_data.items():
        if 'input' not in data or 'output' not in data:
            logger.warning(f"Incomplete data for {custom_id}")
            stats['incomplete'] += 1
            continue
        
        article_id = parse_article_id(custom_id)
        article_status = existing_articles.get(article_id, {'exists': False, 'has_analysis': False})
        
        # Skip if article exists and has analysis
        if article_status['exists'] and article_status['has_analysis']:
            logger.info(f"Article {article_id} already exists with analysis, skipping")
            stats['skipped'] += 1
            continue
        
        # Extract data
        article_data = extract_article_data(data['input'])
        entities = extract_entities(data['output'])
        
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
                
            if created_at:
                article_data['original_openai_data'] = {'created_at': created_at}
                logger.info(f"Found OpenAI timestamp: {created_at}")
        except Exception as e:
            logger.warning(f"Error extracting OpenAI timestamp: {e}")
        
        logger.info(f"Processing article ID: {article_id}, Title: {article_data['title']}, Source: {article_data['source_name'] or 'Unknown'}")
        logger.info(f"Found {len(entities)} entities")
        
        # Flag for source detection - we'll do it in batches 
        article_data['id'] = article_id  # Make sure ID is included
        
        # Add to the list for batch source detection
        if source_detector:
            articles_for_detection.append(article_data)
        
        # Create or update article without source detection for now
        # We'll set the source ID later with batch detection
        article = update_or_create_article(db_manager, article_id, article_data, default_source_id, None)
        if not article:
            logger.error(f"Failed to create/update article {article_id}")
            stats['errors'] += 1
            continue
        
        # Always save entities regardless of whether the article is new or existing
        # This ensures we don't miss any entity analysis
        if entities:
            # First check if article already has entities
            session = db_manager.get_session()
            try:
                existing_entities = session.query(EntityMention).filter_by(article_id=article_id).count()
                session.close()
                
                if existing_entities > 0:
                    logger.info(f"Article {article_id} already has {existing_entities} entity mentions, skipping")
                    stats['processed'] += 1
                else:
                    # Save entities
                    success = save_entities(db_manager, article_id, entities)
                    if success:
                        logger.info(f"Saved {len(entities)} entities for article {article_id}")
                        stats['processed'] += 1
                    else:
                        logger.error(f"Failed to save entities for article {article_id}")
                        stats['errors'] += 1
            except Exception as e:
                logger.error(f"Error checking existing entities: {e}")
                stats['errors'] += 1
        else:
            logger.warning(f"No entities found for article {article_id}")
            stats['processed'] += 1
    
    # Perform batch source detection if we have articles and a source detector
    if articles_for_detection and source_detector:
        logger.info(f"Performing batch source detection for {len(articles_for_detection)} articles")
        source_results = source_detector.process_batch(
            articles_for_detection, 
            max_workers=parallel_workers,
            web_search_limit=web_search_limit
        )
        
        # Update articles with detected sources
        if source_results:
            logger.info(f"Updating articles with detected sources")
            session = db_manager.get_session()
            try:
                update_count = 0
                for article_id, source_id in source_results.items():
                    # Only update if source is different from default
                    if source_id != default_source_id:
                        article = session.query(NewsArticle).filter_by(id=article_id).first()
                        if article:
                            article.source_id = source_id
                            update_count += 1
                
                if update_count > 0:
                    session.commit()
                    logger.info(f"Updated {update_count} articles with new source IDs")
            except Exception as e:
                logger.error(f"Error updating article sources: {e}")
                session.rollback()
            finally:
                session.close()
    
    return stats

def main():
    parser = argparse.ArgumentParser(description='Download and restore OpenAI batch data')
    parser.add_argument('--batch-dir', type=str, default=None,
                        help='Directory for batch files (default: temporary directory)')
    parser.add_argument('--input-file', type=str, default=None,
                        help='Process a specific input file without downloading')
    parser.add_argument('--output-file', type=str, default=None,
                        help='Process a specific output file without downloading')
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
    parser.add_argument('--disable-source-detection', action='store_true',
                        help='Disable automatic source detection')
    parser.add_argument('--parallel-workers', type=int, default=5,
                        help='Number of parallel workers for source detection (default: 5)')
    parser.add_argument('--web-search-limit', type=int, default=10,
                        help='Limit the number of web searches performed in a batch (default: 10)')
    parser.add_argument('--disable-web-search', action='store_true',
                        help='Disable web search for source detection (use only pattern matching)')
    parser.add_argument('--cache-size', type=int, default=1000,
                        help='Maximum size of source detection cache (default: 1000)')
    
    args = parser.parse_args()
    
    # Create database manager
    db_manager = DatabaseManager()
    
    # Initialize source detector
    source_detector = None
    if not args.disable_source_detection:
        logger.info("Initializing source detector...")
        try:
            source_detector = SourceDetector(
                db_manager, 
                enable_web_search=not args.disable_web_search,
                cache_size=args.cache_size
            )
            logger.info(f"Source detector initialized with {len(source_detector.known_sources)} known sources")
            logger.info(f"Web search {'enabled' if not args.disable_web_search else 'disabled'}")
            logger.info(f"Cache size: {args.cache_size}")
            logger.info(f"Web search batch limit: {args.web_search_limit}")
        except Exception as e:
            logger.error(f"Error initializing source detector: {e}")
            logger.warning("Continuing without source detection")
    
    # Ensure default source exists before processing any articles
    if not args.dry_run:
        logger.info("Ensuring default news source exists...")
        if not ensure_default_source(db_manager, args.source_id):
            logger.error(f"Failed to create default news source with ID {args.source_id}. Exiting.")
            return
    
    # Process specific input/output files if provided
    if args.input_file and args.output_file:
        logger.info("Processing specific input/output files")
        stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'incomplete': 0
        }
        
        if not args.dry_run:
            process_batch_file(
                args.input_file, 
                args.output_file, 
                db_manager, 
                stats, 
                args.source_id, 
                source_detector,
                args.web_search_limit,
                args.parallel_workers
            )
        else:
            logger.info("Dry run mode - not modifying database")
        
        logger.info("\n--- Summary ---")
        logger.info(f"Articles processed: {stats['processed']}")
        logger.info(f"Articles skipped (already exist): {stats['skipped']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"Incomplete data: {stats['incomplete']}")
        return
    
    # Create a temporary directory if no batch dir specified
    temp_dir = None
    if args.batch_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="openai_batches_")
        batch_dir = temp_dir
        logger.info(f"Created temporary directory: {batch_dir}")
    else:
        batch_dir = args.batch_dir
        
        # Ensure batch directory exists
        Path(batch_dir).mkdir(exist_ok=True)
        
        # If skip_download, check if there are existing files in the directory
        if args.skip_download:
            input_files = list(Path(batch_dir).glob('*_input.jsonl'))
            if input_files:
                logger.info(f"Found {len(input_files)} existing input files in {batch_dir}")
            else:
                logger.warning(f"No input files found in {batch_dir}, but --skip-download was specified")
    
    try:
        batches = []
        
        # Download batches unless skipped
        if not args.skip_download:
            # Get API key from args or environment
            api_key = args.api_key or os.getenv("OPENAI_API_KEY")
            
            # Set API key in environment if provided via args
            if args.api_key:
                os.environ["OPENAI_API_KEY"] = args.api_key
                logger.info("Using API key provided via command line argument")
            
            if not api_key:
                logger.error("OPENAI_API_KEY not set (neither in environment nor via --api-key), cannot download batches")
                if not args.batch_dir:
                    logger.error("No batch directory specified, exiting")
                    return
                logger.info("Continuing with existing files in batch directory")
            else:
                # Download batches
                batches = download_openai_batches(batch_dir, args.year, args.limit)
        
        # If skip_download, find existing batch files
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
            'incomplete': 0
        }
        
        if not batches:
            logger.warning("No batch files to process")
        else:
            for batch in batches:
                process_batch_file(
                    batch['input_file'],
                    batch['output_file'],
                    db_manager,
                    stats,
                    args.source_id,
                    source_detector,
                    args.web_search_limit,
                    args.parallel_workers
                )
        
        # Print summary
        logger.info("\n--- Summary ---")
        logger.info(f"Total batches processed: {len(batches)}")
        logger.info(f"Articles processed: {stats['processed']}")
        logger.info(f"Articles skipped (already exist): {stats['skipped']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"Incomplete data: {stats['incomplete']}")
    
    finally:
        # Clean up temporary directory if created
        if temp_dir and not args.keep_files:
            logger.info(f"Removing temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()