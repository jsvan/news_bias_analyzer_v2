#!/usr/bin/env python3
"""
Check what entities are in the database, specifically looking for Trump.
"""

import sys
import os

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import DatabaseManager
from database.models import Entity, EntityMention, NewsArticle, NewsSource
from sqlalchemy import func

def main():
    # Initialize database connection
    database_url = os.getenv("DATABASE_URL", "sqlite:///./news_bias.db")
    db_manager = DatabaseManager(database_url)
    
    with db_manager.get_session() as session:
        print("=== CHECKING ENTITIES IN DATABASE ===\n")
        
        # 1. Check total entity count
        total_entities = session.query(Entity).count()
        print(f"Total entities in database: {total_entities}")
        
        # 2. Look for Trump specifically
        trump_entities = session.query(Entity).filter(
            func.lower(Entity.name).like('%trump%')
        ).all()
        
        print(f"\nEntities containing 'trump': {len(trump_entities)}")
        for entity in trump_entities:
            print(f"  - {entity.name} (type: {entity.entity_type}, id: {entity.id})")
        
        # 3. Check for exact matches
        exact_trump = session.query(Entity).filter(
            func.lower(Entity.name) == 'trump'
        ).first()
        
        if exact_trump:
            print(f"\nExact 'Trump' entity found: {exact_trump.name} (id: {exact_trump.id})")
        else:
            print("\nNo exact 'Trump' entity found")
            
        donald_trump = session.query(Entity).filter(
            func.lower(Entity.name) == 'donald trump'
        ).first()
        
        if donald_trump:
            print(f"Exact 'Donald Trump' entity found: {donald_trump.name} (id: {donald_trump.id})")
        else:
            print("No exact 'Donald Trump' entity found")
        
        # 4. Check entity mentions for any Trump entity
        if trump_entities:
            print(f"\n=== ENTITY MENTIONS FOR TRUMP ENTITIES ===")
            for entity in trump_entities:
                mention_count = session.query(EntityMention).filter(
                    EntityMention.entity_id == entity.id
                ).count()
                
                power_mentions = session.query(EntityMention).filter(
                    EntityMention.entity_id == entity.id,
                    EntityMention.power_score.isnot(None)
                ).count()
                
                moral_mentions = session.query(EntityMention).filter(
                    EntityMention.entity_id == entity.id,
                    EntityMention.moral_score.isnot(None)
                ).count()
                
                print(f"  {entity.name}:")
                print(f"    Total mentions: {mention_count}")
                print(f"    Power score mentions: {power_mentions}")
                print(f"    Moral score mentions: {moral_mentions}")
        
        # 5. Show top 10 entities by mention count
        print(f"\n=== TOP 10 ENTITIES BY MENTION COUNT ===")
        top_entities = session.query(
            Entity.name,
            Entity.entity_type,
            func.count(EntityMention.id).label('mention_count')
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).group_by(
            Entity.id, Entity.name, Entity.entity_type
        ).order_by(
            func.count(EntityMention.id).desc()
        ).limit(10).all()
        
        for i, (name, entity_type, count) in enumerate(top_entities, 1):
            print(f"  {i}. {name} ({entity_type}): {count} mentions")
        
        # 6. Check if there are any entities with power/moral scores
        entities_with_scores = session.query(Entity).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).filter(
            EntityMention.power_score.isnot(None),
            EntityMention.moral_score.isnot(None)
        ).distinct().count()
        
        print(f"\nEntities with sentiment scores: {entities_with_scores}")

if __name__ == "__main__":
    main()