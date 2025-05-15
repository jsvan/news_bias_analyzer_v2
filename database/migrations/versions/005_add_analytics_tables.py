"""Add analytics and dashboard tables

Revision ID: 005
Revises: 004
Create Date: 2025-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Create saved_searches table for user-saved searches and analytics
    op.create_table('saved_searches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('query_parameters', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('last_run', sa.DateTime(), nullable=True),
    )
    
    # Create dashboard_widgets table
    op.create_table('dashboard_widgets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('search_id', sa.Integer(), sa.ForeignKey('saved_searches.id'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('widget_type', sa.String(50), nullable=False),  # 'chart', 'table', 'metric', etc.
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('size', sa.String(20), nullable=False, server_default='medium'),  # 'small', 'medium', 'large'
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    # Create cached_results table for storing aggregated data
    op.create_table('cached_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('search_id', sa.Integer(), sa.ForeignKey('saved_searches.id'), nullable=True),
        sa.Column('cache_key', sa.String(255), nullable=False),
        sa.Column('result_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
    )
    
    # Create indexes
    op.create_index('idx_saved_searches_user_id', 'saved_searches', ['user_id'])
    op.create_index('idx_dashboard_widgets_user_id', 'dashboard_widgets', ['user_id'])
    op.create_index('idx_dashboard_widgets_search_id', 'dashboard_widgets', ['search_id'])
    op.create_index('idx_cached_results_search_id', 'cached_results', ['search_id'])
    op.create_index('idx_cached_results_cache_key', 'cached_results', ['cache_key'], unique=True)
    
    # Ensure unique searches per user
    op.create_unique_constraint(
        'uq_saved_searches_user_name', 
        'saved_searches', 
        ['user_id', 'name']
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('cached_results')
    op.drop_table('dashboard_widgets')
    op.drop_table('saved_searches')