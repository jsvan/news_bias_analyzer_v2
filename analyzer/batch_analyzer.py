#!/usr/bin/env python3
"""
Batch analyzer for news articles using OpenAI's Batch API.

This module handles:
1. Creating batches of unanalyzed articles
2. Uploading batches to OpenAI's Batch API (max 4 active batches)
3. Tracking batch status in the openai_batches DB table (with a human-readable
   mirror at batches/batches.txt); OpenAI's batch list is reconciled on startup
   so a restart adopts in-flight batches instead of orphaning them
4. Polling for batch completion
5. Processing completed batches
6. Handling failed or cancelled batches, with backoff and a daily spend cap
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
from sqlalchemy import create_engine, text, func, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.models import NewsArticle, Entity, EntityMention, NewsSource, OpenAIBatch, MIN_ARTICLE_CHARS
from database.services import DatabaseService
from database.config import AnalysisConfig, LoggingConfig
from analyzer.config import get_config
from analyzer.prompts import ENTITY_SENTIMENT_PROMPT, ENTITY_SENTIMENT_SCHEMA
from analyzer.openai_integration import sampling_params, OpenAIProcessor
from analyzer.hotelling_t2 import HotellingT2Calculator
from analyzer.entity_resolution import known_entity_shortlist, format_shortlist_block

# Setup directories
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH_DIR = os.path.join(ROOT_DIR, "batches")
if not os.path.exists(BATCH_DIR):
    os.makedirs(BATCH_DIR)

# Setup logging
LOG_DIR = os.path.join(ROOT_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# force=True: imported modules must not get to configure the root logger first
# (a module-level basicConfig in any import used to win the race, leaving this
# one a no-op and batch_analysis.log empty forever). Stream-only: the scheduler
# redirects the daemon's stdout/stderr into logs/batch_analysis.log, which also
# captures uncaught tracebacks that the logging module would never see.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger("batch_analyzer")

# Global variables
BATCHES_MIRROR = os.path.join(BATCH_DIR, "batches.txt")  # human-readable, host-mounted; DB table is the source of truth
MAX_ACTIVE_BATCHES = 4  # Reduced from 5 to avoid overwhelming OpenAI
BATCH_SIZE = 50  # Reduced from 100 to 50 for better manageability
POLL_INTERVAL_SECONDS = 300  # 5 minutes
LOCK_FILE = os.path.join(ROOT_DIR, "analyzer", "analyzer.lock")
MAX_ANALYSIS_ATTEMPTS = 3  # submissions per article before it's marked failed for good
RECONCILE_WINDOW_HOURS = 48  # how far back startup reconciliation looks for uncollected completed batches
NON_TERMINAL_STATUSES = ("validating", "in_progress", "finalizing", "cancelling")

# Backoff state for batch submission failures (billing wall, quota, network).
# Without this the daemon rebuilt and re-uploaded an identical batch every five
# minutes for hours, silently - see the 2026-08-13 billing-limit outage.
_creation_backoff = {"failures": 0, "until": 0.0}

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

def make_openai_client() -> Optional[OpenAI]:
    """Create an OpenAI client from the environment, or None if no key."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OpenAI API key not found in environment variables")
        return None
    return OpenAI(api_key=api_key)

def load_active_batches(session: Session) -> List[OpenAIBatch]:
    """Batches we still owe action on: not yet ingested or resolved."""
    return (session.query(OpenAIBatch)
            .filter(OpenAIBatch.collected == False)
            .order_by(OpenAIBatch.submitted_at)
            .all())

def count_active_batches(session: Session) -> int:
    return session.query(OpenAIBatch).filter(OpenAIBatch.collected == False).count()

def write_batches_mirror(session: Session):
    """Human-readable mirror of recent batch tracking on the host-mounted volume."""
    try:
        rows = (session.query(OpenAIBatch)
                .order_by(OpenAIBatch.submitted_at.desc())
                .limit(50).all())
        tmp_path = BATCHES_MIRROR + ".tmp"
        with open(tmp_path, 'w') as f:
            f.write("# Mirror of the openai_batches DB table (source of truth), newest first\n")
            for b in rows:
                f.write(json.dumps({
                    "batch_id": b.batch_id,
                    "status": b.status,
                    "collected": b.collected,
                    "article_count": b.article_count,
                    "estimated_cost_usd": b.estimated_cost_usd,
                    "submitted_at": b.submitted_at.isoformat() if b.submitted_at else None,
                    "error": b.error,
                }) + '\n')
        os.replace(tmp_path, BATCHES_MIRROR)  # atomic - readers never see a torn file
    except Exception as e:
        logger.warning(f"Could not write batches mirror: {e}")

def delete_remote_file(client: OpenAI, file_id: Optional[str]):
    """Delete a file from OpenAI storage; inputs are rebuilt from our DB and
    outputs are ingested before deletion, so nothing here is irreplaceable."""
    if not file_id:
        return
    try:
        client.files.delete(file_id)
        logger.info(f"Deleted OpenAI file {file_id}")
    except Exception as e:
        logger.warning(f"Could not delete OpenAI file {file_id}: {e}")

def _register_creation_failure(error_text: str):
    """Back off after a failed submission, or a batch that failed to run after
    a clean submission, instead of retrying every cycle."""
    _creation_backoff["failures"] += 1
    if "billing" in error_text.lower() or "quota" in error_text.lower():
        # Billing walls don't clear in minutes; retry hourly.
        delay = 3600
    else:
        delay = min(3600, POLL_INTERVAL_SECONDS * (2 ** _creation_backoff["failures"]))
    _creation_backoff["until"] = time.time() + delay
    logger.error(f"OpenAI batch failure ({error_text}); backing off {delay}s "
                 f"(consecutive failures: {_creation_backoff['failures']})")

def _reset_creation_backoff():
    if _creation_backoff["failures"]:
        logger.info("Batch submission recovered; clearing backoff")
    _creation_backoff["failures"] = 0
    _creation_backoff["until"] = 0.0

# Billed output tokens per article by reasoning effort, measured on this
# corpus: ~314 visible tokens/article (July gpt-4.1-nano run, zero reasoning)
# vs ~7-8k total at gpt-5-nano's default "medium" (the 2026-08-14 $10 bill).
# 2026-08-14: the mentions/quote arrays (58-78% of visible output) were dropped
# from the schema - measured ~560 visible tokens/article with them, ~250 without.
# Rounded up - the daily-limit guard should overestimate, never under.
OUTPUT_TOKENS_PER_ARTICLE_BY_EFFORT = {
    "none": 400, "minimal": 400, "low": 2500, "medium": 8000,
    "high": 16000, "xhigh": 24000, "max": 32000,
}

def estimate_batch_cost_usd(input_bytes: int, n_articles: int, model: str) -> float:
    """Pre-submission cost estimate: bytes/4 ≈ input tokens; output per article
    scales with reasoning effort for gpt-5-family models (flat ~1000 for older
    non-reasoning models). Batch API halves standard-tier prices."""
    for prefix, (in_price, out_price) in OpenAIProcessor.PRICES_PER_1M.items():
        if model.startswith(prefix):
            break
    else:
        in_price, out_price = 1.25, 10.0  # unknown model: assume mid-tier
    input_tokens = input_bytes / 4
    per_article_out = 1000
    if model.startswith("gpt-5"):
        effort = sampling_params(model, 0.0, 0).get("reasoning_effort", "medium")
        per_article_out = OUTPUT_TOKENS_PER_ARTICLE_BY_EFFORT.get(effort, 8000)
    output_tokens = n_articles * per_article_out
    return 0.5 * (input_tokens * in_price + output_tokens * out_price) / 1_000_000

def today_estimated_spend(session: Session) -> float:
    """Sum of cost estimates for batches submitted since local midnight."""
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total = (session.query(func.coalesce(func.sum(OpenAIBatch.estimated_cost_usd), 0.0))
             .filter(OpenAIBatch.submitted_at >= midnight)
             .scalar())
    return float(total or 0.0)

def get_unanalyzed_articles(session: Session, limit: int = BATCH_SIZE) -> List[NewsArticle]:
    """Get a batch of unanalyzed articles."""
    try:
        articles = session.query(NewsArticle).filter(
            NewsArticle.analysis_status == "unanalyzed",
            NewsArticle.text != None,
            # Guard against stub rows scraped before the scrape-time length check
            func.length(NewsArticle.text) >= MIN_ARTICLE_CHARS,
            func.coalesce(NewsArticle.analysis_attempts, 0) < MAX_ANALYSIS_ATTEMPTS
        ).limit(limit).all()

        return articles
    except Exception as e:
        logger.error(f"Error getting unanalyzed articles: {e}")
        return []

def get_known_entities(session: Session, limit: int = 2000) -> List[Tuple[str, int]]:
    """Top canonical entities by mention count, for known-entity prompt injection."""
    try:
        rows = (session.query(Entity.name, func.count(EntityMention.id).label("n"))
                .join(EntityMention, EntityMention.entity_id == Entity.id)
                .filter(Entity.canonical_id == None)
                .group_by(Entity.name)
                .order_by(func.count(EntityMention.id).desc())
                .limit(limit).all())
        return [(name, n) for name, n in rows]
    except Exception as e:
        logger.error(f"Error loading known entities: {e}")
        return []

def prepare_batch_input(articles: List[NewsArticle], model: str,
                        known_entities: Optional[List[Tuple[str, int]]] = None) -> Tuple[str, Dict[str, NewsArticle]]:
    """Prepare batch input file content and article lookup mapping.

    If known_entities is provided, each article's prompt gets a shortlist of
    already-tracked entities matched in its text, so the model reuses canonical
    names (entity-resolution layer 0 — see docs/ROADMAP_IDEAS_2026.md §12).
    """
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

        if known_entities:
            shortlist = known_entity_shortlist(analysis_text, known_entities)
            analysis_text += format_shortlist_block(shortlist)
        
        # Create batch request line. gpt-5-family models reject the temperature
        # param outright (every batch line would fail) - sampling_params knows
        # which knobs each model accepts.
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": ENTITY_SENTIMENT_PROMPT},
                {"role": "user", "content": analysis_text}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "entity_sentiment",
                    "strict": True,
                    "schema": ENTITY_SENTIMENT_SCHEMA,
                },
            },
        }
        # max_tokens is deliberately not sent in batch mode (pre-existing
        # behavior); reasoning_effort is the knob that keeps gpt-5-family
        # output spend sane - without it nano defaults to "medium" reasoning.
        params = sampling_params(model, 0.2, 0)
        params.pop("max_tokens", None)
        body.update(params)
        batch_line = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body,
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

def create_openai_batch(client: OpenAI, file_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Create a batch in OpenAI. Returns (batch_id, None) or (None, error text)."""
    try:
        batch = client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )

        logger.info(f"Created OpenAI batch: {batch.id}")
        return batch.id, None
    except Exception as e:
        body = getattr(e, "body", None)
        logger.error(f"Error creating OpenAI batch: {e} (body={body})")
        code = body.get("code") if isinstance(body, dict) else None
        return None, str(code or e)

def update_articles_status(session: Session, articles: List[NewsArticle], status: str, batch_id: str = None):
    """Update the status of a list of articles."""
    try:
        for article in articles:
            article.analysis_status = status
            article.batch_id = batch_id
            article.last_analysis_attempt = datetime.now()
            if status == "in_progress":
                # Submission counts as an attempt; MAX_ANALYSIS_ATTEMPTS caps re-pay loops
                article.analysis_attempts = (article.analysis_attempts or 0) + 1

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
            "errors": getattr(batch, "errors", None),
        }
    except Exception as e:
        logger.error(f"Error checking batch status: {e}")
        return None

def summarize_batch_errors(errors) -> str:
    """Flatten a batch's error list into one line for the openai_batches.error
    column. Storing only the word 'failed' turned the Aug 27-Sep 2 2026 OpenAI
    outage into an API archaeology session - the real message was only on the
    remote batch object."""
    try:
        data = getattr(errors, "data", None) or []
        msgs = [f"{getattr(e, 'code', '?')}: {getattr(e, 'message', '')}" for e in data]
        return "; ".join(m for m in msgs if m)[:2000]
    except Exception:
        return ""

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

def process_batch_output(session: Session, output_content: str, article_lookup: Dict[str, NewsArticle], batch_id: str = "unknown"):
    """Process batch output and update database. Idempotent: articles already
    marked completed are skipped, so re-ingesting an output file is harmless."""
    # Parse output file (one JSONL line per result)
    results = [json.loads(line) for line in output_content.splitlines() if line.strip()]
    
    processed_count = 0
    error_count = 0
    skipped_count = 0           # Already-completed articles (idempotent re-ingestion)
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

        # Idempotency guard: startup reconciliation can re-download outputs that
        # an earlier run already ingested, and an adopted batch can overlap a
        # resubmission of the same articles. Completed articles already have
        # their mentions written and their text cleared - never ingest twice.
        if article.analysis_status == "completed":
            skipped_count += 1
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
        else:
            logger.error(f"❌ Verification failed: {actual_diff} new articles marked as completed (expected {expected_diff})")
            
            # Detailed check on each article
            for article_id in processed_article_ids:
                article = session.query(NewsArticle).get(article_id)
                if article and article.analysis_status == "completed":
                    logger.debug(f"Article {article_id} successfully marked as completed")
                else:
                    logger.error(f"Article {article_id} failed to update status to completed")
        
        logger.info(f"Processed batch: {processed_count} articles processed, {error_count} errors, {skipped_count} already completed (skipped)")
        logger.info(f"Total completed articles: {after_count} (was {before_count} before)")
        logger.info(f"💾 Cleared text from {processed_count} articles to save storage space")
        
        # Reset failed articles back to unanalyzed so they can be attempted again in future batches
        if failed_article_ids:
            reset_failed_articles_by_ids(session, failed_article_ids)
        
    except Exception as e:
        logger.error(f"Error committing batch results: {e}")
        session.rollback()
        
    return processed_count, error_count

def _requeue_or_retire(article: NewsArticle) -> bool:
    """Requeue an article for another attempt, or retire it as permanently
    failed once it has burned MAX_ANALYSIS_ATTEMPTS submissions (each one costs
    real money). Returns True if requeued."""
    if (article.analysis_attempts or 0) >= MAX_ANALYSIS_ATTEMPTS:
        article.analysis_status = "failed"
        article.batch_id = None
        return False
    article.analysis_status = "unanalyzed"
    article.batch_id = None
    return True

def reset_failed_articles(session: Session, batch_id: str, refund_attempt: bool = False):
    """Requeue articles that a specific batch left unfinished (in_progress means
    the batch never returned a result for them, failed means the result was bad).

    refund_attempt: the batch itself never ran (validation failure, vendor
    outage), so the submission cost nothing - give the attempt back. Counting
    those attempts let the Aug 27-Sep 2 2026 OpenAI outage retire 16.8k
    articles through MAX_ANALYSIS_ATTEMPTS in hours."""
    try:
        articles = session.query(NewsArticle).filter(
            NewsArticle.batch_id == batch_id,
            NewsArticle.analysis_status.in_(["in_progress", "failed"])
        ).all()

        if refund_attempt:
            for a in articles:
                if a.analysis_status == "in_progress" and (a.analysis_attempts or 0) > 0:
                    a.analysis_attempts -= 1

        requeued = sum(1 for a in articles if _requeue_or_retire(a))
        retired = len(articles) - requeued

        session.commit()
        if articles:
            logger.info(f"Batch {batch_id} leftovers: {requeued} articles requeued, {retired} retired as failed")
    except Exception as e:
        logger.error(f"Error resetting failed articles: {e}")
        session.rollback()

def reset_failed_articles_by_ids(session: Session, article_ids: List[str]):
    """Requeue (or retire) specific failed articles by ID."""
    if not article_ids:
        return

    try:
        requeued = retired = 0
        for article_id in article_ids:
            article = session.query(NewsArticle).get(article_id)
            if article and article.analysis_status == "failed":
                if _requeue_or_retire(article):
                    requeued += 1
                else:
                    retired += 1

        if requeued or retired:
            session.commit()
            logger.info(f"Failed articles: {requeued} requeued for reprocessing, {retired} retired after {MAX_ANALYSIS_ATTEMPTS} attempts")
    except Exception as e:
        logger.error(f"Error resetting failed articles by IDs: {e}")
        session.rollback()

def create_new_batch(session: Session) -> bool:
    """
    Create a new batch if under the maximum active batches.
    
    Returns:
        True if a new batch was created, False otherwise
    """
    # Back off after submission failures instead of re-uploading an identical
    # batch every cycle (the 2026-08-13 billing outage looped for 4+ hours)
    if time.time() < _creation_backoff["until"]:
        remaining = int(_creation_backoff["until"] - time.time())
        logger.info(f"Submission backoff active ({remaining}s left); not creating a batch")
        return False

    # Check how many active batches we have
    active_count = count_active_batches(session)

    if active_count >= MAX_ACTIVE_BATCHES:
        logger.info(f"Maximum active batches ({MAX_ACTIVE_BATCHES}) reached. Cannot create new batch.")
        return False

    client = make_openai_client()
    if not client:
        return False

    # Get OpenAI model from environment or default to gpt-5-nano
    model = os.environ.get("OPENAI_MODEL", "gpt-5-nano")

    # Get unanalyzed articles
    articles = get_unanalyzed_articles(session)

    if not articles:
        logger.info("No unanalyzed articles found.")
        return False

    # Check minimum batch size
    if len(articles) < BATCH_SIZE:
        logger.info(f"Only {len(articles)} unanalyzed articles found. Minimum batch size is {BATCH_SIZE}. Skipping batch creation.")
        return False

    logger.info(f"Found {len(articles)} unanalyzed articles for new batch (model: {model})")

    # Prepare batch input (known-entity injection is opt-in until validated on a pilot)
    known_entities = None
    if os.environ.get("KNOWN_ENTITY_INJECTION") == "1":
        known_entities = get_known_entities(session)
        logger.info(f"Known-entity injection on: {len(known_entities)} canonical names loaded")
    batch_content, article_lookup = prepare_batch_input(articles, model, known_entities)

    # Daily spend cap (analyzer/config.py cost_limits, OPENAI_DAILY_LIMIT env
    # override). Checked before upload so nothing is spent past the cap.
    est_cost = estimate_batch_cost_usd(len(batch_content.encode()), len(articles), model)
    daily_limit = float(get_config().get("openai.cost_limits.daily_limit_usd", 50.0))
    spent = today_estimated_spend(session)
    if spent + est_cost > daily_limit:
        tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        _creation_backoff["until"] = tomorrow.timestamp()
        logger.error(f"Daily spend cap reached: ~${spent:.2f} submitted today + ~${est_cost:.2f} for this batch "
                     f"exceeds the ${daily_limit:.2f} limit. Pausing submissions until midnight.")
        return False

    # Small delay between submissions to avoid overwhelming OpenAI
    time.sleep(10)

    # Create local batch file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_filename = f"batch_{timestamp}.jsonl"
    batch_file_path = create_batch_file(batch_content, batch_filename)

    if not batch_file_path:
        logger.error("Failed to create batch file")
        return False

    # Upload batch file to OpenAI
    file_id = upload_batch_file(client, batch_file_path)

    if not file_id:
        os.remove(batch_file_path)
        _register_creation_failure("file upload failed")
        return False

    # Create OpenAI batch
    batch_id, error_text = create_openai_batch(client, file_id)

    if not batch_id:
        # Don't leave the uploaded input orphaned in OpenAI storage
        delete_remote_file(client, file_id)
        os.remove(batch_file_path)
        _register_creation_failure(error_text or "batch creation failed")
        return False

    # Backoff clears on successful INGESTION (ingest_batch_output), not here: a
    # submission can succeed and the batch still fail to run (Aug 27-Sep 2 2026
    # outage), and clearing on submission would defeat the escalation.

    # Update article status (also increments analysis_attempts)
    update_articles_status(session, articles, "in_progress", batch_id)

    # Track in the DB. No article-map sidecar file: each custom_id embeds its
    # article id, so outputs are self-describing even after a restart.
    session.add(OpenAIBatch(
        batch_id=batch_id,
        input_file_id=file_id,
        status="validating",
        article_count=len(articles),
        estimated_cost_usd=est_cost,
        submitted_at=datetime.now(),
    ))
    session.commit()
    write_batches_mirror(session)

    # The local input file has done its job - the content is on OpenAI now and
    # rebuildable from the DB regardless
    os.remove(batch_file_path)

    logger.info(f"Created new batch: {batch_id} ({len(articles)} articles, est ~${est_cost:.2f})")
    return True

def build_article_lookup_from_output(session: Session, output_content: str) -> Dict[str, NewsArticle]:
    """Rebuild the custom_id -> article mapping from a batch output file.

    custom_ids are 'article_<id>', so outputs are self-describing. No local
    sidecar file involved, which is what lets reconciliation ingest batches
    submitted by a previous container."""
    lookup = {}
    for line in output_content.splitlines():
        if not line.strip():
            continue
        try:
            custom_id = json.loads(line).get("custom_id") or ""
        except json.JSONDecodeError:
            continue
        if not custom_id.startswith("article_") or custom_id in lookup:
            continue
        article = session.query(NewsArticle).get(custom_id[len("article_"):])
        if article:
            lookup[custom_id] = article
        else:
            logger.warning(f"Article for {custom_id} no longer exists in the database. Skipping.")
    return lookup

def ingest_batch_output(session: Session, client: OpenAI, row: OpenAIBatch) -> bool:
    """Download and ingest a completed batch's output, resolve the tracking row,
    and delete the batch's files from OpenAI storage."""
    if not row.output_file_id:
        logger.warning(f"No output file ID for completed batch {row.batch_id}")
        return False

    output_content = download_batch_output(client, row.output_file_id)
    if not output_content:
        return False

    article_lookup = build_article_lookup_from_output(session, output_content)
    processed_count, error_count = process_batch_output(session, output_content, article_lookup, row.batch_id)
    logger.info(f"Processed batch {row.batch_id}: {processed_count} articles, {error_count} errors")

    # Articles the output never mentioned (request-level errors land in the
    # error file, not the output) would sit in_progress forever - requeue them
    reset_failed_articles(session, row.batch_id)

    row.status = "completed"
    row.completed_at = datetime.now()
    row.collected = True
    session.commit()

    # A batch made it through OpenAI end-to-end - the pipeline is healthy again
    _reset_creation_backoff()

    # OpenAI storage hygiene: inputs rebuild from our DB, outputs are ingested -
    # leaving them accumulates hundreds of MB of dead files on the account
    delete_remote_file(client, row.input_file_id)
    delete_remote_file(client, row.output_file_id)
    return True

def check_active_batches(session: Session):
    """Check status of active batches, ingest completed ones, resolve failures."""
    batches = load_active_batches(session)

    if not batches:
        logger.info("No active batches to check")
    else:
        client = make_openai_client()
        if not client:
            return

        for row in batches:
            batch_status = check_batch_status(client, row.batch_id)

            if not batch_status:
                logger.error(f"Failed to get status for batch {row.batch_id}")
                continue

            row.status = batch_status['status']
            if batch_status.get('output_file_id'):
                row.output_file_id = batch_status['output_file_id']

            if row.status == 'completed' and row.output_file_id:
                logger.info(f"Batch {row.batch_id} is complete. Processing output...")
                try:
                    ingest_batch_output(session, client, row)
                except Exception as e:
                    logger.error(f"Error processing batch {row.batch_id}: {e}", exc_info=True)
            elif row.status in ['failed', 'cancelled', 'expired']:
                detail = summarize_batch_errors(batch_status.get("errors"))
                logger.warning(f"Batch {row.batch_id} is {row.status} ({detail or 'no error detail'}). Requeuing its articles...")
                row.error = f"{row.status}: {detail}" if detail else row.status
                row.collected = True
                # failed/cancelled never ran, so the attempt was free; expired
                # batches partially ran and are conservatively left counted
                reset_failed_articles(session, row.batch_id,
                                      refund_attempt=row.status in ('failed', 'cancelled'))
                delete_remote_file(client, row.input_file_id)
                # Escalating backoff: a batch that fails after successful
                # submission (the Aug 27-Sep 2 2026 file-visibility outage) must
                # not trigger an immediate resubmit every 5-minute cycle
                _register_creation_failure(f"batch {row.batch_id} {row.status}"
                                           + (f" - {detail}" if detail else ""))

            session.commit()

        write_batches_mirror(session)

    # Create new batches if we're under the limit
    slots_available = MAX_ACTIVE_BATCHES - count_active_batches(session)

    if slots_available > 0:
        logger.info(f"{slots_available} batch slots available. Creating new batches...")

        for _ in range(slots_available):
            if not create_new_batch(session):
                break

def reconcile_with_openai(session: Session, client: OpenAI):
    """Adopt OpenAI's view of our batches on startup.

    OpenAI's batch list is the authority; local state can be lost (the previous
    tracking file lived inside the container and died on every rebuild). Any
    non-terminal batch we don't know about is adopted and polled as our own;
    any completed batch from the last RECONCILE_WINDOW_HOURS whose output was
    never ingested is ingested now (article-level idempotency makes re-downloads
    harmless). This is what stops a restart from orphaning paid-for work.
    """
    known = {batch_id for (batch_id,) in session.query(OpenAIBatch.batch_id).all()}
    cutoff_ts = time.time() - RECONCILE_WINDOW_HOURS * 3600

    remote = []
    after = None
    try:
        while True:
            page = client.batches.list(limit=100, after=after) if after else client.batches.list(limit=100)
            if not page.data:
                break
            remote.extend(page.data)
            if page.data[-1].created_at < cutoff_ts or len(page.data) < 100:
                break  # list is newest-first; everything further back is out of scope
            after = page.data[-1].id
    except Exception as e:
        logger.error(f"Could not list OpenAI batches for reconciliation: {e}")
        return

    adopted = ingested = 0
    for rb in remote:
        if rb.id in known:
            continue
        non_terminal = rb.status in NON_TERMINAL_STATUSES
        if not non_terminal and rb.created_at < cutoff_ts:
            continue

        row = OpenAIBatch(
            batch_id=rb.id,
            input_file_id=rb.input_file_id,
            output_file_id=getattr(rb, "output_file_id", None),
            status=rb.status,
            submitted_at=datetime.fromtimestamp(rb.created_at),
        )
        session.add(row)

        if non_terminal:
            session.commit()
            adopted += 1
            logger.info(f"Adopted in-flight batch {rb.id} (status={rb.status}) from OpenAI")
        elif rb.status == "completed" and rb.output_file_id:
            session.commit()
            try:
                if ingest_batch_output(session, client, row):
                    ingested += 1
            except Exception as e:
                logger.error(f"Error ingesting batch {rb.id} during reconciliation: {e}", exc_info=True)
        else:
            # failed/cancelled/expired and unknown to us: just record it as resolved
            row.collected = True
            detail = summarize_batch_errors(getattr(rb, "errors", None))
            row.error = f"{rb.status}: {detail}" if detail else rb.status
            session.commit()

    logger.info(f"Reconciliation: {adopted} in-flight batches adopted, {ingested} completed batches ingested")

def reset_orphaned_in_progress_articles(session: Session):
    """Requeue in_progress articles whose batch is no longer tracked.

    Runs AFTER reconciliation, so articles belonging to live adopted batches
    keep their status and their results get collected instead of re-bought.
    """
    try:
        active_ids = [b.batch_id for b in load_active_batches(session)]
        query = session.query(NewsArticle).filter(NewsArticle.analysis_status == "in_progress")
        if active_ids:
            query = query.filter(or_(NewsArticle.batch_id == None,
                                     ~NewsArticle.batch_id.in_(active_ids)))
        articles = query.all()

        if articles:
            requeued = sum(1 for a in articles if _requeue_or_retire(a))
            session.commit()
            logger.info(f"Orphaned in_progress articles: {requeued} requeued, {len(articles) - requeued} retired as failed")
        else:
            logger.info("No orphaned in_progress articles found")

    except Exception as e:
        logger.error(f"Error resetting orphaned in_progress articles: {e}")
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
    """Delete leftover local batch files older than a day.

    Inputs are removed right after submission and outputs are never written
    locally, so anything lingering is residue from a crashed cycle."""
    try:
        if not os.path.exists(BATCH_DIR):
            return

        cutoff = time.time() - 86400
        removed = 0
        for filename in os.listdir(BATCH_DIR):
            if not (filename.endswith('.jsonl') or filename.endswith('.articles.json')):
                continue
            file_path = os.path.join(BATCH_DIR, filename)
            try:
                if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff:
                    os.remove(file_path)
                    removed += 1
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")

        if removed:
            logger.info(f"Cleaned up {removed} leftover batch files")

    except Exception as e:
        logger.error(f"Error during batch file cleanup: {e}")

def check_if_all_work_complete(session: Session) -> bool:
    """
    Check if all analysis work is complete.
    
    Returns:
        True if no unanalyzed articles and no active batches
    """
    # Check for unanalyzed articles still worth submitting (attempt cap aside,
    # retired articles would otherwise keep the daemon alive forever)
    unanalyzed_count = session.query(NewsArticle).filter(
        NewsArticle.analysis_status == "unanalyzed",
        NewsArticle.text != None,
        NewsArticle.text != "",
        func.coalesce(NewsArticle.analysis_attempts, 0) < MAX_ANALYSIS_ATTEMPTS
    ).count()

    # Check for active batches
    active_batch_count = count_active_batches(session)

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

        # Startup: sync with OpenAI BEFORE touching any local state, so batches
        # submitted by a previous container are adopted and their paid-for
        # results collected, not orphaned and re-bought
        logger.info("=== Starting batch analyzer reconciliation ===")
        client = make_openai_client()
        if client:
            reconcile_with_openai(session, client)
        reset_orphaned_in_progress_articles(session)
        clear_batches_directory()
        write_batches_mirror(session)
        logger.info("=== Reconciliation complete ===")
        
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