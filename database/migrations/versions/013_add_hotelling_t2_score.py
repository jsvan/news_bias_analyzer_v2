"""Add Hotelling T² score for article extremeness

Revision ID: 013_add_hotelling_t2_score
Revises: 012_add_source_similarity_tables
Create Date: 2025-05-28

This migration adds:
1. hotelling_t2_score column to news_articles table - stores the fundamental 
   statistical extremeness metric for each article
2. weekly_sentiment_stats table - caches entity sentiment statistics for 
   efficient T² computation
3. Indexes for efficient percentile ranking queries
"""

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Add Hotelling T² score column to news_articles
    op.add_column('news_articles', 
        sa.Column('hotelling_t2_score', sa.Float(), nullable=True)
    )
    
    # Create weekly sentiment statistics cache table
    op.create_table('weekly_sentiment_stats',
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('mean_power', sa.Float(), nullable=True),
        sa.Column('mean_moral', sa.Float(), nullable=True),
        sa.Column('variance_power', sa.Float(), nullable=True),
        sa.Column('variance_moral', sa.Float(), nullable=True),
        sa.Column('covariance', sa.Float(), nullable=True),
        sa.Column('sample_count', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('entity_id', 'week_start'),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE')
    )
    
    # Index for fast percentile queries on articles from the past week
    op.create_index(
        'idx_articles_week_t2',
        'news_articles',
        ['processed_at', 'hotelling_t2_score'],
        postgresql_where=sa.text('hotelling_t2_score IS NOT NULL')
    )
    
    # Index for efficient weekly stats lookups
    op.create_index(
        'idx_weekly_stats_week',
        'weekly_sentiment_stats',
        ['week_start', 'entity_id']
    )
    
    # Index for cleanup of old weekly stats
    op.create_index(
        'idx_weekly_stats_updated',
        'weekly_sentiment_stats',
        ['updated_at']
    )


def downgrade():
    # Remove indexes
    op.drop_index('idx_weekly_stats_updated', table_name='weekly_sentiment_stats')
    op.drop_index('idx_weekly_stats_week', table_name='weekly_sentiment_stats')
    op.drop_index('idx_articles_week_t2', table_name='news_articles')
    
    # Remove weekly stats table
    op.drop_table('weekly_sentiment_stats')
    
    # Remove T² score column
    op.drop_column('news_articles', 'hotelling_t2_score')