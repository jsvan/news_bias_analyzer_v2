"""Add similarity tables

Revision ID: 010
Revises: 009b_rename_metadata
Create Date: 2025-05-12

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009b_rename_metadata'
branch_labels = None
depends_on = None


def upgrade():
    # Create similarity_embeddings table
    op.create_table(
        'similarity_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('article_id', sa.String(32), sa.ForeignKey('news_articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=False),
        sa.Column('model', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_similarity_article_id', 'similarity_embeddings', ['article_id'], unique=True)
    
    # Create topic_models table
    op.create_table(
        'topic_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('model_type', sa.String(64), nullable=False),
        sa.Column('num_topics', sa.Integer(), nullable=False),
        sa.Column('num_articles', sa.Integer(), nullable=False),
        sa.Column('parameters', sa.Text(), nullable=False),
        sa.Column('result_data', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create article_similarities table
    op.create_table(
        'article_similarities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_article_id', sa.String(32), sa.ForeignKey('news_articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_article_id', sa.String(32), sa.ForeignKey('news_articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_article_similarity_source_target', 'article_similarities', ['source_article_id', 'target_article_id'], unique=True)
    op.create_index('idx_article_similarity_score', 'article_similarities', ['similarity_score'])


def downgrade():
    op.drop_table('article_similarities')
    op.drop_table('topic_models')
    op.drop_table('similarity_embeddings')