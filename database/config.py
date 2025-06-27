"""
Database configuration and constants.

Centralizes all database-related configuration to avoid magic numbers
and scattered constants throughout the codebase.
"""

import os
from typing import Optional


class DatabaseConfig:
    """Database connection and behavior configuration."""
    
    # Connection settings
    PRIMARY_DATABASE_URL: str = os.environ.get('DATABASE_URL', 
        'postgresql://newsbias:newsbias@localhost:5432/news_bias')
    
    STATISTICAL_DATABASE_PATH: str = os.path.join(
        os.path.dirname(__file__), '..', 'statistical_database', 'intelligence.db'
    )
    
    # Connection pool settings
    POOL_SIZE: int = 10
    MAX_OVERFLOW: int = 20
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 3600  # 1 hour
    
    # Session settings
    AUTOCOMMIT: bool = False
    AUTOFLUSH: bool = True
    
    # Performance monitoring
    SLOW_QUERY_THRESHOLD: float = 1.0  # seconds
    
    @classmethod
    def get_database_url(cls, override_url: Optional[str] = None) -> str:
        """Get database URL with optional override."""
        return override_url or cls.PRIMARY_DATABASE_URL


class EntityPruningConfig:
    """Configuration for entity pruning operations."""
    
    # Pruning thresholds
    MAX_ENTITY_AGE_WEEKS: int = 12  # Cap at 12 weeks for threshold calculation
    MIN_ENTITY_AGE_DAYS: int = 7    # Don't prune entities younger than 1 week
    
    # Batch processing
    PRUNING_BATCH_SIZE: int = 1000  # Delete entities in batches of 1000
    
    # Preservation settings
    PRESERVE_METADATA_KEY: str = 'preserve'
    PRESERVE_METADATA_VALUE: str = 'true'
    
    @classmethod
    def calculate_mention_threshold(cls, weeks_old: float) -> int:
        """
        Calculate required mentions for entity age.
        
        Rule: Entity must have MORE mentions than weeks old.
        Examples:
        - 1 week old needs > 1 mentions (so >= 2)
        - 4 weeks old needs > 4 mentions (so >= 5)
        - 12+ weeks old needs > 12 mentions (so >= 13)
        """
        weeks_capped = min(weeks_old, cls.MAX_ENTITY_AGE_WEEKS)
        return int(weeks_capped)


class AnalysisConfig:
    """Configuration for article analysis operations."""
    
    # Batch processing
    DEFAULT_BATCH_SIZE: int = 50
    MAX_BATCH_SIZE: int = 100
    
    # Sentiment score validation
    MIN_SENTIMENT_SCORE: float = -2.0
    MAX_SENTIMENT_SCORE: float = 2.0
    DEFAULT_SENTIMENT_SCORE: float = 0.0
    
    # Article processing
    CLEAR_TEXT_AFTER_ANALYSIS: bool = True  # Save storage space
    
    # Status values
    class Status:
        UNANALYZED = "unanalyzed"
        IN_PROGRESS = "in_progress" 
        COMPLETED = "completed"
        FAILED = "failed"


class StatisticalConfig:
    """Configuration for statistical analysis operations."""
    
    # Hotelling T² calculation
    ENABLE_T2_CALCULATION: bool = True
    T2_CALCULATION_TIMEOUT: int = 30  # seconds
    
    # Clustering settings
    MIN_CLUSTER_SIZE: int = 2
    SIMILARITY_THRESHOLD: float = 0.7
    
    # Intelligence analysis
    ENABLE_INTELLIGENCE_MODULES: bool = True
    INTELLIGENCE_CHECK_INTERVAL: int = 3600  # 1 hour


class LoggingConfig:
    """Configuration for database operation logging."""
    
    # Log levels for different operations
    ENTITY_CREATION_LEVEL: str = "DEBUG"
    BATCH_PROCESSING_LEVEL: str = "INFO"
    ERROR_LEVEL: str = "ERROR"
    
    # Performance logging
    LOG_SLOW_QUERIES: bool = True
    SLOW_QUERY_THRESHOLD: float = 1.0  # seconds
    
    # Statistics logging
    LOG_BATCH_STATISTICS: bool = True
    LOG_PRUNING_STATISTICS: bool = True