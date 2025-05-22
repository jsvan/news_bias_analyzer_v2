#!/usr/bin/env python3
"""
Script to update existing NewsSource records with proper country information
from the news_sources.py configuration.
"""

import sys
import os

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import DatabaseManager
from database.models import NewsSource
from scrapers.news_sources import get_news_sources

def update_source_countries():
    """Update existing NewsSource records with country information."""
    
    # Get country mapping from configuration
    news_sources = get_news_sources()
    country_mapping = {source['name']: source.get('country', 'Unknown') for source in news_sources}
    
    print(f"Country mapping loaded: {len(country_mapping)} sources")
    for name, country in country_mapping.items():
        print(f"  {name} -> {country}")
    
    # Connect to database
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Get all news sources
        sources = session.query(NewsSource).all()
        print(f"\nFound {len(sources)} existing news sources in database")
        
        updated_count = 0
        for source in sources:
            if source.name in country_mapping:
                new_country = country_mapping[source.name]
                old_country = source.country
                
                if old_country != new_country:
                    source.country = new_country
                    print(f"Updated {source.name}: '{old_country}' -> '{new_country}'")
                    updated_count += 1
                else:
                    print(f"Unchanged {source.name}: '{old_country}'")
            else:
                print(f"No mapping found for source: {source.name}")
        
        # Commit changes
        if updated_count > 0:
            session.commit()
            print(f"\n✅ Successfully updated {updated_count} news sources")
        else:
            print(f"\n✅ No updates needed - all sources already have correct countries")
            
    except Exception as e:
        print(f"❌ Error updating sources: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    update_source_countries()