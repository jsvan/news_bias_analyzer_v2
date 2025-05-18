#!/usr/bin/env python3
"""
Script to download OpenAI batch files.
This will retrieve all successful batches from 2025 and save them as input/output pairs.
"""

import os
import sys
import logging
import argparse
import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def unix_to_datetime(ts):
    """Convert Unix timestamp to datetime."""
    return datetime.datetime.utcfromtimestamp(ts)

def download_openai_batches(output_dir='openai_batches', year=2025, limit=None):
    """
    Download OpenAI batch files for the specified year.
    
    Args:
        output_dir: Directory to save batch files
        year: Year to filter batches (default: 2025)
        limit: Maximum number of batches to download (default: None - download all)
    
    Returns:
        count: Number of batches downloaded
    """
    try:
        import openai
    except ImportError:
        logger.error("OpenAI package not installed. Install with: pip install openai")
        return 0
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return 0
    
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
        return 0
    
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
    count = 0
    for batch in filtered_batches:
        batch_id = batch.id
        created_str = unix_to_datetime(batch.created_at).strftime("%Y-%m-%d %H:%M:%S UTC")
        input_file_id = batch.input_file_id
        output_file_id = batch.output_file_id
        
        logger.info(f"\nProcessing Batch ID: {batch_id}")
        logger.info(f"Uploaded on: {created_str}")
        
        # Download input file
        if input_file_id:
            try:
                input_stream = openai.files.content(input_file_id)
                input_path = output_path / f"{batch_id}_input.jsonl"
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
                output_path_file = output_path / f"{batch_id}_output.jsonl"
                with open(output_path_file, "wb") as f:
                    f.write(output_stream.read())
                logger.info(f"Downloaded output file to {output_path_file}")
            except Exception as e:
                logger.error(f"Error downloading output file: {e}")
                continue
        else:
            logger.warning("No output file found.")
            continue
        
        count += 1
    
    logger.info(f"\nDownloaded {count} successful batches from {year}")
    return count

def main():
    parser = argparse.ArgumentParser(description='Download OpenAI batch files')
    parser.add_argument('--output-dir', type=str, default='openai_batches',
                        help='Directory to save batch files (default: openai_batches)')
    parser.add_argument('--year', type=int, default=2025,
                        help='Year to filter batches (default: 2025)')
    parser.add_argument('--limit', type=int,
                        help='Maximum number of batches to download')
    
    args = parser.parse_args()
    
    download_openai_batches(args.output_dir, args.year, args.limit)

if __name__ == "__main__":
    main()