"""Rename metadata column to extraction_info

Revision ID: 009_rename_metadata
Revises: 008_add_metadata_column
Create Date: 2025-05-11

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '009_rename_metadata'
down_revision = '008_add_metadata_column'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First check if metadata column exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('news_articles')]
    
    if 'metadata' in columns:
        # Rename metadata column to extraction_info
        op.alter_column('news_articles', 'metadata', new_column_name='extraction_info')
    elif 'extraction_info' not in columns:
        # If neither column exists, add extraction_info column
        op.add_column('news_articles', sa.Column('extraction_info', JSONB, nullable=True))


def downgrade() -> None:
    # First check if extraction_info column exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('news_articles')]
    
    if 'extraction_info' in columns:
        # Rename extraction_info column back to metadata
        op.alter_column('news_articles', 'extraction_info', new_column_name='metadata')