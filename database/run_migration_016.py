#!/usr/bin/env python3
"""
Run migration 016: add entity_embeddings, the learned-relatedness table for Phase 4
(entity relatedness via co-occurrence + sentiment-profile embeddings - see
analyzer/entity_embeddings.py). Explicitly NOT a hand-curated hierarchy: "Trump relates
to Republicans/White House" is meant to emerge from co-occurrence and sentiment-profile
statistics, not be asserted here.

entity_id is a real FK to entities(id), not COALESCE(canonical_id, id) resolved at write
time in SQL - analyzer/entity_embeddings.py resolves identity through
COALESCE(canonical_id, id) itself before ever building a candidate-entity list, so only
canonical (surviving) entity rows are ever written here. ON DELETE CASCADE means a merged
entity's row disappears automatically if entities.id is ever hard-deleted.

cooccurrence_vec / sentiment_vec are plain DOUBLE PRECISION[] rather than a fixed-width
vector type (e.g. pgvector) - this repo has no vector extension installed, and
Python/numpy on the read and write side is enough for the dataset sizes involved
(cosine similarity computed at request time in extension/api/embeddings_endpoints.py).

Run with: ./run.sh custom 'database/run_migration_016.py'
"""

import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run migration 016: create entity_embeddings."""

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False

    try:
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("Starting migration 016: entity_embeddings...")

        check_table = text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'entity_embeddings'
        """)
        if session.execute(check_table).fetchone():
            logger.info("entity_embeddings already exists, skipping creation")
        else:
            logger.info("Creating entity_embeddings...")
            session.execute(text("""
                CREATE TABLE entity_embeddings (
                    entity_id INTEGER PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
                    cooccurrence_vec DOUBLE PRECISION[] NOT NULL,
                    sentiment_vec DOUBLE PRECISION[] NOT NULL,
                    mention_count INTEGER NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            session.commit()
            logger.info("✓ Created entity_embeddings")

        logger.info("Migration 016 completed successfully!")

        summary = session.execute(text(
            "SELECT COUNT(*) AS rows FROM entity_embeddings"
        )).fetchone()
        logger.info("\n=== Migration Summary ===")
        logger.info(f"entity_embeddings rows: {summary.rows}")

        session.close()
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
