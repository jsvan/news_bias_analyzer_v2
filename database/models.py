from datetime import datetime
from typing import List, Optional
import os
import logging

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON, Index, ARRAY, text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB, BYTEA
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set up logging
logger = logging.getLogger(__name__)

Base = declarative_base()

def get_db_connection():
    """Get a database connection from environment variables."""
    # Use environment variable for database URL
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL environment variable must be set")

    # Create engine
    engine = create_engine(db_url)
    return engine

def get_db_session():
    """Get a database session."""
    engine = get_db_connection()
    Session = sessionmaker(bind=engine)
    return Session()

def check_compression_support(session):
    """Check if the PostgreSQL version supports LZ4 compression."""
    try:
        result = session.execute(text("SHOW server_version")).fetchone()
        version = result[0].split('.')[0]  # Get major version number

        if int(version) >= 14:
            return "LZ4"  # PostgreSQL 14+ supports LZ4 compression
        else:
            return "PGLZ"  # Earlier versions only support default PGLZ
    except Exception as e:
        logger.error(f"Error checking compression support: {e}")
        return None

def compress_article_text(session, article_id):
    """
    Compress the text of an article that has been analyzed.
    This sets the PostgreSQL TOAST compression to LZ4 if available.

    Args:
        session: SQLAlchemy session
        article_id: The ID of the article to compress

    Returns:
        True if compression was applied, False otherwise
    """
    try:
        # First check if the database supports LZ4 compression
        compression_type = check_compression_support(session)

        if compression_type == "LZ4":
            # PostgreSQL 14+ with LZ4 support
            query = text("""
                UPDATE news_articles
                SET text = text, html = html
                WHERE id = :article_id AND processed_at IS NOT NULL;
                
                ALTER TABLE news_articles
                ALTER COLUMN text SET COMPRESSION LZ4,
                ALTER COLUMN html SET COMPRESSION LZ4
            """)
        else:
            # PostgreSQL with only PGLZ support or older version
            query = text("""
                UPDATE news_articles
                SET text = text, html = html
                WHERE id = :article_id AND processed_at IS NOT NULL;
                
                ALTER TABLE news_articles
                ALTER COLUMN text SET STORAGE EXTENDED,
                ALTER COLUMN html SET STORAGE EXTENDED
            """)

        session.execute(query, {"article_id": article_id})
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Error compressing article text: {e}")
        session.rollback()
        return False


class NewsSource(Base):
    """News source information."""
    __tablename__ = 'news_sources'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    base_url = Column(String(255), nullable=False)
    country = Column(String(100))
    language = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    articles = relationship("NewsArticle", back_populates="source")
    
    def __repr__(self):
        return f"<NewsSource(name='{self.name}', country='{self.country}')>"


class NewsArticle(Base):
    """Represents a scraped news article."""
    __tablename__ = 'news_articles'

    id = Column(String(32), primary_key=True)  # MD5 hash of URL
    source_id = Column(Integer, ForeignKey('news_sources.id'))
    url = Column(String(1024), nullable=False, unique=True)
    title = Column(String(512))
    text = Column(Text)
    html = Column(Text, nullable=True)
    publish_date = Column(DateTime)
    authors = Column(JSON)
    language = Column(String(10), nullable=True)
    top_image = Column(String(1024), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    extraction_info = Column(JSON, nullable=True)  # Store extraction method, lengths, etc.
    
    # New processing status fields for batch analysis
    analysis_status = Column(String(20), default="unanalyzed")  # unanalyzed, in_progress, completed, failed
    batch_id = Column(String(50), nullable=True)  # OpenAI batch ID if in a batch
    last_analysis_attempt = Column(DateTime, nullable=True)  # When last attempted to analyze
    
    # Hotelling T² score for measuring article extremeness
    hotelling_t2_score = Column(Float, nullable=True)  # Statistical extremeness metric

    source = relationship("NewsSource", back_populates="articles")
    entities = relationship("EntityMention", back_populates="article")
    quotes = relationship("Quote", back_populates="article")
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_news_articles_publish_date', 'publish_date'),
        Index('idx_news_articles_processed_at', 'processed_at'),
        Index('idx_news_articles_analysis_status', 'analysis_status'),
        Index('idx_news_articles_batch_id', 'batch_id'),
    )
    
    def __repr__(self):
        return f"<NewsArticle(id='{self.id}', title='{self.title[:30]}...', status='{self.analysis_status}')>"


class Entity(Base):
    """Named entity that can appear in articles."""
    __tablename__ = 'entities'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50))  # person, organization, country, political_party, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Canonical form for entity resolution
    canonical_id = Column(Integer, ForeignKey('entities.id'), nullable=True)
    
    mentions = relationship("EntityMention", back_populates="entity")
    
    # Unique constraint on name and type
    __table_args__ = (
        Index('idx_entities_name_type', 'name', 'entity_type', unique=True),
    )
    
    def __repr__(self):
        return f"<Entity(name='{self.name}', type='{self.entity_type}')>"


class EntityMention(Base):
    """Occurrence of an entity in an article with sentiment scores."""
    __tablename__ = 'entity_mentions'
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey('entities.id'))
    article_id = Column(String(32), ForeignKey('news_articles.id'))
    
    # Sentiment scores
    power_score = Column(Float)  # strong/weak dimension (-2 to +2)
    moral_score = Column(Float)  # good/evil dimension (-2 to +2)
    
    # Sample mentions with context
    mentions = Column(JSON)  # List of {text, context} objects
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    entity = relationship("Entity", back_populates="mentions")
    article = relationship("NewsArticle", back_populates="entities")
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_entity_mentions_entity_id', 'entity_id'),
        Index('idx_entity_mentions_article_id', 'article_id'),
        Index('idx_entity_mentions_scores', 'power_score', 'moral_score'),
    )
    
    def __repr__(self):
        return f"<EntityMention(entity_id={self.entity_id}, article_id='{self.article_id}', " \
               f"power_score={self.power_score}, moral_score={self.moral_score})>"


# New tables for quote tracking

class PublicFigure(Base):
    """Notable people whose quotes we're tracking."""
    __tablename__ = 'public_figures'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    title = Column(String(255))
    country = Column(String(100))
    political_party = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    quotes = relationship("Quote", back_populates="public_figure")
    
    def __repr__(self):
        return f"<PublicFigure(name='{self.name}', country='{self.country}')>"


class Quote(Base):
    """Represents a quote from a public figure."""
    __tablename__ = 'quotes'
    
    id = Column(Integer, primary_key=True)
    public_figure_id = Column(Integer, ForeignKey('public_figures.id', ondelete='CASCADE'))
    article_id = Column(String(32), ForeignKey('news_articles.id', ondelete='CASCADE'))
    
    quote_text = Column(Text, nullable=False)
    context = Column(Text)
    quote_date = Column(DateTime)
    topics = Column(JSONB)  # JSON array of topic names/IDs
    sentiment_scores = Column(JSONB)  # JSON object with sentiment analysis
    mentioned_entities = Column(JSONB)  # JSON array of entities mentioned in the quote
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    public_figure = relationship("PublicFigure", back_populates="quotes")
    article = relationship("NewsArticle", back_populates="quotes")
    topic_links = relationship("QuoteTopic", back_populates="quote")
    
    def __repr__(self):
        preview = self.quote_text[:50] + "..." if len(self.quote_text) > 50 else self.quote_text
        return f"<Quote(id={self.id}, figure_id={self.public_figure_id}, text='{preview}')>"


class Topic(Base):
    """Topics for categorizing quotes."""
    __tablename__ = 'topics'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey('topics.id', ondelete='SET NULL'))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Self-referential relationship for hierarchical topics
    subtopics = relationship("Topic", 
                            backref="parent", remote_side=[id],
                            cascade="all")
    
    quote_links = relationship("QuoteTopic", back_populates="topic")
    
    def __repr__(self):
        return f"<Topic(name='{self.name}')>"


class QuoteTopic(Base):
    """Linking table between quotes and topics."""
    __tablename__ = 'quote_topics'
    
    quote_id = Column(Integer, ForeignKey('quotes.id', ondelete='CASCADE'), primary_key=True)
    topic_id = Column(Integer, ForeignKey('topics.id', ondelete='CASCADE'), primary_key=True)
    relevance_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    quote = relationship("Quote", back_populates="topic_links")
    topic = relationship("Topic", back_populates="quote_links")


class WeeklySentimentStats(Base):
    """Weekly aggregated sentiment statistics for entities."""
    __tablename__ = 'weekly_sentiment_stats'
    
    entity_id = Column(Integer, ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True)
    week_start = Column(DateTime, primary_key=True)
    mean_power = Column(Float)
    mean_moral = Column(Float)
    variance_power = Column(Float)
    variance_moral = Column(Float)
    covariance = Column(Float)
    sample_count = Column(Integer)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    entity = relationship("Entity")
    
    def __repr__(self):
        return f"<WeeklySentimentStats(entity_id={self.entity_id}, week={self.week_start.date()})>"