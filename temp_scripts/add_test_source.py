# Test script to add a sample news source
from database.db import DatabaseManager
from database.models import NewsSource

def go():
    """Add a test news source to the database."""
    print("Adding test news source to the database...")
    
    # Create a database manager
    db_manager = DatabaseManager()
    
    # Get a session
    session = db_manager.get_session()
    
    try:
        # Check if the test source already exists
        existing = session.query(NewsSource).filter_by(name="Test News Source").first()
        
        if existing:
            print(f"Test source already exists: {existing.name} ({existing.id})")
            return
        
        # Create a new test news source
        test_source = NewsSource(
            name="Test News Source",
            base_url="https://test-news-source.example.com",
            country="Test Country",
            language="en"
        )
        
        # Add to the session and commit
        session.add(test_source)
        session.commit()
        
        print(f"Successfully added test news source with ID: {test_source.id}")
        
    except Exception as e:
        print(f"Error adding test source: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    go()