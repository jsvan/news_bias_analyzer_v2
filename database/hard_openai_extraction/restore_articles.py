#!/usr/bin/env python3
"""
Script to restore article analysis from OpenAI batches into the database.
This script processes pairs of input and output JSONL files from OpenAI batches
and inserts the extracted entities and sentiment analysis back into the database.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add the parent directory to the path to import database modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.db import DatabaseManager
from database.models import NewsArticle, Entity, EntityMention

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_article_id(custom_id):
    """Extract article_id from custom_id in batch request."""
    if custom_id.startswith('article_'):
        return custom_id[8:]  # Remove 'article_' prefix
    return custom_id

def extract_article_title(input_data):
    """Extract article title from input request."""
    try:
        if 'body' in input_data and 'messages' in input_data['body']:
            messages = input_data['body']['messages']
            for message in messages:
                if message['role'] == 'user':
                    content = message['content']
                    title_match = content.split('Title: ', 1)
                    if len(title_match) > 1:
                        title = title_match[1].split('\n', 1)[0]
                        return title
    except Exception as e:
        logger.error(f"Error extracting title: {e}")
    return None

def extract_article_content(input_data):
    """Extract article content from input request."""
    try:
        if 'body' in input_data and 'messages' in input_data['body']:
            messages = input_data['body']['messages']
            for message in messages:
                if message['role'] == 'user':
                    content = message['content']
                    # Skip the title line and get the rest
                    content_parts = content.split('\n', 1)
                    if len(content_parts) > 1:
                        return content_parts[1].strip()
    except Exception as e:
        logger.error(f"Error extracting content: {e}")
    return None

def extract_entities(output_data):
    """Extract entities from OpenAI output response."""
    try:
        if 'body' in output_data and 'choices' in output_data['body']:
            choices = output_data['body']['choices']
            if choices and 'message' in choices[0] and 'content' in choices[0]['message']:
                content = choices[0]['message']['content']
                # Parse the JSON content
                entity_data = json.loads(content)
                if 'entities' in entity_data:
                    return entity_data['entities']
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
    return []

def process_batch_files(input_file, output_file, db_manager, dry_run=False):
    """Process a pair of input and output batch files."""
    logger.info(f"Processing input file: {input_file}")
    logger.info(f"Processing output file: {output_file}")
    
    input_data = []
    output_data = []
    
    # Load input data
    with open(input_file, 'r') as f:
        for line in f:
            input_data.append(json.loads(line))
    
    # Load output data
    with open(output_file, 'r') as f:
        for line in f:
            output_data.append(json.loads(line))
    
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
    
    processed_count = 0
    skipped_count = 0
    
    # Process matched data
    for custom_id, data in matched_data.items():
        if 'input' in data and 'output' in data:
            article_id = parse_article_id(custom_id)
            
            # Extract article info
            title = extract_article_title(data['input'])
            content = extract_article_content(data['input'])
            entities = extract_entities(data['output'])
            
            logger.info(f"Processing article ID: {article_id}, Title: {title}")
            logger.info(f"Found {len(entities)} entities")
            
            if not dry_run:
                # Check if article exists
                article = update_or_create_article(db_manager, article_id, title, content)
                if article:
                    # Save entities
                    save_entities(db_manager, article.id, entities)
                    processed_count += 1
                else:
                    skipped_count += 1
            else:
                logger.info(f"DRY RUN: Would process article {article_id} with {len(entities)} entities")
                processed_count += 1
    
    logger.info(f"Completed processing batch. Processed: {processed_count}, Skipped: {skipped_count}")
    return processed_count, skipped_count

def update_or_create_article(db_manager, article_id, title, content):
    """Update existing article or create a new one if it doesn't exist."""
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
            if not article.processed_at:
                article.processed_at = datetime.now()
            session.commit()
            return article
        else:
            # Create a new article record
            logger.info(f"Article {article_id} does not exist, creating new record")
            
            # Create minimal article record - will need source_id and URL in real use
            # You might want to adjust this based on your actual requirements
            new_article = NewsArticle(
                id=article_id,
                title=title,
                text=content,
                source_id=1,  # Default source ID, adjust as needed
                url=f"restored_article_{article_id}",  # Placeholder URL
                publish_date=datetime.now(),
                scraped_at=datetime.now(),
                processed_at=datetime.now(),
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

def process_batch_directory(batch_dir, db_manager, dry_run=False):
    """Process all batch files in the specified directory."""
    batch_dir = Path(batch_dir)
    
    # Get all input files
    input_files = list(batch_dir.glob('*_input.jsonl'))
    logger.info(f"Found {len(input_files)} input files in {batch_dir}")
    
    total_processed = 0
    total_skipped = 0
    
    for input_file in input_files:
        # Find matching output file
        batch_id = input_file.name.split('_input.jsonl')[0]
        output_file = batch_dir / f"{batch_id}_output.jsonl"
        
        if output_file.exists():
            processed, skipped = process_batch_files(input_file, output_file, db_manager, dry_run)
            total_processed += processed
            total_skipped += skipped
        else:
            logger.warning(f"No matching output file found for {input_file}")
    
    logger.info(f"Completed processing all batches. Total processed: {total_processed}, Total skipped: {total_skipped}")

def main():
    parser = argparse.ArgumentParser(description='Restore article analysis from OpenAI batches')
    parser.add_argument('--batch-dir', type=str, default='openai_batches',
                        help='Directory containing batch files (default: openai_batches)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without making changes to the database')
    parser.add_argument('--batch-id', type=str,
                        help='Process a specific batch ID only')
    
    args = parser.parse_args()
    
    # Create database manager
    db_manager = DatabaseManager()
    
    if args.batch_id:
        # Process specific batch
        input_file = Path(args.batch_dir) / f"{args.batch_id}_input.jsonl"
        output_file = Path(args.batch_dir) / f"{args.batch_id}_output.jsonl"
        
        if input_file.exists() and output_file.exists():
            logger.info(f"Processing single batch: {args.batch_id}")
            process_batch_files(input_file, output_file, db_manager, args.dry_run)
        else:
            logger.error(f"Batch files for ID {args.batch_id} not found")
    else:
        # Process all batches in directory
        process_batch_directory(args.batch_dir, db_manager, args.dry_run)

if __name__ == "__main__":
    main()