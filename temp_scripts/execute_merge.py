#!/usr/bin/env python3
"""
Execute entity consolidation automatically without prompting
"""

import sys
import os
from typing import Dict, List

# Add project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import the merger functions directly
from temp_scripts.merge_obvious_duplicates import find_mergeable_entities, execute_merge

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://newsbias:newsbias@localhost:5432/news_bias')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def main():
    print(f"🚀 Starting automated entity duplicate merger...")
    print(f"💧 Dry run: No")
    
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
        
        print(f"\n🔧 Proceeding automatically with {len(mergeable_entities)} entity group merges...")
        
        # Execute merges
        successful_merges = 0
        failed_merges = 0
        total_mentions_consolidated = 0
        
        for merge_plan in mergeable_entities:
            success = execute_merge(session, merge_plan, dry_run=False)
            if success:
                successful_merges += 1
                total_mentions_consolidated += sum(e['mention_count'] for e in merge_plan['entities_to_merge'])
            else:
                failed_merges += 1
            
            # Commit every 20 merges
            if successful_merges % 20 == 0:
                session.commit()
                print(f"  💾 Committed batch of merges (completed: {successful_merges})")
        
        # Final commit
        if successful_merges > 0:
            session.commit()
            print(f"\n✅ Final commit completed")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"🎯 MERGE SUMMARY")
        print(f"{'='*60}")
        print(f"  • Successful merges: {successful_merges}")
        print(f"  • Failed merges: {failed_merges}")
        print(f"  • Total mentions consolidated: {total_mentions_consolidated:,}")
        
        if successful_merges > 0:
            entities_removed = sum(len(m['entities_to_merge']) for m in mergeable_entities[:successful_merges])
            print(f"  • Duplicate entities removed: {entities_removed}")
            print(f"\n✅ Entity merging completed successfully!")
            print(f"📊 Database now has {entities_removed} fewer duplicate entities")
        
    finally:
        session.close()

if __name__ == "__main__":
    main()