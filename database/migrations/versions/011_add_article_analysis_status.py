"""Add article analysis status fields

Revision ID: 011_add_article_analysis_status
Revises: 010_add_similarity_tables
Create Date: 2025-05-14 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_add_article_analysis_status'
down_revision = '010_add_similarity_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Add analysis_status field with default 'unanalyzed'
    op.add_column('news_articles', sa.Column('analysis_status', sa.String(20), 
                                          server_default='unanalyzed', nullable=False))
    
    # Add batch_id field
    op.add_column('news_articles', sa.Column('batch_id', sa.String(50), nullable=True))
    
    # Add last_analysis_attempt field
    op.add_column('news_articles', sa.Column('last_analysis_attempt', sa.DateTime(), nullable=True))
    
    # Create indexes
    op.create_index('idx_news_articles_analysis_status', 'news_articles', ['analysis_status'])
    op.create_index('idx_news_articles_batch_id', 'news_articles', ['batch_id'])

    # Update existing articles with processed_at to have 'completed' status
    op.execute("""
        UPDATE news_articles 
        SET analysis_status = 'completed' 
        WHERE processed_at IS NOT NULL
    """)


def downgrade():
    # Drop indexes
    op.drop_index('idx_news_articles_analysis_status', table_name='news_articles')
    op.drop_index('idx_news_articles_batch_id', table_name='news_articles')
    
    # Drop columns
    op.drop_column('news_articles', 'last_analysis_attempt')
    op.drop_column('news_articles', 'batch_id')
    op.drop_column('news_articles', 'analysis_status')