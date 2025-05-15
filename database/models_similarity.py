from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

from database.models import Base

# Models for similarity and clustering features

class SimilarityEmbedding(Base):
    """Stores article embedding vectors for similarity analysis."""
    __tablename__ = 'similarity_embeddings'
    
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey('news_articles.id', ondelete='CASCADE'), nullable=False)
    embedding = Column(Text, nullable=False)  # JSON string containing embedding vector
    model = Column(String(64), nullable=False)  # Name/version of embedding model used
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    
    # Relationships
    article = relationship("NewsArticle", back_populates="similarity_embedding")
    
    # Indexes
    __table_args__ = (
        Index('idx_similarity_article_id', 'article_id', unique=True),
    )


class TopicModel(Base):
    """Stores topic clustering models and results."""
    __tablename__ = 'topic_models'
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False)
    model_type = Column(String(64), nullable=False)  # e.g., 'umap_hdbscan', 'lda', etc.
    num_topics = Column(Integer, nullable=False)
    num_articles = Column(Integer, nullable=False)
    parameters = Column(Text, nullable=False)  # JSON string with model parameters
    result_data = Column(Text, nullable=True)  # JSON string with clustering result data (coordinates, cluster assignments)


class ArticleSimilarity(Base):
    """Stores precomputed similarity scores between article pairs."""
    __tablename__ = 'article_similarities'
    
    id = Column(Integer, primary_key=True)
    source_article_id = Column(Integer, ForeignKey('news_articles.id', ondelete='CASCADE'), nullable=False)
    target_article_id = Column(Integer, ForeignKey('news_articles.id', ondelete='CASCADE'), nullable=False)
    similarity_score = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False)
    
    # Relationships
    source_article = relationship("NewsArticle", foreign_keys=[source_article_id])
    target_article = relationship("NewsArticle", foreign_keys=[target_article_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_article_similarity_source_target', 'source_article_id', 'target_article_id', unique=True),
        Index('idx_article_similarity_score', 'similarity_score'),
    )