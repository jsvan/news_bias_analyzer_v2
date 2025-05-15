"""Add political_leaning to news_sources

Revision ID: 007_add_political_leaning
Revises: 006_add_quote_tables
Create Date: 2023-05-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_political_leaning'
down_revision = '006_add_quote_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Check if the column already exists
    # This is a safer approach that won't fail if the column is already there
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('news_sources')]
    
    if 'political_leaning' not in columns:
        op.add_column('news_sources', sa.Column('political_leaning', sa.String(50), nullable=True))


def downgrade():
    # We don't want to drop the column on downgrade if it might be in use
    pass