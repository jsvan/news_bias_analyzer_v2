#!/usr/bin/env python3
"""
Entity Deduplication Script

Merges duplicate entities in the database by:
1. Finding entities with the same name but different types
2. Choosing the best canonical entity (highest mention count)
3. Merging all entity mentions to the canonical entity
4. Updating entity records to point to canonical entity
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_session
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EntityDeduplicator:
    def __init__(self, dry_run=True):
        self.session = get_session()
        self.dry_run = dry_run
        
    def get_duplicate_groups(self, min_total_mentions=20):
        """Find groups of entities with the same name but different types."""
        query = text('''
            SELECT e.name, 
                   array_agg(e.id ORDER BY COALESCE(em.mention_count, 0) DESC) as ids,
                   array_agg(e.entity_type ORDER BY COALESCE(em.mention_count, 0) DESC) as types,
                   array_agg(COALESCE(em.mention_count, 0) ORDER BY COALESCE(em.mention_count, 0) DESC) as mentions,
                   SUM(COALESCE(em.mention_count, 0)) as total_mentions
            FROM entities e
            LEFT JOIN (
                SELECT entity_id, COUNT(*) as mention_count 
                FROM entity_mentions 
                GROUP BY entity_id
            ) em ON e.id = em.entity_id
            GROUP BY e.name
            HAVING COUNT(DISTINCT e.entity_type) > 1 AND SUM(COALESCE(em.mention_count, 0)) >= :min_mentions
            ORDER BY SUM(COALESCE(em.mention_count, 0)) DESC
        ''')
        
        result = self.session.execute(query, {"min_mentions": min_total_mentions})
        return result.fetchall()
    
    def choose_canonical_entity(self, entity_group):
        """Choose the best entity to be the canonical one (highest mentions)."""
        name, ids, types, mentions, total = entity_group
        
        # Choose entity with most mentions as canonical
        canonical_id = ids[0]
        canonical_type = types[0]
        canonical_mentions = mentions[0]
        
        # For important entities, prefer certain types over others
        type_preferences = {
            'sovereign_state': 10,  # Countries should be sovereign_state
            'political_leader': 8,  # Politicians should be political_leader  
            'person': 6,            # General people
            'organization': 4,      # Organizations
            'international_institution': 3,
            'political_organization': 2,
        }
        
        # Re-evaluate if we have a preferred type with substantial mentions
        for i, (entity_id, entity_type, mention_count) in enumerate(zip(ids, types, mentions)):
            preference_score = type_preferences.get(entity_type, 1)
            # If this type is much more preferred and has at least 20% of max mentions
            if (preference_score > type_preferences.get(canonical_type, 1) and 
                mention_count >= canonical_mentions * 0.2):
                canonical_id = entity_id
                canonical_type = entity_type
                canonical_mentions = mention_count
                break
        
        logger.info(f"Canonical entity for '{name}': ID {canonical_id} ({canonical_type}) with {canonical_mentions} mentions")
        return canonical_id, canonical_type
    
    def merge_entity_group(self, entity_group):
        """Merge a group of duplicate entities into one canonical entity."""
        name, ids, types, mentions, total = entity_group
        canonical_id, canonical_type = self.choose_canonical_entity(entity_group)
        
        duplicate_ids = [id for id in ids if id != canonical_id]
        
        if not duplicate_ids:
            logger.info(f"No duplicates to merge for '{name}'")
            return 0
            
        logger.info(f"Merging {len(duplicate_ids)} duplicates for '{name}' into entity {canonical_id}")
        
        merged_count = 0
        
        for duplicate_id in duplicate_ids:
            # Count mentions to be moved
            mention_count = self.session.execute(text(
                "SELECT COUNT(*) FROM entity_mentions WHERE entity_id = :entity_id"
            ), {"entity_id": duplicate_id}).scalar()
            
            if mention_count > 0:
                logger.info(f"  Moving {mention_count} mentions from entity {duplicate_id} to {canonical_id}")
                
                if not self.dry_run:
                    # Move all entity mentions to canonical entity
                    self.session.execute(text(
                        "UPDATE entity_mentions SET entity_id = :canonical_id WHERE entity_id = :duplicate_id"
                    ), {"canonical_id": canonical_id, "duplicate_id": duplicate_id})
                
                merged_count += mention_count
            
            # Set canonical_id for the duplicate entity
            if not self.dry_run:
                self.session.execute(text(
                    "UPDATE entities SET canonical_id = :canonical_id WHERE id = :duplicate_id"
                ), {"canonical_id": canonical_id, "duplicate_id": duplicate_id})
                
            logger.info(f"  Marked entity {duplicate_id} as duplicate of {canonical_id}")
        
        if not self.dry_run:
            self.session.commit()
            
        return merged_count
    
    def deduplicate_all(self, min_mentions=20):
        """Deduplicate all entity groups."""
        duplicate_groups = self.get_duplicate_groups(min_mentions)
        
        logger.info(f"Found {len(duplicate_groups)} duplicate groups to process")
        
        total_merged = 0
        entities_merged = 0
        
        for group in duplicate_groups:
            name, ids, types, mentions, total = group
            logger.info(f"\n--- Processing: {name} (total: {total} mentions) ---")
            logger.info(f"    Types: {types}")
            logger.info(f"    Mentions: {mentions}")
            
            merged = self.merge_entity_group(group)
            total_merged += merged
            entities_merged += len(ids) - 1  # All but canonical
            
        logger.info(f"\n=== DEDUPLICATION SUMMARY ===")
        logger.info(f"Groups processed: {len(duplicate_groups)}")
        logger.info(f"Entities merged: {entities_merged}")
        logger.info(f"Mentions moved: {total_merged}")
        logger.info(f"Dry run: {self.dry_run}")
        
        return entities_merged, total_merged
    
    def close(self):
        """Close database session."""
        self.session.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Deduplicate entities in the database')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Run in dry-run mode (default: True)')
    parser.add_argument('--execute', action='store_true',
                       help='Actually execute the merges (overrides dry-run)')
    parser.add_argument('--min-mentions', type=int, default=20,
                       help='Minimum total mentions for a group to be processed')
    
    args = parser.parse_args()
    
    # Override dry_run if --execute is specified
    dry_run = args.dry_run and not args.execute
    
    if not dry_run:
        response = input("This will modify the database. Are you sure? (type 'yes' to confirm): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    deduplicator = EntityDeduplicator(dry_run=dry_run)
    
    try:
        entities_merged, mentions_moved = deduplicator.deduplicate_all(args.min_mentions)
        
        if dry_run:
            print(f"\nDRY RUN COMPLETE")
            print(f"Would merge {entities_merged} entities and move {mentions_moved} mentions")
            print(f"Run with --execute to actually perform the merges")
        else:
            print(f"\nDEDUPLICATION COMPLETE")
            print(f"Merged {entities_merged} entities and moved {mentions_moved} mentions")
            
    finally:
        deduplicator.close()

if __name__ == "__main__":
    main()