"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2025-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create news_sources table
    op.create_table('news_sources',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('base_url', sa.String(255), nullable=False),
        sa.Column('country', sa.String(100)),
        sa.Column('language', sa.String(50)),
        sa.Column('political_leaning', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    # Create news_articles table
    op.create_table('news_articles',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('news_sources.id')),
        sa.Column('url', sa.String(1024), nullable=False, unique=True),
        sa.Column('title', sa.String(512)),
        sa.Column('text', sa.Text()),
        sa.Column('html', sa.Text(), nullable=True),
        sa.Column('publish_date', sa.DateTime()),
        sa.Column('authors', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('top_image', sa.String(1024), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
    )
    
    # Create entities table
    op.create_table('entities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('entity_type', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('canonical_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=True),
    )
    
    # Create entity_mentions table
    op.create_table('entity_mentions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id')),
        sa.Column('article_id', sa.String(32), sa.ForeignKey('news_articles.id')),
        sa.Column('power_score', sa.Float()),
        sa.Column('moral_score', sa.Float()),
        sa.Column('mentions', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    # Create indexes
    op.create_index('idx_news_articles_publish_date', 'news_articles', ['publish_date'])
    op.create_index('idx_news_articles_processed_at', 'news_articles', ['processed_at'])
    op.create_index('idx_entities_name_type', 'entities', ['name', 'entity_type'], unique=True)
    op.create_index('idx_entity_mentions_entity_id', 'entity_mentions', ['entity_id'])
    op.create_index('idx_entity_mentions_article_id', 'entity_mentions', ['article_id'])
    op.create_index('idx_entity_mentions_scores', 'entity_mentions', ['power_score', 'moral_score'])


def downgrade():
    # Drop tables in reverse order of creation
    op.drop_table('entity_mentions')
    op.drop_table('entities')
    op.drop_table('news_articles')
    op.drop_table('news_sources')