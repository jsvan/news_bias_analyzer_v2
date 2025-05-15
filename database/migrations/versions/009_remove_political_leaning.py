"""Remove political_leaning field from news_sources

Revision ID: 009_remove_political_leaning
Revises: 008_add_metadata_column
Create Date: 2025-05-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_remove_political_leaning'
down_revision = '008_add_metadata_column'
branch_labels = None
depends_on = None


def upgrade():
    # Check if the column exists before trying to remove it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('news_sources')]
    
    if 'political_leaning' in columns:
        op.drop_column('news_sources', 'political_leaning')


def downgrade():
    # We don't re-add the column on downgrade since we're removing this concept
    pass