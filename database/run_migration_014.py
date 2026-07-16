#!/usr/bin/env python3
"""
Run migration 014: stop using entity_type as part of Entity identity.

Background: the unique constraint on (name, entity_type) meant that any drift in the
free-text entity_type field (e.g. "United States" typed once as "government" and once as
"political_leader") minted a brand-new duplicate Entity row for a name that already
existed. Structured Outputs enum enforcement (see analyzer/prompts.py::ENTITY_TYPES) stops
new drift going forward, but existing duplicate-name rows need resolving before identity
can be name-only.

This migration:
1. Drops the (name, entity_type) unique index.
2. Auto-merges existing canonical (canonical_id IS NULL) entities that share an exact
   normalized name, via analyzer/entity_resolution.py's existing propose_merges() - the
   same exact-match tier the weekly merge job (see database/run_migration_014 sibling:
   scheduler/job_scheduler.py) uses going forward. Only exact matches auto-merge; no
   human review queue, consistent with the rest of this pipeline.
3. Creates a new unique index on name alone, scoped to canonical (unmerged) rows only -
   merged-away rows are expected to share a name with their canonical row, that's the
   point of a merge, so the constraint is a partial index (WHERE canonical_id IS NULL).

Run with: ./run.sh custom 'database/run_migration_014.py'
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from analyzer.entity_resolution import propose_merges

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run migration 014: drop entity_type from Entity's unique constraint."""

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False

    try:
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("Starting migration 014: name-only entity identity...")

        # Step 1: drop the (name, entity_type) unique index if present
        check_index = text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'entities' AND indexname = 'idx_entities_name_type'
        """)
        if session.execute(check_index).fetchone():
            logger.info("Dropping idx_entities_name_type (name, entity_type unique index)...")
            session.execute(text("DROP INDEX idx_entities_name_type"))
            session.commit()
            logger.info("✓ Dropped idx_entities_name_type")
        else:
            logger.info("idx_entities_name_type already absent, skipping")

        # Step 2: auto-merge existing canonical entities that share an exact normalized name
        # (the same duplicate-name-different-type problem the old constraint was causing).
        logger.info("Finding canonical entities with exact-match normalized-name collisions...")
        candidates = session.execute(text("""
            SELECT e.id, e.name, e.entity_type, COUNT(em.id) AS mention_count
            FROM entities e
            LEFT JOIN entity_mentions em ON em.entity_id = e.id
            WHERE e.canonical_id IS NULL
            GROUP BY e.id, e.name, e.entity_type
        """)).fetchall()

        entities_tuples = [(row.id, row.name, row.entity_type, row.mention_count) for row in candidates]
        auto, review = propose_merges(entities_tuples)

        logger.info(f"Found {len(auto)} exact-match auto-merges, {len(review)} fuzzy candidates "
                    f"(fuzzy candidates are NOT auto-merged - no human review queue exists, "
                    f"conservative default is to leave them separate)")

        merged_count = 0
        for loser_id, canonical_id, reason in auto:
            session.execute(
                text("UPDATE entities SET canonical_id = :canonical_id WHERE id = :loser_id"),
                {"canonical_id": canonical_id, "loser_id": loser_id}
            )
            merged_count += 1
        session.commit()
        logger.info(f"✓ Auto-merged {merged_count} duplicate-name entities via canonical_id")

        # Step 3: create the new name-only unique index, scoped to canonical rows.
        check_new_index = text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'entities' AND indexname = 'idx_entities_name_canonical_unique'
        """)
        if session.execute(check_new_index).fetchone():
            logger.info("idx_entities_name_canonical_unique already exists, skipping")
        else:
            logger.info("Creating partial unique index on name (canonical rows only)...")
            session.execute(text("""
                CREATE UNIQUE INDEX idx_entities_name_canonical_unique
                ON entities (name)
                WHERE canonical_id IS NULL
            """))
            session.commit()
            logger.info("✓ Created idx_entities_name_canonical_unique")

        logger.info("Migration 014 completed successfully!")

        summary = session.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE canonical_id IS NULL) AS canonical,
                   COUNT(*) FILTER (WHERE canonical_id IS NOT NULL) AS merged
            FROM entities
        """)).fetchone()
        logger.info("\n=== Migration Summary ===")
        logger.info(f"Total entities: {summary.total}")
        logger.info(f"Canonical (unmerged): {summary.canonical}")
        logger.info(f"Merged (canonical_id set): {summary.merged}")

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
