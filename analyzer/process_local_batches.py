#!/usr/bin/env python3
"""
Process local batch files with custom naming patterns.
This script handles the mapping between input files (batch_YYYYMMDD_HHMMSS.jsonl)
and output files (batch_<openai_id>_output.jsonl).
"""

import os
import sys
import logging
import json
import re
from pathlib import Path
from datetime import datetime
import openai
import tempfile
import shutil

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analyzer.tools.recover_openai_batches import (
    process_batch_file,
    ensure_default_source,
    DatabaseManager
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("process_local_batches")

def read_batch_tracking():
    """
    Read the batch tracking file to get OpenAI batch IDs.
    Returns a list of batch info dictionaries.
    """
    tracking_file = Path('analyzer/batches.txt')
    if not tracking_file.exists():
        logger.error(f"Batch tracking file not found: {tracking_file}")
        return []
    
    batches = []
    with open(tracking_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    batch_info = json.loads(line)
                    batches.append(batch_info)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in tracking file: {line[:50]}...")
    
    return batches

def download_batch_results(batch_info, output_dir):
    """
    Download the output file for a completed batch from OpenAI.
    """
    batch_id = batch_info['id']
    status = batch_info.get('status', 'unknown')
    
    if status != 'completed':
        logger.info(f"Batch {batch_id} is not completed (status: {status}), skipping")
        return None
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return None
    
    openai.api_key = api_key
    
    try:
        # Get batch details from OpenAI
        batch = openai.batches.retrieve(batch_id)
        
        if batch.status != 'completed':
            logger.info(f"Batch {batch_id} status is {batch.status}, skipping")
            return None
        
        output_file_id = batch.output_file_id
        if not output_file_id:
            logger.warning(f"No output file for batch {batch_id}")
            return None
        
        # Download the output file
        output_path = Path(output_dir) / f"{batch_id}_output.jsonl"
        
        if output_path.exists():
            logger.info(f"Output file already exists: {output_path}")
            return str(output_path)
        
        logger.info(f"Downloading output file for batch {batch_id}")
        output_stream = openai.files.content(output_file_id)
        
        with open(output_path, "wb") as f:
            f.write(output_stream.read())
        
        logger.info(f"Downloaded output file to {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Error downloading batch {batch_id}: {e}")
        return None

def find_batch_pairs_with_tracking(batch_dir, temp_dir):
    """
    Find batch pairs using the tracking file and download missing outputs.
    Returns list of (input_file, output_file) tuples.
    """
    batch_path = Path(batch_dir)
    matched_pairs = []
    
    # Read batch tracking
    batch_tracking = read_batch_tracking()
    if not batch_tracking:
        logger.error("No batch tracking data found")
        return []
    
    logger.info(f"Found {len(batch_tracking)} batches in tracking file")
    
    # Process each tracked batch
    for batch_info in batch_tracking:
        batch_file = batch_info.get('batch_file')
        batch_id = batch_info.get('id')
        status = batch_info.get('status', 'unknown')
        
        if not batch_file or not batch_id:
            logger.warning(f"Invalid batch info: {batch_info}")
            continue
        
        # Check if input file exists
        input_file = batch_path / batch_file
        if not input_file.exists():
            logger.warning(f"Input file not found: {input_file}")
            continue
        
        # Only process completed batches
        if status != 'completed':
            logger.info(f"Skipping batch {batch_file} with status: {status}")
            continue
        
        # Check for output file or download it
        output_file = None
        
        # First check if we already have it in temp_dir
        temp_output = Path(temp_dir) / f"{batch_id}_output.jsonl"
        if temp_output.exists():
            output_file = temp_output
        else:
            # Try to download it
            logger.info(f"Attempting to download output for batch {batch_id}")
            downloaded_path = download_batch_results(batch_info, temp_dir)
            if downloaded_path:
                output_file = Path(downloaded_path)
        
        if output_file and output_file.exists():
            matched_pairs.append((input_file, output_file))
            logger.info(f"Matched pair: {input_file.name} -> {output_file.name}")
        else:
            logger.warning(f"Could not get output file for batch {batch_id}")
    
    return matched_pairs

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Process completed batch files from the batches/ directory')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be processed without modifying database')
    
    args = parser.parse_args()
    
    # Always use the batches/ directory
    batch_dir = 'batches'
    batch_path = Path(batch_dir)
    
    if not batch_path.exists():
        logger.error(f"Batch directory does not exist: {batch_dir}")
        logger.info("This directory should be created by the batch analyzer daemon")
        return
    
    # Create temporary directory for downloaded files
    temp_dir = tempfile.mkdtemp(prefix="batch_progress_")
    logger.info(f"Created temporary directory: {temp_dir}")
    
    try:
        # Find matching batch pairs using tracking file
        batch_pairs = find_batch_pairs_with_tracking(batch_dir, temp_dir)
        
        if not batch_pairs:
            logger.warning("No completed batch pairs found to process")
            logger.info("This could mean:")
            logger.info("  1. No batches have completed yet")
            logger.info("  2. All completed batches have already been processed")
            logger.info("  3. Cannot download output files from OpenAI")
            return
        
        logger.info(f"Found {len(batch_pairs)} completed batch pairs to process")
        
        if args.dry_run:
            logger.info("Dry run mode - showing what would be processed:")
            for input_file, output_file in batch_pairs:
                logger.info(f"  {input_file.name} -> {output_file.name}")
            return
        
        # Initialize database
        db_manager = DatabaseManager()
        ensure_default_source(db_manager, 1)  # Always use default source ID 1
        
        # Process each batch pair
        stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'incomplete': 0,
            'recovered': 0,
            'total_processed': 0,
            'already_complete': 0,
            'not_found': 0
        }
        
        for input_file, output_file in batch_pairs:
            logger.info(f"\nProcessing batch pair:")
            logger.info(f"  Input:  {input_file}")
            logger.info(f"  Output: {output_file}")
            
            try:
                process_batch_file(
                    str(input_file),
                    str(output_file),
                    db_manager,
                    stats,
                    1  # Always use default source ID 1
                )
            except Exception as e:
                logger.error(f"Error processing batch pair: {e}")
                stats['errors'] += 1
    
        # Print summary
        logger.info("\n--- Processing Summary ---")
        logger.info(f"Total batch pairs processed: {len(batch_pairs)}")
        logger.info(f"Articles recovered (incomplete → complete): {stats['recovered']}")
        logger.info(f"Total articles processed: {stats['total_processed']}")
        logger.info(f"Articles already complete: {stats['already_complete']}")
        logger.info(f"Articles not found in database: {stats.get('not_found', 0)}")
        logger.info(f"Articles skipped: {stats['skipped']}")
        logger.info(f"Errors encountered: {stats['errors']}")
        logger.info(f"Incomplete data entries: {stats['incomplete']}")
    
    finally:
        # Clean up temp directory
        if Path(temp_dir).exists():
            logger.info(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()