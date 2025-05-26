"""Add source similarity tracking tables

Revision ID: 012
Revises: 011
Create Date: 2025-05-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Source similarity matrix - stores pairwise similarities between sources
    op.create_table('source_similarity_matrix',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id_1', sa.Integer(), nullable=False),
        sa.Column('source_id_2', sa.Integer(), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=False),
        sa.Column('correlation_score', sa.Float(), nullable=True),  # Pearson correlation
        sa.Column('common_entities', sa.Integer(), nullable=False),  # Number of entities both covered
        sa.Column('calculation_method', sa.String(50), nullable=False),  # 'pearson_common', 'cosine_all', etc.
        sa.Column('time_window_start', sa.DateTime(), nullable=False),
        sa.Column('time_window_end', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['source_id_1'], ['news_sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id_2'], ['news_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for efficient querying
    op.create_index('idx_source_similarity_sources_window', 'source_similarity_matrix', 
                    ['source_id_1', 'source_id_2', 'time_window_start', 'time_window_end'], 
                    unique=True)
    op.create_index('idx_source_similarity_score', 'source_similarity_matrix', ['similarity_score'])
    op.create_index('idx_source_similarity_window', 'source_similarity_matrix', 
                    ['time_window_start', 'time_window_end'])
    
    # Source temporal drift - tracks how sources change over time
    op.create_table('source_temporal_drift',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('avg_sentiment', sa.Float(), nullable=False),
        sa.Column('sentiment_change', sa.Float(), nullable=True),  # Change from previous week
        sa.Column('mention_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['source_id'], ['news_sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_source_drift_lookup', 'source_temporal_drift', 
                    ['source_id', 'entity_id', 'week_start'], unique=True)
    op.create_index('idx_source_drift_week', 'source_temporal_drift', ['week_start'])
    
    # Entity volatility tracking - identifies entities with high sentiment variance
    op.create_table('entity_volatility',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('time_window_start', sa.DateTime(), nullable=False),
        sa.Column('time_window_end', sa.DateTime(), nullable=False),
        sa.Column('volatility_score', sa.Float(), nullable=False),  # Std dev of sentiment
        sa.Column('trend_direction', sa.Float(), nullable=True),  # Linear trend coefficient
        sa.Column('source_divergence', sa.Float(), nullable=True),  # How much sources disagree
        sa.Column('mention_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_entity_volatility_lookup', 'entity_volatility', 
                    ['entity_id', 'time_window_start', 'time_window_end'], unique=True)
    op.create_index('idx_entity_volatility_score', 'entity_volatility', ['volatility_score'])
    
    # Source clusters - tracks hierarchical clustering assignments
    op.create_table('source_clusters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.String(50), nullable=False),  # e.g., "US_mainstream_1"
        sa.Column('cluster_level', sa.Integer(), nullable=False),  # 1=major, 2=clustered, 3=minor
        sa.Column('similarity_to_centroid', sa.Float(), nullable=True),
        sa.Column('assigned_date', sa.Date(), nullable=False),
        sa.Column('is_centroid', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),  # stores quality metrics, etc.
        sa.ForeignKeyConstraint(['source_id'], ['news_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_source_clusters_lookup', 'source_clusters', 
                    ['source_id', 'assigned_date'], unique=True)
    op.create_index('idx_source_clusters_cluster', 'source_clusters', 
                    ['cluster_id', 'assigned_date'])

def downgrade():
    op.drop_table('source_clusters')
    op.drop_table('entity_volatility')
    op.drop_table('source_temporal_drift')
    op.drop_table('source_similarity_matrix')