"""
Database manager for the News Bias Analyzer.
Handles database connections and queries.
"""
import os
import logging
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import models
from database.models import NewsArticle, NewsSource, Entity, EntityMention, get_db_connection, compress_article_text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and operations for the News Bias Analyzer."""
    
    def __init__(self, db_url=None):
        """
        Initialize the database manager.
        
        Args:
            db_url: Optional database URL. If None, uses environment variable.
        """
        if db_url:
            self.engine = create_engine(db_url)
        else:
            self.engine = get_db_connection()
            
        self.Session = sessionmaker(bind=self.engine)
        
    def get_session(self):
        """Get a new database session."""
        return self.Session()
    
    def get_articles(self, limit=None, only_unprocessed=False, order_by='publish_date', 
                    days_ago=None, source_id=None):
        """
        Get articles from the database.
        
        Args:
            limit: Maximum number of articles to return
            only_unprocessed: If True, only return articles that haven't been processed
            order_by: Column to order results by ('publish_date', 'scraped_at', etc.)
            days_ago: Only return articles from this many days ago
            source_id: Only return articles from this source
            
        Returns:
            List of NewsArticle objects
        """
        session = self.get_session()
        try:
            query = session.query(NewsArticle)
            
            # Apply filters
            if only_unprocessed:
                query = query.filter(NewsArticle.processed_at.is_(None))
                
            if days_ago:
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
                query = query.filter(NewsArticle.publish_date >= cutoff_date)
                
            if source_id:
                query = query.filter(NewsArticle.source_id == source_id)
            
            # Apply ordering
            if order_by == 'publish_date':
                query = query.order_by(NewsArticle.publish_date.desc())
            elif order_by == 'scraped_at':
                query = query.order_by(NewsArticle.scraped_at.desc())
            
            # Apply limit
            if limit:
                query = query.limit(limit)
                
            return query.all()
        finally:
            session.close()
    
    def save_entity_analysis(self, article_id, entity_data):
        """
        Save entity analysis results to the database.
        
        Args:
            article_id: ID of the article
            entity_data: List of entity data dicts with sentiment scores
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session()
        try:
            # Get the article
            article = session.query(NewsArticle).filter_by(id=article_id).first()
            
            if not article:
                logger.error(f"Article not found: {article_id}")
                return False
            
            # Process each entity
            for entity_info in entity_data:
                # Get or create entity
                entity_name = entity_info.get('name', '')
                entity_type = entity_info.get('type', '')
                
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
                    article_id=article.id,
                    power_score=entity_info.get('power_score', 0),
                    moral_score=entity_info.get('moral_score', 0),
                    mentions=entity_info.get('quotes', [])
                )
                session.add(mention)
            
            # Mark article as processed
            article.processed_at = datetime.datetime.now()

            # Commit changes
            session.commit()

            # Compress article text after successful analysis
            compression_result = compress_article_text(session, article.id)
            if compression_result:
                logger.info(f"Compressed text for article {article.id}")
            else:
                logger.warning(f"Failed to compress text for article {article.id}")

            return True
            
        except Exception as e:
            logger.error(f"Error saving entity analysis: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_sources(self):
        """
        Get all news sources from the database.
        
        Returns:
            List of NewsSource objects
        """
        session = self.get_session()
        try:
            return session.query(NewsSource).all()
        finally:
            session.close()
    
    def get_entities(self, limit=None):
        """
        Get entities from the database.
        
        Args:
            limit: Maximum number of entities to return
            
        Returns:
            List of Entity objects
        """
        session = self.get_session()
        try:
            query = session.query(Entity)
            
            if limit:
                query = query.limit(limit)
                
            return query.all()
        finally:
            session.close()
    
    def get_entity_mentions(self, entity_id=None, article_id=None, limit=None):
        """
        Get entity mentions from the database.
        
        Args:
            entity_id: Optional entity ID to filter by
            article_id: Optional article ID to filter by
            limit: Maximum number of mentions to return
            
        Returns:
            List of EntityMention objects
        """
        session = self.get_session()
        try:
            query = session.query(EntityMention)
            
            if entity_id:
                query = query.filter(EntityMention.entity_id == entity_id)
                
            if article_id:
                query = query.filter(EntityMention.article_id == article_id)
            
            if limit:
                query = query.limit(limit)
                
            return query.all()
        finally:
            session.close()
            
    def get_article_by_id(self, article_id):
        """
        Get an article by its ID.
        
        Args:
            article_id: The ID of the article
            
        Returns:
            NewsArticle object or None if not found
        """
        session = self.get_session()
        try:
            return session.query(NewsArticle).filter_by(id=article_id).first()
        finally:
            session.close()
            
    def get_article_by_url(self, url):
        """
        Get an article by its URL.
        
        Args:
            url: The URL of the article
            
        Returns:
            NewsArticle object or None if not found
        """
        session = self.get_session()
        try:
            return session.query(NewsArticle).filter_by(url=url).first()
        finally:
            session.close()