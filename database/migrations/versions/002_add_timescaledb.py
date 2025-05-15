"""Add TimescaleDB hypertables

Revision ID: 002
Revises: 001
Create Date: 2025-05-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Create TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    
    # Convert tables to hypertables
    op.execute("""
        SELECT create_hypertable(
            'entity_mentions', 
            'created_at',
            if_not_exists => TRUE
        );
    """)
    
    op.execute("""
        SELECT create_hypertable(
            'news_articles', 
            'publish_date',
            if_not_exists => TRUE
        );
    """)


def downgrade():
    # TimescaleDB doesn't support converting hypertables back to regular tables
    # So this is a no-op for safety
    pass