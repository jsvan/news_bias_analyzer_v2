"""
Repository pattern implementation for data access.

Provides clean, testable abstractions for database operations,
separating data access logic from business logic.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from .models import Entity, EntityMention, NewsArticle, NewsSource
from .config import AnalysisConfig


class BaseRepository(ABC):
    """Base repository with common database operations."""
    
    def __init__(self, session: Session):
        self.session = session


class EntityRepository(BaseRepository):
    """Repository for Entity operations."""
    
    def find_by_normalized_name(self, normalized_name: str) -> Optional[Entity]:
        """Find entity by case-insensitive normalized name."""
        return self.session.query(Entity).filter(
            func.lower(Entity.name) == func.lower(normalized_name)
        ).first()
    
    def find_by_id(self, entity_id: int) -> Optional[Entity]:
        """Find entity by ID."""
        return self.session.query(Entity).get(entity_id)
    
    def create(self, name: str, entity_type: str) -> Entity:
        """Create new entity."""
        entity = Entity(name=name, entity_type=entity_type)
        self.session.add(entity)
        return entity
    
    def find_entities_needing_pruning(
        self, 
        max_weeks: int, 
        min_days: int,
        preserve_key: str,
        preserve_value: str
    ) -> List[Tuple[int, str, str, int, float, int]]:
        """
        Find entities that should be pruned based on age and mention count.
        
        Returns:
            List of tuples: (id, name, entity_type, mention_count, weeks_old, threshold)
        """
        from sqlalchemy import text
        
        query = text("""
            WITH entity_stats AS (
                SELECT 
                    e.id,
                    e.name,
                    e.entity_type,
                    COUNT(em.id) as mention_count,
                    EXTRACT(EPOCH FROM (NOW() - e.created_at)) / 604800 as weeks_old,
                    LEAST(CEIL(EXTRACT(EPOCH FROM (NOW() - e.created_at)) / 604800), :max_weeks) as threshold
                FROM entities e
                LEFT JOIN entity_mentions em ON e.id = em.entity_id
                WHERE 
                    (e.pruning_metadata->>:preserve_key IS NULL OR e.pruning_metadata->>:preserve_key != :preserve_value)
                    AND e.created_at < NOW() - INTERVAL :min_days DAY
                GROUP BY e.id, e.name, e.entity_type, e.created_at
                HAVING 
                    COUNT(em.id) <= LEAST(CEIL(EXTRACT(EPOCH FROM (NOW() - e.created_at)) / 604800), :max_weeks)
            )
            SELECT 
                id, name, entity_type, mention_count, 
                ROUND(weeks_old::numeric, 1) as weeks_old, threshold
            FROM entity_stats
            ORDER BY mention_count, weeks_old DESC
        """)
        
        return self.session.execute(query, {
            'max_weeks': max_weeks,
            'min_days': min_days,
            'preserve_key': preserve_key,
            'preserve_value': preserve_value
        }).fetchall()
    
    def delete_by_ids(self, entity_ids: List[int]) -> int:
        """
        Delete entities by IDs.
        
        Returns:
            Number of entities deleted
        """
        from sqlalchemy import text
        
        result = self.session.execute(
            text("DELETE FROM entities WHERE id = ANY(:ids)"),
            {"ids": entity_ids}
        )
        return result.rowcount
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get entity statistics."""
        total_count = self.session.query(Entity).count()
        
        # Count by entity type
        type_stats = self.session.query(
            Entity.entity_type, 
            func.count(Entity.id)
        ).group_by(Entity.entity_type).all()
        
        return {
            'total_entities': total_count,
            'by_type': dict(type_stats)
        }


class EntityMentionRepository(BaseRepository):
    """Repository for EntityMention operations."""
    
    def create(
        self, 
        entity_id: int, 
        article_id: str, 
        power_score: float,
        moral_score: float,
        mentions: List[Dict[str, Any]] = None,
        created_at: datetime = None
    ) -> EntityMention:
        """Create new entity mention."""
        mention = EntityMention(
            entity_id=entity_id,
            article_id=article_id,
            power_score=power_score,
            moral_score=moral_score,
            mentions=mentions or [],
            created_at=created_at or datetime.utcnow()
        )
        self.session.add(mention)
        return mention
    
    def find_by_article_id(self, article_id: str) -> List[EntityMention]:
        """Find all mentions for an article."""
        return self.session.query(EntityMention).filter_by(article_id=article_id).all()
    
    def count_by_article_id(self, article_id: str) -> int:
        """Count mentions for an article."""
        return self.session.query(EntityMention).filter_by(article_id=article_id).count()
    
    def find_with_entities_by_article_id(self, article_id: str) -> List[Tuple[Entity, EntityMention]]:
        """Find entity mentions with joined entity data."""
        return self.session.query(Entity, EntityMention).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).filter(EntityMention.article_id == article_id).all()
    
    def delete_by_entity_ids(self, entity_ids: List[int]) -> int:
        """
        Delete entity mentions by entity IDs.
        
        Returns:
            Number of mentions deleted
        """
        from sqlalchemy import text
        
        result = self.session.execute(
            text("DELETE FROM entity_mentions WHERE entity_id = ANY(:ids)"),
            {"ids": entity_ids}
        )
        return result.rowcount
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get entity mention statistics."""
        total_count = self.session.query(EntityMention).count()
        
        # Average scores
        avg_scores = self.session.query(
            func.avg(EntityMention.power_score).label('avg_power'),
            func.avg(EntityMention.moral_score).label('avg_moral')
        ).first()
        
        return {
            'total_mentions': total_count,
            'average_power_score': float(avg_scores.avg_power or 0),
            'average_moral_score': float(avg_scores.avg_moral or 0)
        }


class ArticleRepository(BaseRepository):
    """Repository for NewsArticle operations."""
    
    def find_by_id(self, article_id: str) -> Optional[NewsArticle]:
        """Find article by ID."""
        return self.session.query(NewsArticle).get(article_id)
    
    def find_unanalyzed(self, limit: int = None) -> List[NewsArticle]:
        """Find articles that need analysis."""
        query = self.session.query(NewsArticle).filter(
            NewsArticle.analysis_status == AnalysisConfig.Status.UNANALYZED
        )
        
        if limit:
            query = query.limit(limit)
            
        return query.all()
    
    def find_by_status(self, status: str, limit: int = None) -> List[NewsArticle]:
        """Find articles by analysis status."""
        query = self.session.query(NewsArticle).filter(
            NewsArticle.analysis_status == status
        )
        
        if limit:
            query = query.limit(limit)
            
        return query.all()
    
    def update_status(self, article_id: str, status: str, processed_at: datetime = None) -> bool:
        """Update article analysis status."""
        article = self.find_by_id(article_id)
        if not article:
            return False
        
        article.analysis_status = status
        if processed_at:
            article.processed_at = processed_at
        
        return True
    
    def update_hotelling_score(self, article_id: str, score: float) -> bool:
        """Update article Hotelling T² score."""
        article = self.find_by_id(article_id)
        if not article:
            return False
        
        article.hotelling_t2_score = score
        return True
    
    def clear_text_content(self, article_id: str) -> bool:
        """Clear article text and HTML content to save space."""
        article = self.find_by_id(article_id)
        if not article:
            return False
        
        article.text = None
        article.html = None
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get article statistics."""
        total_count = self.session.query(NewsArticle).count()
        
        # Count by status
        status_stats = self.session.query(
            NewsArticle.analysis_status,
            func.count(NewsArticle.id)
        ).group_by(NewsArticle.analysis_status).all()
        
        # Recent articles
        recent_count = self.session.query(NewsArticle).filter(
            NewsArticle.scraped_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        return {
            'total_articles': total_count,
            'by_status': dict(status_stats),
            'recent_articles': recent_count
        }


class SourceRepository(BaseRepository):
    """Repository for NewsSource operations."""
    
    def find_by_id(self, source_id: int) -> Optional[NewsSource]:
        """Find source by ID."""
        return self.session.query(NewsSource).get(source_id)
    
    def find_by_name(self, name: str) -> Optional[NewsSource]:
        """Find source by name."""
        return self.session.query(NewsSource).filter(
            NewsSource.name == name
        ).first()
    
    def find_by_country(self, country: str) -> List[NewsSource]:
        """Find sources by country."""
        return self.session.query(NewsSource).filter(
            NewsSource.country == country
        ).all()
    
    def get_all(self) -> List[NewsSource]:
        """Get all news sources."""
        return self.session.query(NewsSource).all()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get source statistics."""
        total_count = self.session.query(NewsSource).count()
        
        # Count by country
        country_stats = self.session.query(
            NewsSource.country,
            func.count(NewsSource.id)
        ).group_by(NewsSource.country).all()
        
        return {
            'total_sources': total_count,
            'by_country': dict(country_stats)
        }


class RepositoryFactory:
    """Factory for creating repository instances."""
    
    def __init__(self, session: Session):
        self.session = session
        self._entities: Optional[EntityRepository] = None
        self._entity_mentions: Optional[EntityMentionRepository] = None
        self._articles: Optional[ArticleRepository] = None
        self._sources: Optional[SourceRepository] = None
    
    @property
    def entities(self) -> EntityRepository:
        """Get entity repository."""
        if self._entities is None:
            self._entities = EntityRepository(self.session)
        return self._entities
    
    @property
    def entity_mentions(self) -> EntityMentionRepository:
        """Get entity mention repository."""
        if self._entity_mentions is None:
            self._entity_mentions = EntityMentionRepository(self.session)
        return self._entity_mentions
    
    @property
    def articles(self) -> ArticleRepository:
        """Get article repository."""
        if self._articles is None:
            self._articles = ArticleRepository(self.session)
        return self._articles
    
    @property
    def sources(self) -> SourceRepository:
        """Get source repository."""
        if self._sources is None:
            self._sources = SourceRepository(self.session)
        return self._sources


# Add missing import
from datetime import timedelta