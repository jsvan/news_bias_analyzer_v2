"""
Database services layer providing clean abstractions for data access.

This module implements the service pattern to encapsulate business logic
and provide consistent database operations across the application.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Entity, EntityMention, NewsArticle
from .repositories import RepositoryFactory
from utils.entity_mapper import normalize_entity_name

logger = logging.getLogger(__name__)


class EntityService:
    """Service for managing entity and entity mention operations."""
    
    def __init__(self, session: Session):
        self.session = session
        self.repos = RepositoryFactory(session)
    
    def get_or_create_entity(self, entity_name: str, entity_type: str) -> Entity:
        """
        Get existing entity or create new one using normalized name matching.
        
        Args:
            entity_name: Raw entity name from analysis
            entity_type: Entity type (person, organization, etc.)
            
        Returns:
            Entity object (existing or newly created)
            
        Note:
            Uses case-insensitive name matching and entity normalization.
            Flushes session to ensure ID is available immediately.
        """
        if not entity_name or not entity_type:
            raise ValueError("Entity name and type are required")
        
        # Normalize entity name for deduplication
        normalized_name = normalize_entity_name(entity_name)
        
        # Look for existing entity by normalized name
        entity = self.repos.entities.find_by_normalized_name(normalized_name)
        
        if not entity:
            # Create new entity with normalized name
            entity = self.repos.entities.create(normalized_name, entity_type)
            self.session.flush()  # Ensure ID is available for immediate use
            logger.debug(f"Created new entity: {normalized_name} ({entity_type})")
        
        return entity
    
    def create_entity_mention(
        self, 
        entity: Entity, 
        article_id: str, 
        power_score: float, 
        moral_score: float, 
        mentions: List[Dict[str, Any]] = None,
        mention_date: datetime = None
    ) -> EntityMention:
        """
        Create an entity mention linking entity to article with sentiment scores.
        
        Args:
            entity: Entity object
            article_id: Article ID
            power_score: Power dimension score (-2 to +2)
            moral_score: Moral dimension score (-2 to +2)
            mentions: List of mention contexts
            mention_date: When the mention occurred (defaults to now)
            
        Returns:
            EntityMention object
        """
        return self.repos.entity_mentions.create(
            entity_id=entity.id,
            article_id=article_id,
            power_score=self._sanitize_score(power_score),
            moral_score=self._sanitize_score(moral_score),
            mentions=mentions or [],
            created_at=mention_date or datetime.utcnow()
        )
    
    def process_article_entities(
        self, 
        article_id: str, 
        entity_data_list: List[Dict[str, Any]],
        article_date: datetime = None
    ) -> List[Tuple[Entity, EntityMention]]:
        """
        Process all entities for an article in a single transaction.
        
        Args:
            article_id: Article ID
            entity_data_list: List of entity data from analysis
            article_date: Article publication date
            
        Returns:
            List of (Entity, EntityMention) tuples created
            
        Raises:
            ValueError: If entity data is invalid
        """
        results = []
        
        for entity_data in entity_data_list:
            # Validate entity data
            entity_name = entity_data.get('entity') or entity_data.get('name')
            entity_type = entity_data.get('entity_type')
            
            if not entity_name or not entity_type:
                logger.warning(f"Skipping invalid entity data: {entity_data}")
                continue
            
            # Create or get entity
            entity = self.get_or_create_entity(entity_name, entity_type)
            
            # Create entity mention
            mention = self.create_entity_mention(
                entity=entity,
                article_id=article_id,
                power_score=entity_data.get('power_score', 0),
                moral_score=entity_data.get('moral_score', 0),
                mentions=entity_data.get('mentions', []),
                mention_date=article_date
            )
            
            results.append((entity, mention))
        
        logger.debug(f"Processed {len(results)} entities for article {article_id}")
        return results
    
    def get_entity_mentions_for_article(self, article_id: str) -> List[Tuple[Entity, EntityMention]]:
        """Get all entity mentions for a specific article."""
        return self.repos.entity_mentions.find_with_entities_by_article_id(article_id)
    
    def check_article_has_mentions(self, article_id: str) -> bool:
        """Check if an article already has entity mentions."""
        return self.repos.entity_mentions.count_by_article_id(article_id) > 0
    
    @staticmethod
    def _sanitize_score(score: Any) -> float:
        """Sanitize and validate sentiment scores."""
        try:
            score = float(score) if score is not None else 0.0
            # Clamp to valid range
            return max(-2.0, min(2.0, score))
        except (ValueError, TypeError):
            logger.warning(f"Invalid score value: {score}, defaulting to 0.0")
            return 0.0


class ArticleService:
    """Service for managing article operations."""
    
    def __init__(self, session: Session):
        self.session = session
        self.repos = RepositoryFactory(session)
    
    def get_article_by_id(self, article_id: str) -> Optional[NewsArticle]:
        """Get article by ID."""
        return self.repos.articles.find_by_id(article_id)
    
    def mark_article_completed(
        self, 
        article_id: str, 
        processed_at: datetime = None,
        hotelling_t2_score: float = None
    ) -> bool:
        """
        Mark article as completed with optional metrics.
        
        Args:
            article_id: Article ID
            processed_at: Processing timestamp (defaults to now)
            hotelling_t2_score: Statistical extremeness score
            
        Returns:
            True if successful, False otherwise
        """
        success = self.repos.articles.update_status(
            article_id, "completed", processed_at or datetime.utcnow()
        )
        
        if success and hotelling_t2_score is not None:
            self.repos.articles.update_hotelling_score(article_id, hotelling_t2_score)
        
        if not success:
            logger.error(f"Article {article_id} not found")
        
        return success
    
    def mark_article_failed(self, article_id: str) -> bool:
        """Mark article as failed analysis."""
        success = self.repos.articles.update_status(article_id, "failed")
        if not success:
            logger.error(f"Article {article_id} not found")
        return success
    
    def clear_article_text(self, article_id: str) -> bool:
        """Clear article text to save storage space after analysis."""
        return self.repos.articles.clear_text_content(article_id)


class DatabaseService:
    """Facade service providing access to all database operations."""
    
    def __init__(self, session: Session):
        self.session = session
        self.entities = EntityService(session)
        self.articles = ArticleService(session)
    
    def commit(self):
        """Commit current transaction."""
        self.session.commit()
    
    def rollback(self):
        """Rollback current transaction."""
        self.session.rollback()
    
    def close(self):
        """Close session."""
        self.session.close()