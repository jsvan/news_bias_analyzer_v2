"""Add entity resolution table

Revision ID: 003
Revises: 002
Create Date: 2025-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Create entity_resolution table for tracking entity merges and aliases
    op.create_table('entity_resolution',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('alias_entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=True),
        sa.Column('alias_name', sa.String(255), nullable=False),
        sa.Column('resolution_type', sa.String(50), nullable=False),  # 'alias', 'merge', 'split'
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('resolved_by', sa.String(100), nullable=True),  # 'auto' or username
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    
    # Create entity_stats table for caching statistics about entities
    op.create_table('entity_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('time_period', sa.String(20), nullable=False),  # 'day', 'week', 'month', 'year', 'all'
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('mention_count', sa.Integer(), nullable=False),
        sa.Column('source_count', sa.Integer(), nullable=False),
        sa.Column('power_score_avg', sa.Float(), nullable=False),
        sa.Column('power_score_std', sa.Float(), nullable=False),
        sa.Column('moral_score_avg', sa.Float(), nullable=False),
        sa.Column('moral_score_std', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    # Create indexes
    op.create_index('idx_entity_resolution_entity_id', 'entity_resolution', ['entity_id'])
    op.create_index('idx_entity_resolution_alias_entity_id', 'entity_resolution', ['alias_entity_id'])
    op.create_index('idx_entity_resolution_alias_name', 'entity_resolution', ['alias_name'])
    
    op.create_index('idx_entity_stats_entity_id', 'entity_stats', ['entity_id'])
    op.create_index('idx_entity_stats_time_period', 'entity_stats', ['time_period'])
    op.create_index('idx_entity_stats_date_range', 'entity_stats', ['start_date', 'end_date'])
    
    # Add unique constraint
    op.create_unique_constraint(
        'uq_entity_stats_entity_period_dates', 
        'entity_stats', 
        ['entity_id', 'time_period', 'start_date', 'end_date']
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('entity_stats')
    op.drop_table('entity_resolution')