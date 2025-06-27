"""
Unified database session management.

Provides consistent session creation, lifecycle management, and transaction
handling across the entire application. Replaces scattered session patterns
with a centralized, reliable approach.
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .config import DatabaseConfig
from .models import Base

logger = logging.getLogger(__name__)


class DatabaseSessionManager:
    """
    Centralized database session manager providing consistent session handling.
    
    Features:
    - Connection pooling
    - Automatic session cleanup
    - Transaction management
    - Performance monitoring
    """
    
    _instance: Optional['DatabaseSessionManager'] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None
    
    def __new__(cls, database_url: Optional[str] = None) -> 'DatabaseSessionManager':
        """Singleton pattern to ensure consistent database connections."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(database_url)
        return cls._instance
    
    def _initialize(self, database_url: Optional[str] = None) -> None:
        """Initialize database engine and session factory."""
        if self._engine is not None:
            return  # Already initialized
            
        db_url = DatabaseConfig.get_database_url(database_url)
        
        # Create engine with connection pooling
        self._engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=DatabaseConfig.POOL_SIZE,
            max_overflow=DatabaseConfig.MAX_OVERFLOW,
            pool_timeout=DatabaseConfig.POOL_TIMEOUT,
            pool_recycle=DatabaseConfig.POOL_RECYCLE,
            echo=False  # Set to True for SQL query logging in development
        )
        
        # Add performance monitoring
        if logger.isEnabledFor(logging.DEBUG):
            self._add_performance_monitoring()
        
        # Create session factory
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=DatabaseConfig.AUTOCOMMIT,
            autoflush=DatabaseConfig.AUTOFLUSH
        )
        
        logger.info(f"Database session manager initialized with URL: {self._mask_url(db_url)}")
    
    def _add_performance_monitoring(self) -> None:
        """Add database performance monitoring for development."""
        @event.listens_for(self._engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(self._engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - context._query_start_time
            if total > DatabaseConfig.SLOW_QUERY_THRESHOLD:
                logger.warning(f"Slow query ({total:.2f}s): {statement[:100]}...")
    
    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask sensitive information in database URL for logging."""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)
    
    def get_session(self) -> Session:
        """
        Create a new database session.
        
        Returns:
            Session: SQLAlchemy session
            
        Note:
            Caller is responsible for closing the session.
            Use get_session_context() for automatic cleanup.
        """
        if self._session_factory is None:
            raise RuntimeError("DatabaseSessionManager not initialized")
        
        return self._session_factory()
    
    @contextmanager
    def get_session_context(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions with automatic cleanup.
        
        Yields:
            Session: SQLAlchemy session
            
        Example:
            with session_manager.get_session_context() as session:
                # Use session
                session.add(entity)
                # Automatic commit on success, rollback on exception
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    @contextmanager
    def get_transaction_context(self) -> Generator[Session, None, None]:
        """
        Context manager for explicit transaction management.
        
        Yields:
            Session: SQLAlchemy session
            
        Note:
            Does not auto-commit. Caller must explicitly call session.commit()
        """
        session = self.get_session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_tables(self) -> None:
        """Create all database tables."""
        if self._engine is None:
            raise RuntimeError("DatabaseSessionManager not initialized")
        
        Base.metadata.create_all(self._engine)
        logger.info("Database tables created/verified")
    
    def close_all_connections(self) -> None:
        """Close all database connections and cleanup."""
        if self._engine is not None:
            self._engine.dispose()
            logger.info("All database connections closed")


# Global session manager instance
_session_manager: Optional[DatabaseSessionManager] = None


def get_session_manager(database_url: Optional[str] = None) -> DatabaseSessionManager:
    """
    Get the global session manager instance.
    
    Args:
        database_url: Optional database URL override
        
    Returns:
        DatabaseSessionManager: Global session manager
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = DatabaseSessionManager(database_url)
    return _session_manager


def get_db_session() -> Session:
    """
    Convenience function to get a new database session.
    
    Returns:
        Session: SQLAlchemy session
        
    Note:
        Equivalent to get_session_manager().get_session()
        Caller is responsible for closing the session.
    """
    return get_session_manager().get_session()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Convenience context manager for database sessions.
    
    Yields:
        Session: SQLAlchemy session with automatic cleanup
        
    Example:
        with get_db_context() as db:
            db.add(entity)
            # Auto-commit on success
    """
    with get_session_manager().get_session_context() as session:
        yield session


# FastAPI dependency for consistent session management
def get_db_dependency() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    
    Yields:
        Session: SQLAlchemy session
        
    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db_dependency)):
            # Use db session
    """
    session = get_db_session()
    try:
        yield session
    finally:
        session.close()


# Import time for performance monitoring
import time