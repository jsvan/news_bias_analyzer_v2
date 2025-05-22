#!/usr/bin/env python3
"""
Debug script to check Entity and EntityMention tables for Trump-related entries.
This will help debug the 404 error in the entity endpoints.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append('/Users/jsv/Projects/news_bias_analyzer')

# Load environment variables
load_dotenv()

from database.models import Entity, EntityMention, NewsArticle, get_db_session
from sqlalchemy import func, or_

def main():
    """Query the database for Trump-related entities and debugging info."""
    
    print("=== ENTITY DATABASE DEBUG ===\n")
    
    # Get database session
    session = get_db_session()
    
    try:
        # 1. Check total entity count
        total_entities = session.query(Entity).count()
        print(f"Total entities in database: {total_entities}")
        
        # 2. Check total entity mentions count
        total_mentions = session.query(EntityMention).count()
        print(f"Total entity mentions in database: {total_mentions}")
        
        # 3. Search for Trump-related entities (case-insensitive)
        print("\n=== TRUMP-RELATED ENTITIES ===")
        trump_entities = session.query(Entity).filter(
            or_(
                Entity.name.ilike('%trump%'),
                Entity.name.ilike('%donald%')
            )
        ).all()
        
        if trump_entities:
            print(f"Found {len(trump_entities)} Trump-related entities:")
            for entity in trump_entities:
                print(f"  - ID: {entity.id}, Name: '{entity.name}', Type: '{entity.entity_type}'")
        else:
            print("No Trump-related entities found.")
        
        # 4. Check for exact matches
        print("\n=== EXACT ENTITY NAME SEARCHES ===")
        exact_searches = ['Trump', 'Donald Trump', 'Donald J. Trump', 'President Trump']
        
        for search_name in exact_searches:
            entity = session.query(Entity).filter(Entity.name == search_name).first()
            if entity:
                print(f"Found exact match for '{search_name}': ID {entity.id}, Type: {entity.entity_type}")
            else:
                print(f"No exact match found for '{search_name}'")
        
        # 5. Show some sample entities to understand naming patterns
        print("\n=== SAMPLE ENTITIES (first 20) ===")
        sample_entities = session.query(Entity).limit(20).all()
        for entity in sample_entities:
            print(f"  - ID: {entity.id}, Name: '{entity.name}', Type: '{entity.entity_type}'")
        
        # 6. Check entity mentions for Trump entities
        if trump_entities:
            print("\n=== TRUMP ENTITY MENTIONS ===")
            for entity in trump_entities:
                mentions = session.query(EntityMention).filter(
                    EntityMention.entity_id == entity.id
                ).all()
                print(f"Entity '{entity.name}' (ID: {entity.id}) has {len(mentions)} mentions")
                
                if mentions:
                    # Show first few mentions with scores
                    for mention in mentions[:3]:
                        print(f"  - Article: {mention.article_id}, Power: {mention.power_score}, Moral: {mention.moral_score}")
        
        # 7. Check entity types distribution
        print("\n=== ENTITY TYPES DISTRIBUTION ===")
        type_counts = session.query(
            Entity.entity_type, 
            func.count(Entity.id).label('count')
        ).group_by(Entity.entity_type).order_by(func.count(Entity.id).desc()).all()
        
        for entity_type, count in type_counts:
            print(f"  {entity_type}: {count} entities")
        
        # 8. Check for entities with 'person' type that might include Trump
        print("\n=== PERSON ENTITIES (first 10) ===")
        person_entities = session.query(Entity).filter(
            Entity.entity_type == 'person'
        ).limit(10).all()
        
        for entity in person_entities:
            print(f"  - ID: {entity.id}, Name: '{entity.name}'")
        
        # 9. Check recent articles to see if they have entity analysis
        print("\n=== RECENT ARTICLES WITH ENTITY ANALYSIS ===")
        recent_articles = session.query(NewsArticle).filter(
            NewsArticle.processed_at.isnot(None)
        ).order_by(NewsArticle.processed_at.desc()).limit(5).all()
        
        for article in recent_articles:
            entity_count = session.query(EntityMention).filter(
                EntityMention.article_id == article.id
            ).count()
            print(f"  - Article {article.id}: {entity_count} entity mentions, processed at {article.processed_at}")
        
    except Exception as e:
        print(f"Error querying database: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        session.close()

if __name__ == "__main__":
    main()