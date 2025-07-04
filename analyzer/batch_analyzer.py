#!/usr/bin/env python3
"""
Batch analyzer for news articles using OpenAI's Batch API.

This module handles:
1. Creating batches of unanalyzed articles (100 at a time)
2. Uploading batches to OpenAI's Batch API (max 5 active batches)
3. Tracking batch status in batches.txt
4. Polling for batch completion
5. Processing completed batches
6. Handling failed or cancelled batches
"""

import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import signal
import fcntl
from typing import List, Dict, Any, Tuple, Optional

import openai
from openai import OpenAI
import sqlalchemy
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.models import NewsArticle, Entity, EntityMention, NewsSource
from database.services import DatabaseService
from database.config import AnalysisConfig, LoggingConfig
from analyzer.prompts import ENTITY_SENTIMENT_PROMPT
from analyzer.hotelling_t2 import HotellingT2Calculator

# Setup directories
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH_DIR = os.path.join(ROOT_DIR, "batches")
if not os.path.exists(BATCH_DIR):
    os.makedirs(BATCH_DIR)

# Setup logging
LOG_DIR = os.path.join(ROOT_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "batch_analysis.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("batch_analyzer")

# Global variables
BATCHES_FILE = os.path.join(ROOT_DIR, "analyzer", "batches.txt")
MAX_ACTIVE_BATCHES = 4  # Reduced from 5 to avoid overwhelming OpenAI
BATCH_SIZE = 50  # Reduced from 100 to 50 for better manageability
POLL_INTERVAL_SECONDS = 300  # 5 minutes
LOCK_FILE = os.path.join(ROOT_DIR, "analyzer", "analyzer.lock")

# Status tracking
active_batches = []

def acquire_lock() -> Optional[int]:
    """Acquire a file lock to ensure only one instance runs at a time."""
    try:
        lock_file = open(LOCK_FILE, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except IOError:
        return None

def release_lock(lock_file):
    """Release the file lock."""
    if lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

def setup_database() -> Session:
    """Set up database connection and return session."""
    # Use environment variable for database URL
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL environment variable must be set")
    
    logger.info(f"Connecting to database: {db_url}")
    
    # Create engine
    engine = create_engine(db_url)
    
    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    return session

def read_batches_file() -> List[Dict[str, Any]]:
    """Read active batches from batches.txt file."""
    if not os.path.exists(BATCHES_FILE):
        return []
    
    try:
        with open(BATCHES_FILE, 'r') as f:
            batches = [json.loads(line) for line in f if line.strip()]
            return batches
    except Exception as e:
        logger.error(f"Error reading batches file: {e}")
        return []

def write_batches_file(batches: List[Dict[str, Any]]):
    """Write active batches to batches.txt file."""
    try:
        with open(BATCHES_FILE, 'w') as f:
            for batch in batches:
                f.write(json.dumps(batch) + '\n')
    except Exception as e:
        logger.error(f"Error writing batches file: {e}")

def count_active_batches() -> int:
    """Count the number of active batches."""
    batches = read_batches_file()
    return len(batches)

def get_unanalyzed_articles(session: Session, limit: int = BATCH_SIZE) -> List[NewsArticle]:
    """Get a batch of unanalyzed articles."""
    try:
        articles = session.query(NewsArticle).filter(
            NewsArticle.analysis_status == "unanalyzed",
            NewsArticle.text != None,
            NewsArticle.text != ""
        ).limit(limit).all()
        
        return articles
    except Exception as e:
        logger.error(f"Error getting unanalyzed articles: {e}")
        return []

def prepare_batch_input(articles: List[NewsArticle], model: str) -> Tuple[str, Dict[str, NewsArticle]]:
    """Prepare batch input file content and article lookup mapping."""
    batch_lines = []
    article_lookup = {}  # Maps custom_id to article
    
    for i, article in enumerate(articles):
        custom_id = f"article_{article.id}"
        article_lookup[custom_id] = article
        
        # Prepare article text
        title = article.title or "Untitled Article"
        text = article.text or ""
        
        # Include source information if available
        source_info = ""
        if hasattr(article, 'source') and article.source is not None:
            source_info = f"Source: {article.source.name}\n"
        elif article.source_id is not None:
            source_info = f"Source ID: {article.source_id}\n"
        
        # Truncate text if too long (15000 chars should be safe)
        analysis_text = f"Title: {title}\n{source_info}\n{text[:15000]}"
        
        # Create batch request line
        batch_line = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": [
                    {"role": "system", "content": ENTITY_SENTIMENT_PROMPT},
                    {"role": "user", "content": analysis_text}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
        }
        
        batch_lines.append(json.dumps(batch_line))
    
    # Join lines with newlines
    batch_content = "\n".join(batch_lines)
    return batch_content, article_lookup

def create_batch_file(batch_content: str, filename: str = None) -> str:
    """Create a batch input file and return its path."""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_{timestamp}.jsonl"
    
    file_path = os.path.join(BATCH_DIR, filename)
    
    try:
        with open(file_path, 'w') as f:
            f.write(batch_content)
        logger.info(f"Created batch file: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error creating batch file: {e}")
        return None

def upload_batch_file(client: OpenAI, file_path: str) -> str:
    """Upload batch file to OpenAI and return file ID."""
    try:
        with open(file_path, 'rb') as f:
            response = client.files.create(
                file=f,
                purpose="batch"
            )
        
        logger.info(f"Uploaded batch file: {file_path}, file ID: {response.id}")
        return response.id
    except Exception as e:
        logger.error(f"Error uploading batch file: {e}")
        return None

def create_openai_batch(client: OpenAI, file_id: str) -> str:
    """Create a batch in OpenAI and return batch ID."""
    try:
        batch = client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        
        logger.info(f"Created OpenAI batch: {batch.id}")
        return batch.id
    except Exception as e:
        logger.error(f"Error creating OpenAI batch: {e}")
        return None

def update_articles_status(session: Session, articles: List[NewsArticle], status: str, batch_id: str = None):
    """Update the status of a list of articles."""
    try:
        for article in articles:
            article.analysis_status = status
            article.batch_id = batch_id
            article.last_analysis_attempt = datetime.now()
        
        session.commit()
        logger.info(f"Updated {len(articles)} articles to status: {status}")
    except Exception as e:
        logger.error(f"Error updating article status: {e}")
        session.rollback()

def check_batch_status(client: OpenAI, batch_id: str) -> Dict[str, Any]:
    """Check the status of a batch."""
    try:
        batch = client.batches.retrieve(batch_id)
        return {
            "id": batch.id,
            "status": batch.status,
            "created_at": batch.created_at,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id,
            "request_counts": batch.request_counts,
        }
    except Exception as e:
        logger.error(f"Error checking batch status: {e}")
        return None

def download_batch_output(client: OpenAI, file_id: str) -> str:
    """Download batch output file and return content."""
    try:
        response = client.files.content(file_id)
        content = response.text
        logger.info(f"Downloaded batch output: {len(content)} bytes")
        return content
    except Exception as e:
        logger.error(f"Error downloading batch output: {e}")
        return None

def sanitize_numeric_value(value):
    """
    Sanitize a value that should be numeric by removing any non-numeric characters,
    except for the decimal point and negative sign.
    
    Args:
        value: The value to sanitize
        
    Returns:
        float: The sanitized value as a float, or 0.0 if conversion fails
    """
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        # Remove any non-numeric characters except decimal point and negative sign
        # This handles cases like ": 0.5" or "score: 1.2" etc.
        import re
        cleaned = re.sub(r'[^0-9\.\-]', '', value)
        
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert '{value}' to float after cleaning to '{cleaned}'")
            return 0.0
    
    return 0.0

def process_batch_output(session: Session, output_content: str, article_lookup: Dict[str, NewsArticle], batch_info: Dict[str, Any], batch_id: str = "unknown"):
    """Process batch output and update database."""
    # Parse output file (one JSONL line per result)
    results = [json.loads(line) for line in output_content.splitlines() if line.strip()]
    
    processed_count = 0
    error_count = 0
    processed_article_ids = []  # Keep track of processed article IDs for verification
    failed_article_ids = []     # Keep track of failed article IDs for resetting
    
    # Count completed articles before processing
    before_count = session.query(NewsArticle).filter(
        NewsArticle.analysis_status == "completed"
    ).count()
    logger.info(f"Before processing: {before_count} articles with 'completed' status")
    
    for result in results:
        custom_id = result.get("custom_id")
        if not custom_id or custom_id not in article_lookup:
            logger.warning(f"Unknown custom_id in batch results: {custom_id}")
            continue
        
        article = article_lookup[custom_id]
        
        # Skip this article if it no longer exists in the database
        # This handles cases where articles were deleted after the batch was created
        try:
            # Check if article still exists by refreshing it from the database
            session.refresh(article)
        except Exception as e:
            logger.warning(f"Article with ID {article.id} no longer exists in the database. Skipping.")
            continue
        
        # Check for errors
        if result.get("error"):
            logger.error(f"Error processing article {article.id}: {result['error']}")
            article.analysis_status = "failed"
            error_count += 1
            failed_article_ids.append(article.id)
            continue
        
        # Process successful result
        response = result.get("response", {})
        status_code = response.get("status_code")
        
        if status_code != 200:
            logger.error(f"Error status for article {article.id}: {status_code}")
            article.analysis_status = "failed"
            error_count += 1
            failed_article_ids.append(article.id)
            continue
        
        # Extract response data
        response_body = response.get("body", {})
        if not response_body:
            logger.error(f"Empty response body for article {article.id}")
            article.analysis_status = "failed"
            error_count += 1
            failed_article_ids.append(article.id)
            continue
        
        try:
            # Extract content from response
            content = json.dumps(response_body)
            analyzed_data = json.loads(content)
            
            # Extract choices/message/content which contains the actual analysis
            choices = analyzed_data.get("choices", [])
            if not choices:
                logger.error(f"No choices in response for article {article.id}")
                article.analysis_status = "failed"
                error_count += 1
                failed_article_ids.append(article.id)
                continue
            
            message = choices[0].get("message", {})
            content = message.get("content", "")
            
            # Parse the content as JSON
            try:
                analysis_result = json.loads(content)
                
                # Process entities using service layer
                db_service = DatabaseService(session)
                article_entities = []
                
                if 'entities' in analysis_result and analysis_result['entities']:
                    try:
                        # Process all entities for this article
                        entity_results = db_service.entities.process_article_entities(
                            article_id=article.id,
                            entity_data_list=analysis_result['entities'],
                            article_date=article.publish_date or article.scraped_at
                        )
                        
                        # Collect data for T² calculation
                        article_entities = [
                            {
                                'entity_id': entity.id,
                                'power_score': mention.power_score,
                                'moral_score': mention.moral_score
                            }
                            for entity, mention in entity_results
                        ]
                        
                    except ValueError as e:
                        logger.warning(f"Error processing entities for article {article.id}: {e}")
                
                # Calculate Hotelling's T² score if we have entities
                t2_score = None
                if article_entities:
                    try:
                        t2_calculator = HotellingT2Calculator(session)
                        t2_score = t2_calculator.calculate_article_t2(article_entities)
                        if t2_score:
                            logger.debug(f"Article {article.id} T² score: {t2_score:.2f}")
                    except Exception as e:
                        logger.warning(f"Failed to calculate T² score for article {article.id}: {e}")
                
                # Update article status using service
                success = db_service.articles.mark_article_completed(
                    article_id=article.id,
                    processed_at=datetime.now(),
                    hotelling_t2_score=t2_score
                )
                
                if not success:
                    logger.error(f"Failed to mark article {article.id} as completed")
                    continue
                
                # Clear article text to save storage space if configured
                if AnalysisConfig.CLEAR_TEXT_AFTER_ANALYSIS:
                    db_service.articles.clear_article_text(article.id)
                
                processed_count += 1
                processed_article_ids.append(article.id)
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing analysis result for article {article.id}: {e}")
                article.analysis_status = "failed"
                error_count += 1
                failed_article_ids.append(article.id)
                
        except Exception as e:
            logger.error(f"Error processing article {article.id}: {e}")
            article.analysis_status = "failed"
            error_count += 1
            failed_article_ids.append(article.id)
    
    # Commit changes
    try:
        session.commit()
        
        # Verify changes were committed successfully
        after_count = session.query(NewsArticle).filter(
            NewsArticle.analysis_status == "completed"
        ).count()
        
        # Calculate expected difference
        expected_diff = processed_count
        actual_diff = after_count - before_count
        
        # Verify and report
        if actual_diff == expected_diff:
            logger.info(f"✅ Verification successful: {actual_diff} new articles marked as completed (expected {expected_diff})")
            
            # Clean up batch files
            cleanup_successful = cleanup_batch_files(batch_info, batch_id)
            if cleanup_successful:
                logger.info(f"🧹 Cleaned up batch files successfully")
            else:
                logger.warning(f"⚠️ Failed to clean up some batch files")
                
        else:
            logger.error(f"❌ Verification failed: {actual_diff} new articles marked as completed (expected {expected_diff})")
            
            # Detailed check on each article
            for article_id in processed_article_ids:
                article = session.query(NewsArticle).get(article_id)
                if article and article.analysis_status == "completed":
                    logger.debug(f"Article {article_id} successfully marked as completed")
                else:
                    logger.error(f"Article {article_id} failed to update status to completed")
        
        logger.info(f"Processed batch: {processed_count} articles processed, {error_count} errors")
        logger.info(f"Total completed articles: {after_count} (was {before_count} before)")
        logger.info(f"💾 Cleared text from {processed_count} articles to save storage space")
        
        # Reset failed articles back to unanalyzed so they can be attempted again in future batches
        if failed_article_ids:
            reset_failed_articles_by_ids(session, failed_article_ids)
        
    except Exception as e:
        logger.error(f"Error committing batch results: {e}")
        session.rollback()
        
    return processed_count, error_count

def cleanup_batch_files(batch_info: Dict[str, Any], batch_id: str = "unknown") -> bool:
    """
    Clean up batch files after successful processing.
    
    Args:
        batch_info: Information about the batch
        batch_id: The ID of the batch being processed
        
    Returns:
        True if all files were cleaned up successfully, False otherwise
    """
    try:
        all_successful = True
        
        # Log the batch info to help debug
        logger.info(f"Cleaning up batch files for batch {batch_id} with info: {batch_info}")
        
        # Delete the batch input file
        batch_file = batch_info.get('batch_file')
        if batch_file:
            batch_path = os.path.join(BATCH_DIR, batch_file)
            if os.path.exists(batch_path):
                os.remove(batch_path)
                logger.info(f"🧹 Removed batch file: {batch_path}")
            else:
                logger.warning(f"⚠️ Batch file not found: {batch_path}")
                all_successful = False
        else:
            logger.warning(f"⚠️ Batch filename not found in batch info for {batch_id}")
            all_successful = False
        
        # Delete the article lookup file
        lookup_file = batch_info.get('article_lookup_file')
        if lookup_file:
            lookup_path = os.path.join(BATCH_DIR, lookup_file)
            if os.path.exists(lookup_path):
                os.remove(lookup_path)
                logger.info(f"🧹 Removed article lookup file: {lookup_path}")
            else:
                logger.warning(f"⚠️ Article lookup file not found: {lookup_path}")
                all_successful = False
        else:
            logger.warning(f"⚠️ Article lookup filename not found in batch info for {batch_id}")
            all_successful = False
        
        return all_successful
    except Exception as e:
        logger.error(f"Error cleaning up batch files: {e}")
        return False

def reset_failed_articles(session: Session, batch_id: str):
    """Reset articles that failed processing in a specific batch back to unanalyzed."""
    try:
        articles = session.query(NewsArticle).filter(
            NewsArticle.batch_id == batch_id,
            NewsArticle.analysis_status.in_(["in_progress", "failed"])
        ).all()
        
        for article in articles:
            article.analysis_status = "unanalyzed"
            article.batch_id = None
        
        session.commit()
        logger.info(f"Reset {len(articles)} failed articles back to unanalyzed")
    except Exception as e:
        logger.error(f"Error resetting failed articles: {e}")
        session.rollback()

def reset_failed_articles_by_ids(session: Session, article_ids: List[str]):
    """Reset specific failed articles back to unanalyzed status by ID."""
    if not article_ids:
        return
    
    try:
        count = 0
        for article_id in article_ids:
            article = session.query(NewsArticle).get(article_id)
            if article and article.analysis_status == "failed":
                article.analysis_status = "unanalyzed"
                article.batch_id = None
                count += 1
        
        if count > 0:
            session.commit()
            logger.info(f"Reset {count} failed articles back to unanalyzed for reprocessing")
    except Exception as e:
        logger.error(f"Error resetting failed articles by IDs: {e}")
        session.rollback()

def remove_batch_from_tracking(batch_id: str):
    """Remove a batch from the tracking file."""
    batches = read_batches_file()
    batches = [b for b in batches if b.get('id') != batch_id]
    write_batches_file(batches)
    logger.info(f"Removed batch {batch_id} from tracking")

def create_new_batch(session: Session) -> bool:
    """
    Create a new batch if under the maximum active batches.
    
    Returns:
        True if a new batch was created, False otherwise
    """
    # Check how many active batches we have
    active_count = count_active_batches()
    
    if active_count >= MAX_ACTIVE_BATCHES:
        logger.info(f"Maximum active batches ({MAX_ACTIVE_BATCHES}) reached. Cannot create new batch.")
        return False
    
    # Add delay between batch submissions to avoid overwhelming OpenAI
    logger.info("Adding 10-second delay before submitting new batch...")
    time.sleep(10)
    
    # Initialize OpenAI client
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not found in environment variables")
            return False
        
        client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized")
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {e}")
        return False
    
    # Get OpenAI model from environment or default to gpt-4.1-nano
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-nano")
    logger.info(f"Using OpenAI model: {model}")
    
    # Get unanalyzed articles
    articles = get_unanalyzed_articles(session)
    
    if not articles:
        logger.info("No unanalyzed articles found.")
        return False
    
    # Check minimum batch size
    if len(articles) < 50:
        logger.info(f"Only {len(articles)} unanalyzed articles found. Minimum batch size is 50. Skipping batch creation.")
        return False
    
    logger.info(f"Found {len(articles)} unanalyzed articles for new batch")
    
    # Prepare batch input
    batch_content, article_lookup = prepare_batch_input(articles, model)
    
    # Create batch file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_filename = f"batch_{timestamp}.jsonl"
    batch_file_path = create_batch_file(batch_content, batch_filename)
    
    if not batch_file_path:
        logger.error("Failed to create batch file")
        return False
    
    # Upload batch file to OpenAI
    file_id = upload_batch_file(client, batch_file_path)
    
    if not file_id:
        logger.error("Failed to upload batch file")
        return False
    
    # Create OpenAI batch
    batch_id = create_openai_batch(client, file_id)
    
    if not batch_id:
        logger.error("Failed to create OpenAI batch")
        return False
    
    # Update article status
    update_articles_status(session, articles, "in_progress", batch_id)
    
    # Add batch to tracking
    batch_info = {
        "id": batch_id,
        "file_id": file_id,
        "created_at": datetime.now().isoformat(),
        "batch_file": batch_filename,
        "article_count": len(articles),
        "status": "validating",
        "article_lookup_file": f"{batch_filename}.articles.json",
    }
    
    batches = read_batches_file()
    batches.append(batch_info)
    write_batches_file(batches)
    
    # Save article lookup for future reference
    lookup_file = os.path.join(BATCH_DIR, f"{batch_filename}.articles.json")
    with open(lookup_file, 'w') as f:
        article_map = {k: v.id for k, v in article_lookup.items()}
        json.dump(article_map, f)
    
    logger.info(f"Created new batch: {batch_id}")
    return True

def check_active_batches(session: Session):
    """Check status of active batches and process completed ones."""
    batches = read_batches_file()
    
    if not batches:
        logger.info("No active batches to check")
        return
    
    # Initialize OpenAI client
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not found in environment variables")
            return
        
        client = OpenAI(api_key=api_key)
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {e}")
        return
    
    updated_batches = []
    
    for batch in batches:
        batch_id = batch.get('id')
        
        if not batch_id:
            logger.warning(f"Batch missing ID: {batch}")
            continue
        
        # Check batch status
        batch_status = check_batch_status(client, batch_id)
        
        if not batch_status:
            logger.error(f"Failed to get status for batch {batch_id}")
            updated_batches.append(batch)  # Keep in list for now
            continue
        
        # Update batch info
        batch['status'] = batch_status['status']
        
        if batch_status['status'] in ['completed', 'finalizing']:
            logger.info(f"Batch {batch_id} is complete. Processing output...")
            
            # Get output file ID
            output_file_id = batch_status.get('output_file_id')
            
            if output_file_id:
                # Download output
                output_content = download_batch_output(client, output_file_id)
                
                if output_content:
                    # Load article lookup
                    lookup_file = os.path.join(BATCH_DIR, batch.get('article_lookup_file'))
                    
                    try:
                        with open(lookup_file, 'r') as f:
                            article_map = json.load(f)
                            
                        # Convert article IDs to article objects
                        article_lookup = {}
                        for custom_id, article_id in article_map.items():
                            # Check if article still exists in the database
                            article = session.query(NewsArticle).get(article_id)
                            if article:
                                article_lookup[custom_id] = article
                            else:
                                logger.warning(f"Article with ID {article_id} no longer exists in the database. Skipping.")
                        
                        # Process output
                        processed_count, error_count = process_batch_output(session, output_content, article_lookup, batch, batch_id)
                        
                        logger.info(f"Processed batch {batch_id}: {processed_count} articles, {error_count} errors")
                        
                        # Cleanup is already handled inside process_batch_output()
                        # Don't keep batch in active list
                        continue
                    except Exception as e:
                        logger.error(f"Error processing batch {batch_id}: {e}")
                else:
                    logger.error(f"Failed to download output for batch {batch_id}")
            else:
                logger.warning(f"No output file ID for completed batch {batch_id}")
        
        elif batch_status['status'] in ['failed', 'cancelled', 'expired']:
            logger.warning(f"Batch {batch_id} has failed or been cancelled. Resetting articles...")
            
            # Reset articles back to unanalyzed
            reset_failed_articles(session, batch_id)
            
            # Clean up batch files
            cleanup_successful = cleanup_batch_files(batch, batch_id)
            if cleanup_successful:
                logger.info(f"🧹 Cleaned up batch files for failed batch {batch_id}")
            else:
                logger.warning(f"⚠️ Failed to clean up some batch files for failed batch {batch_id}")
            
            # Don't keep batch in active list
            continue
        
        # Keep batch in the updated list if not complete/failed
        updated_batches.append(batch)
    
    # Write updated batches file
    write_batches_file(updated_batches)
    
    # Create new batches if we're under the limit
    current_count = len(updated_batches)
    slots_available = MAX_ACTIVE_BATCHES - current_count
    
    if slots_available > 0:
        logger.info(f"{slots_available} batch slots available. Creating new batches...")
        
        for _ in range(slots_available):
            create_new_batch(session)

def reset_in_progress_articles(session: Session):
    """Reset all in_progress articles back to unanalyzed on startup."""
    try:
        # Find all articles with in_progress status
        in_progress_articles = session.query(NewsArticle).filter(
            NewsArticle.analysis_status == "in_progress"
        ).all()
        
        count = len(in_progress_articles)
        if count > 0:
            logger.info(f"Found {count} articles stuck in 'in_progress' status")
            
            # Reset them to unanalyzed
            for article in in_progress_articles:
                article.analysis_status = "unanalyzed"
                article.batch_id = None
            
            session.commit()
            logger.info(f"Reset {count} in_progress articles back to unanalyzed")
        else:
            logger.info("No in_progress articles found")
            
    except Exception as e:
        logger.error(f"Error resetting in_progress articles: {e}")
        session.rollback()

def clear_batches_directory():
    """Clear all files from the batches directory on startup."""
    try:
        if not os.path.exists(BATCH_DIR):
            os.makedirs(BATCH_DIR)
            logger.info("Created batches directory")
            return
            
        # Count files before deletion
        files = os.listdir(BATCH_DIR)
        file_count = len(files)
        
        if file_count > 0:
            logger.info(f"Clearing {file_count} files from batches directory...")
            
            # Delete all files in the directory
            for filename in files:
                file_path = os.path.join(BATCH_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logger.debug(f"Deleted: {filename}")
                except Exception as e:
                    logger.error(f"Error deleting {filename}: {e}")
            
            logger.info("Batches directory cleared")
        else:
            logger.info("Batches directory is already empty")
            
    except Exception as e:
        logger.error(f"Error clearing batches directory: {e}")

def cleanup_old_batch_files():
    """
    Cleanup old batch files that might have been left behind.
    Keeps a record of which files were deleted.
    """
    try:
        logger.info("Cleaning up old batch files...")
        
        # Check if batch directory exists
        if not os.path.exists(BATCH_DIR):
            logger.warning(f"Batch directory does not exist: {BATCH_DIR}")
            return
        
        # Get all .jsonl files in the batch directory
        jsonl_files = [f for f in os.listdir(BATCH_DIR) if f.endswith('.jsonl')]
        articles_files = [f for f in os.listdir(BATCH_DIR) if f.endswith('.articles.json')]
        
        # Current tracked batches
        batches = read_batches_file()
        tracked_files = set()
        
        for batch in batches:
            if 'batch_file' in batch:
                tracked_files.add(batch['batch_file'])
            if 'article_lookup_file' in batch:
                tracked_files.add(batch['article_lookup_file'])
        
        # Find files not tracked in batches.txt
        untracked_jsonl = [f for f in jsonl_files if f not in tracked_files]
        untracked_articles = [f for f in articles_files if f not in tracked_files]
        
        # Delete untracked files
        deleted_files = []
        
        for f in untracked_jsonl:
            file_path = os.path.join(BATCH_DIR, f)
            try:
                os.remove(file_path)
                deleted_files.append(file_path)
                logger.debug(f"Deleted untracked batch file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")
        
        for f in untracked_articles:
            file_path = os.path.join(BATCH_DIR, f)
            try:
                os.remove(file_path)
                deleted_files.append(file_path)
                logger.debug(f"Deleted untracked articles file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")
        
        # Log summary
        if deleted_files:
            logger.info(f"Cleaned up {len(deleted_files)} untracked batch files")
        else:
            logger.info("No untracked batch files to clean up")
            
    except Exception as e:
        logger.error(f"Error during batch file cleanup: {e}")

def check_if_all_work_complete(session: Session) -> bool:
    """
    Check if all analysis work is complete.
    
    Returns:
        True if no unanalyzed articles and no active batches
    """
    # Check for unanalyzed articles
    unanalyzed_count = session.query(NewsArticle).filter(
        NewsArticle.analysis_status == "unanalyzed",
        NewsArticle.text != None,
        NewsArticle.text != ""
    ).count()
    
    # Check for active batches
    active_batches = read_batches_file()
    active_batch_count = len(active_batches)
    
    logger.info(f"Work status: {unanalyzed_count} unanalyzed articles, {active_batch_count} active batches")
    
    return unanalyzed_count == 0 and active_batch_count == 0

def run_post_analysis_tasks():
    """Run statistics and clustering after all analysis is complete."""
    logger.info("=== All analysis complete! Running post-analysis tasks ===")
    
    try:
        # Run the statistics command
        logger.info("Running statistical analysis and clustering...")
        import subprocess
        
        # Get the project root directory
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        run_script = os.path.join(script_dir, "run.sh")
        
        # Run statistics with all components
        result = subprocess.run([run_script, "statistics"], 
                              capture_output=True, text=True, 
                              cwd=script_dir)
        
        if result.returncode == 0:
            logger.info("✅ Statistical analysis completed successfully")
            logger.info(f"Statistics output:\n{result.stdout}")
        else:
            logger.error(f"❌ Statistical analysis failed with return code {result.returncode}")
            logger.error(f"Error output:\n{result.stderr}")
            
    except Exception as e:
        logger.error(f"Error running post-analysis tasks: {e}")

def run_analyzer(daemon_mode=False):
    """Run the batch analyzer main loop."""
    # Acquire lock to ensure only one instance runs
    lock_file = acquire_lock()
    if not lock_file:
        logger.error("Another instance of the analyzer is already running. Exiting.")
        return
    
    try:
        # Setup database
        session = setup_database()
        
        # Startup cleanup
        logger.info("=== Starting batch analyzer cleanup ===")
        
        # Reset any stuck in_progress articles
        reset_in_progress_articles(session)
        
        # Clear the batches directory
        clear_batches_directory()
        
        # Clear the tracking file
        logger.info("Clearing batch tracking file...")
        write_batches_file([])
        logger.info("Batch tracking file cleared")
        
        logger.info("=== Cleanup complete, starting fresh ===")
        
        if daemon_mode:
            logger.info("Starting analyzer in daemon mode. Press Ctrl+C to exit.")
            logger.info("📊 Daemon will automatically shut down and run statistics when all articles are processed.")
            
            def signal_handler(sig, frame):
                logger.info("Received signal to exit. Cleaning up...")
                
                
                release_lock(lock_file)
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Track when we last did maintenance cleanup
            last_maintenance = time.time()
            # Track consecutive idle cycles
            idle_cycles = 0
            max_idle_cycles = 3  # Wait 3 cycles (15 minutes) before shutting down
            
            while True:
                # Check active batches and create new ones
                check_active_batches(session)
                create_new_batch(session)
                
                # Check if all work is complete
                if check_if_all_work_complete(session):
                    idle_cycles += 1
                    logger.info(f"🏁 No work remaining. Idle cycle {idle_cycles}/{max_idle_cycles}")
                    
                    if idle_cycles >= max_idle_cycles:
                        logger.info("🏁 All analysis work is complete! Shutting down daemon...")
                        
                        
                        # Run post-analysis tasks
                        run_post_analysis_tasks()
                        
                        logger.info("🎉 Analysis daemon completed successfully!")
                        break
                else:
                    # Reset idle counter if there's work
                    idle_cycles = 0
                
                # Run maintenance cleanup every hour
                now = time.time()
                if now - last_maintenance > 3600:  # 1 hour in seconds
                    cleanup_old_batch_files()
                    last_maintenance = now
                
                logger.info(f"Sleeping for 5 minutes ({POLL_INTERVAL_SECONDS} seconds)...")
                time.sleep(POLL_INTERVAL_SECONDS)
        else:
            # Single run mode
            check_active_batches(session)
            create_new_batch(session)
    
    finally:
        release_lock(lock_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch analyzer for news articles")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run in daemon mode")
    
    args = parser.parse_args()
    run_analyzer(daemon_mode=args.daemon)