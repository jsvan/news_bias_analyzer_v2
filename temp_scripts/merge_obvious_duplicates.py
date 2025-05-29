#!/usr/bin/env python3
"""
Merge obvious entity duplicates based on exact name matches with compatible types.

This script focuses on the most obvious cases like:
- Donald Trump (person) + Donald Trump (political_leader)
- Russia (country) + Russia (sovereign_state)
- United States (country) + United States (sovereign_state)
"""

import sys
import os
from typing import Dict, List, Tuple

# Add project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database.models import Entity, EntityMention

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://newsbias:newsbias@localhost:5432/news_bias')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_compatible_type_groups() -> List[List[str]]:
    """Define groups of compatible entity types that can be safely merged"""
    return [
        ['person', 'political_leader'],
        ['country', 'sovereign_state'],
        ['organization', 'company'],
        ['location', 'place']
    ]


def find_mergeable_entities(session) -> List[Dict]:
    """Find entities that have exact name matches with compatible types"""
    
    # Get entities with exact name duplicates and their mention counts
    query = text("""
        SELECT 
            e.id,
            e.name,
            e.entity_type,
            COUNT(em.id) as mention_count
        FROM entities e
        LEFT JOIN entity_mentions em ON e.id = em.entity_id
        WHERE e.name IN (
            SELECT name 
            FROM entities 
            GROUP BY name 
            HAVING COUNT(DISTINCT entity_type) > 1
        )
        GROUP BY e.id, e.name, e.entity_type
        ORDER BY e.name, mention_count DESC
    """)
    
    results = session.execute(query).fetchall()
    
    # Group by name
    entities_by_name = {}
    for row in results:
        name = row.name
        if name not in entities_by_name:
            entities_by_name[name] = []
        entities_by_name[name].append({
            'id': row.id,
            'name': row.name,
            'entity_type': row.entity_type,
            'mention_count': row.mention_count
        })
    
    # Find mergeable groups
    compatible_groups = get_compatible_type_groups()
    mergeable_entities = []
    
    for name, entity_list in entities_by_name.items():
        if len(entity_list) < 2:
            continue
            
        # Group entities by compatible types
        for compatible_types in compatible_groups:
            compatible_entities = [
                e for e in entity_list 
                if e['entity_type'] in compatible_types
            ]
            
            if len(compatible_entities) >= 2:
                # Sort by mention count (descending) to pick the "official" entity
                compatible_entities.sort(key=lambda x: x['mention_count'], reverse=True)
                
                official_entity = compatible_entities[0]
                entities_to_merge = compatible_entities[1:]
                
                mergeable_entities.append({
                    'name': name,
                    'types': [e['entity_type'] for e in compatible_entities],
                    'official_entity': official_entity,
                    'entities_to_merge': entities_to_merge,
                    'total_mentions': sum(e['mention_count'] for e in compatible_entities)
                })
    
    return mergeable_entities


def execute_merge(session, merge_plan: Dict, dry_run: bool = True) -> bool:
    """Execute a single merge operation"""
    
    official_entity = merge_plan['official_entity']
    entities_to_merge = merge_plan['entities_to_merge']
    
    print(f"\n🔄 {'DRY RUN: ' if dry_run else ''}Merging {merge_plan['name']}")
    print(f"  🎯 Keep: {official_entity['entity_type']} (ID: {official_entity['id']}, {official_entity['mention_count']} mentions)")
    
    total_mentions_moved = 0
    
    for entity in entities_to_merge:
        print(f"  ➡️  Merge: {entity['entity_type']} (ID: {entity['id']}, {entity['mention_count']} mentions)")
        
        if not dry_run:
            try:
                # Update entity mentions to point to official entity
                update_query = text("""
                    UPDATE entity_mentions 
                    SET entity_id = :official_id 
                    WHERE entity_id = :merge_id
                """)
                
                result = session.execute(update_query, {
                    'official_id': official_entity['id'],
                    'merge_id': entity['id']
                })
                
                mentions_updated = result.rowcount
                print(f"    ✅ Updated {mentions_updated} mentions")
                
                # Delete the duplicate entity
                delete_query = text("DELETE FROM entities WHERE id = :entity_id")
                session.execute(delete_query, {'entity_id': entity['id']})
                print(f"    🗑️  Removed duplicate entity")
                
                total_mentions_moved += mentions_updated
                
            except Exception as e:
                print(f"    ❌ Error: {e}")
                return False
        else:
            print(f"    🔄 Would update {entity['mention_count']} mentions and remove entity")
            total_mentions_moved += entity['mention_count']
    
    print(f"  ✅ Total mentions consolidated: {total_mentions_moved}")
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Merge obvious entity duplicates')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be done without making changes')
    parser.add_argument('--execute', action='store_true',
                       help='Actually perform the merges (overrides --dry-run)')
    args = parser.parse_args()
    
    # If --execute is specified, turn off dry-run
    dry_run = not args.execute
    
    print(f"🚀 Starting obvious entity duplicate merger...")
    print(f"💧 Dry run: {'Yes' if dry_run else 'No'}")
    
    session = Session()
    try:
        # Find mergeable entities
        print(f"\n🔍 Finding entities with exact name matches and compatible types...")
        mergeable_entities = find_mergeable_entities(session)
        
        if not mergeable_entities:
            print(f"ℹ️  No mergeable entities found")
            return
        
        print(f"\n📋 Found {len(mergeable_entities)} mergeable entity groups:")
        
        # Show preview
        for i, merge_plan in enumerate(mergeable_entities[:10], 1):
            print(f"  {i}. {merge_plan['name']} ({', '.join(merge_plan['types'])})")
            print(f"     Total mentions: {merge_plan['total_mentions']}")
        
        if len(mergeable_entities) > 10:
            print(f"     ... and {len(mergeable_entities) - 10} more")
        
        # Confirm execution (unless dry run)
        if not dry_run:
            try:
                response = input(f"\n❓ Proceed with merging {len(mergeable_entities)} entity groups? (y/N): ")
                if response.lower() != 'y':
                    print("❌ Cancelled by user")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\n❌ Cancelled by user")
                return
        else:
            print(f"\n🔄 DRY RUN: Would proceed to merge {len(mergeable_entities)} entity groups")
        
        # Execute merges
        successful_merges = 0
        failed_merges = 0
        total_mentions_consolidated = 0
        
        for merge_plan in mergeable_entities:
            success = execute_merge(session, merge_plan, dry_run)
            if success:
                successful_merges += 1
                total_mentions_consolidated += sum(e['mention_count'] for e in merge_plan['entities_to_merge'])
            else:
                failed_merges += 1
            
            # Commit every 10 merges
            if not dry_run and successful_merges % 10 == 0:
                session.commit()
                print(f"  💾 Committed batch of merges")
        
        # Final commit
        if not dry_run and successful_merges > 0:
            session.commit()
            print(f"\n✅ Final commit completed")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"🎯 MERGE {'DRY RUN ' if dry_run else ''}SUMMARY")
        print(f"{'='*60}")
        print(f"  • Successful merges: {successful_merges}")
        print(f"  • Failed merges: {failed_merges}")
        print(f"  • Total mentions consolidated: {total_mentions_consolidated:,}")
        
        if dry_run:
            print(f"\n💡 This was a dry run. To execute for real, run with --execute flag")
        else:
            print(f"\n✅ Entity merging completed successfully!")
            entities_removed = sum(len(m['entities_to_merge']) for m in mergeable_entities)
            print(f"📊 Database now has {entities_removed} fewer duplicate entities")
        
    finally:
        session.close()


if __name__ == "__main__":
    main()