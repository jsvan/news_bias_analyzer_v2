"""Add quote tracking tables

Revision ID: 006
Revises: 005
Create Date: 2025-05-10

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None

def upgrade():
    # Create the public_figures table to track politicians and other notable people
    op.create_table(
        'public_figures',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('title', sa.String(255)),
        sa.Column('country', sa.String(100)),
        sa.Column('political_party', sa.String(100)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())
    )
    
    # Create unique index on name
    op.create_index('idx_public_figures_name', 'public_figures', ['name'], unique=True)
    
    # Create the quotes table to store actual quotes
    op.create_table(
        'quotes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('public_figure_id', sa.Integer, sa.ForeignKey('public_figures.id', ondelete='CASCADE')),
        sa.Column('article_id', sa.String(32), sa.ForeignKey('news_articles.id', ondelete='CASCADE')),
        sa.Column('quote_text', sa.Text, nullable=False),
        sa.Column('context', sa.Text),
        sa.Column('quote_date', sa.DateTime),
        sa.Column('topics', JSONB),
        sa.Column('sentiment_scores', JSONB),
        sa.Column('mentioned_entities', JSONB),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    
    # Create indexes for efficient querying
    op.create_index('idx_quotes_public_figure_id', 'quotes', ['public_figure_id'])
    op.create_index('idx_quotes_article_id', 'quotes', ['article_id'])
    op.create_index('idx_quotes_quote_date', 'quotes', ['quote_date'])
    
    # Create the topics table for categorizing quotes
    op.create_table(
        'topics',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text),
        sa.Column('parent_id', sa.Integer, sa.ForeignKey('topics.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    
    # Create a linking table between quotes and topics
    op.create_table(
        'quote_topics',
        sa.Column('quote_id', sa.Integer, sa.ForeignKey('quotes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('topic_id', sa.Integer, sa.ForeignKey('topics.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('relevance_score', sa.Float),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )

def downgrade():
    op.drop_table('quote_topics')
    op.drop_table('topics')
    op.drop_table('quotes')
    op.drop_table('public_figures')