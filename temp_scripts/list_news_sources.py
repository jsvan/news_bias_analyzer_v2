# Script to list all news sources in the database
from database.db import DatabaseManager
from database.models import NewsSource

def go():
    """List all news sources in the database."""
    print("Listing all news sources in the database...")
    
    # Create a database manager
    db_manager = DatabaseManager()
    
    # Get all news sources
    sources = db_manager.get_sources()
    
    if not sources:
        print("No news sources found in the database.")
        return
    
    print(f"Found {len(sources)} news sources:")
    print("-" * 50)
    print(f"{'ID':<5} {'Name':<30} {'Country':<15} {'Language':<10}")
    print("-" * 50)
    
    for source in sources:
        print(f"{source.id:<5} {source.name[:30]:<30} {source.country or 'N/A':<15} {source.language or 'N/A':<10}")


if __name__ == "__main__":
    go()