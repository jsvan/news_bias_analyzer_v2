"""Add metadata column to news_articles

Revision ID: 008_add_metadata_column
Revises: 007_add_political_leaning_to_sources
Create Date: 2024-05-12 13:30:45.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '008_add_metadata_column'
down_revision: str = '007_add_political_leaning_to_sources'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add metadata JSON column to store extraction method and other metadata
    op.add_column('news_articles', sa.Column('metadata', JSONB, nullable=True))


def downgrade() -> None:
    # Remove the metadata column
    op.drop_column('news_articles', 'metadata')