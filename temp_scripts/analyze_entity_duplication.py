#!/usr/bin/env python3
"""
Analyze entity duplication patterns to determine if entity types are useful or just creating noise
"""

import sys
import os
from collections import defaultdict, Counter

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.db import get_session
from database.models import Entity, EntityMention
from sqlalchemy import func, desc

def analyze_entity_duplication():
    """Analyze entity duplication patterns in the database"""
    print("🔍 Analyzing entity duplication patterns...")
    
    session = get_session()
    if not session:
        print("❌ Could not connect to database")
        return
    
    try:
        # 1. Find entities with the same name but different types
        print("\n📊 Entities with multiple types:")
        print("=" * 60)
        
        # Query for entities grouped by name, showing different types
        name_groups = session.query(
            Entity.name,
            func.array_agg(Entity.entity_type).label('types'),
            func.array_agg(Entity.id).label('ids'),
            func.count(Entity.id).label('type_count')
        ).group_by(Entity.name).having(
            func.count(Entity.id) > 1
        ).order_by(desc('type_count')).limit(20).all()
        
        print(f"Found {len(name_groups)} entity names with multiple types")
        print("\nTop duplicated entities:")
        
        for name, types, ids, count in name_groups[:10]:
            print(f"\n'{name}' ({count} types):")
            
            # Get mention counts for each type
            for i, entity_id in enumerate(ids):
                entity_type = types[i] if i < len(types) else "unknown"
                mention_count = session.query(func.count(EntityMention.id)).filter(
                    EntityMention.entity_id == entity_id
                ).scalar()
                print(f"  - {entity_type}: {mention_count} mentions (ID: {entity_id})")
        
        # 2. Analyze specific cases to see if types are meaningful
        print("\n\n🔍 Detailed analysis of specific entities:")
        print("=" * 60)
        
        # Look at some specific examples
        examples = [
            "Donald Trump",
            "Vladimir Putin", 
            "United States",
            "Russia",
            "Israel",
            "European Union",
            "Apple",
            "Tesla"
        ]
        
        for entity_name in examples:
            entities = session.query(Entity).filter(
                func.lower(Entity.name) == entity_name.lower()
            ).all()
            
            if len(entities) > 1:
                print(f"\n'{entity_name}':")
                total_mentions = 0
                for entity in entities:
                    mention_count = session.query(func.count(EntityMention.id)).filter(
                        EntityMention.entity_id == entity.id
                    ).scalar()
                    total_mentions += mention_count
                    print(f"  - {entity.entity_type}: {mention_count} mentions")
                print(f"  Total: {total_mentions} mentions across {len(entities)} types")
        
        # 3. Count entity types to see patterns
        print("\n\n📈 Entity type distribution:")
        print("=" * 60)
        
        type_counts = session.query(
            Entity.entity_type,
            func.count(Entity.id).label('count')
        ).group_by(Entity.entity_type).order_by(desc('count')).limit(20).all()
        
        print("Top entity types:")
        for entity_type, count in type_counts:
            print(f"  {entity_type}: {count} entities")
        
        # 4. Check for obvious redundant types
        print("\n\n🔍 Potentially redundant type pairs:")
        print("=" * 60)
        
        # Look for entities that appear as both generic and specific types
        redundant_patterns = [
            ("person", "political_leader"),
            ("person", "business_leader"), 
            ("organization", "political_organization"),
            ("organization", "major_corporation"),
            ("country", "sovereign_state"),
            ("individual", "person")
        ]
        
        for generic_type, specific_type in redundant_patterns:
            # Find entities that appear as both types
            generic_names = set(row[0] for row in session.query(Entity.name).filter(
                Entity.entity_type == generic_type
            ).all())
            
            specific_names = set(row[0] for row in session.query(Entity.name).filter(
                Entity.entity_type == specific_type  
            ).all())
            
            overlap = generic_names & specific_names
            if overlap:
                print(f"\n{generic_type} + {specific_type}: {len(overlap)} overlapping entities")
                for name in list(overlap)[:5]:  # Show first 5 examples
                    print(f"  - {name}")
                if len(overlap) > 5:
                    print(f"  ... and {len(overlap) - 5} more")
        
        # 5. Calculate total duplication impact
        print("\n\n💡 Duplication impact analysis:")
        print("=" * 60)
        
        total_entities = session.query(func.count(Entity.id)).scalar()
        unique_names = session.query(func.count(func.distinct(Entity.name))).scalar()
        
        print(f"Total entities: {total_entities}")
        print(f"Unique names: {unique_names}")
        print(f"Duplication factor: {total_entities / unique_names:.2f}x")
        print(f"Potential savings: {total_entities - unique_names} entities ({(total_entities - unique_names) / total_entities * 100:.1f}%)")
        
        # 6. Recommendation
        print("\n\n💭 Analysis and Recommendations:")
        print("=" * 60)
        
        # Check if there are cases where types actually matter
        meaningful_cases = 0
        total_duplicated_names = len(name_groups)
        
        print(f"Found {total_duplicated_names} entity names with multiple types")
        print(f"Average types per duplicated name: {sum(row.type_count for row in name_groups) / len(name_groups):.1f}")
        
        return {
            'total_entities': total_entities,
            'unique_names': unique_names,
            'duplicated_names': total_duplicated_names,
            'duplication_factor': total_entities / unique_names
        }
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        session.close()

def provide_recommendations(stats):
    """Provide recommendations based on the analysis"""
    print("\n🎯 RECOMMENDATIONS:")
    print("=" * 60)
    
    if stats['duplication_factor'] > 1.5:
        print("✅ CONSOLIDATE ENTITY TYPES")
        print("   - High duplication factor suggests entity types are creating noise")
        print("   - Consider using only entity names, ignoring types")
        print("   - Or map similar types together (person + political_leader = person)")
        
    print(f"\n📊 Key metrics:")
    print(f"   - {stats['duplicated_names']} names have multiple types")
    print(f"   - {stats['duplication_factor']:.1f}x duplication factor")
    print(f"   - Could reduce entities by {stats['total_entities'] - stats['unique_names']}")
    
    print(f"\n🔧 Implementation options:")
    print(f"   1. Ignore entity_type completely, group by name only")
    print(f"   2. Create type mapping to consolidate similar types")
    print(f"   3. Use entity_mapper to deduplicate programmatically")

if __name__ == "__main__":
    print("🚀 Starting entity duplication analysis...\n")
    
    stats = analyze_entity_duplication()
    
    if stats:
        provide_recommendations(stats)
        print("\n🎉 Analysis complete!")
    else:
        print("\n❌ Analysis failed!")