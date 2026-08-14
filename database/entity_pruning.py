#!/usr/bin/env python3
"""
Entity pruning module for cleaning up low-activity entities.

Uses a dynamic threshold based on entity age:
- 1 week old: needs 1+ mentions
- 2 weeks old: needs 2+ mentions
- ...up to 12 weeks old: needs 12+ mentions
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.system_metrics import increment_system_metric
from database.config import EntityPruningConfig

logger = logging.getLogger(__name__)

def add_pruning_metadata_column(session: Session):
    """Add pruning_metadata column to entities table if it doesn't exist.

    The pruning query and repositories.py both read e.pruning_metadata->>'preserve',
    but no migration ever created the column - every pruning run since deploy died
    with UndefinedColumn (silently: the job-level try/except just logged it)."""
    try:
        result = session.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'entities' AND column_name = 'pruning_metadata'
        """)).fetchone()

        if not result:
            logger.info("Adding pruning_metadata column to entities table...")
            session.execute(text("""
                ALTER TABLE entities
                ADD COLUMN pruning_metadata JSONB
            """))
            session.commit()
            logger.info("Successfully added pruning_metadata column")
        else:
            logger.debug("pruning_metadata column already exists")

    except Exception as e:
        logger.error(f"Error adding pruning_metadata column: {e}")
        session.rollback()
        raise


def add_last_updated_column(session: Session):
    """Add last_updated column to entities table if it doesn't exist."""
    try:
        # Check if column exists
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'entities' AND column_name = 'last_updated'
        """)).fetchone()
        
        if not result:
            logger.info("Adding last_updated column to entities table...")
            session.execute(text("""
                ALTER TABLE entities 
                ADD COLUMN last_updated TIMESTAMP DEFAULT NOW()
            """))
            
            # Initialize with created_at or current time
            session.execute(text("""
                UPDATE entities 
                SET last_updated = COALESCE(created_at, NOW())
                WHERE last_updated IS NULL
            """))
            
            # Create index for performance
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_entities_last_updated 
                ON entities(last_updated)
            """))
            
            session.commit()
            logger.info("Successfully added last_updated column")
        else:
            logger.debug("last_updated column already exists")
            
    except Exception as e:
        logger.error(f"Error adding last_updated column: {e}")
        session.rollback()
        raise

def update_entity_last_updated_trigger(session: Session):
    """Create trigger to auto-update last_updated when entity_mentions are added."""
    try:
        # Create trigger function
        session.execute(text("""
            CREATE OR REPLACE FUNCTION update_entity_last_updated()
            RETURNS TRIGGER AS $$
            BEGIN
                UPDATE entities 
                SET last_updated = NOW() 
                WHERE id = NEW.entity_id;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Create trigger
        session.execute(text("""
            DROP TRIGGER IF EXISTS entity_mention_update_last_updated ON entity_mentions;
            
            CREATE TRIGGER entity_mention_update_last_updated
            AFTER INSERT ON entity_mentions
            FOR EACH ROW
            EXECUTE FUNCTION update_entity_last_updated();
        """))
        
        session.commit()
        logger.info("Created trigger for updating entity last_updated")
        
    except Exception as e:
        logger.error(f"Error creating trigger: {e}")
        session.rollback()
        raise

def prune_low_activity_entities(session: Session, dry_run: bool = False):
    """
    Prune entities based on a dynamic threshold measured in actual pipeline activity,
    not wall-clock time.

    Threshold = min(sampling_weeks_since_creation, 12), where a "sampling week" is 7 days
    that actually had scraping activity (distinct DATE(scraped_at) in news_articles),
    counted only up to the most recent real scrape - not NOW(). This matters because if the
    pipeline goes dormant (scheduler not running, no scraping happening), calendar time
    keeps passing but no new mentions can possibly arrive; a wall-clock threshold would
    treat that dormancy as "this entity had its chance and didn't get mentioned," which
    isn't true - it never got sampled at all. Anchoring to the last real sample means an
    entity's age only advances when the pipeline actually had a chance to mention it again.

    Args:
        session: Database session
        dry_run: If True, only report what would be deleted

    Returns:
        Number of entities pruned
    """
    try:
        # First ensure we have the last_updated column and trigger
        add_last_updated_column(session)
        add_pruning_metadata_column(session)
        update_entity_last_updated_trigger(session)

        # Find entities to prune
        query = text("""
            WITH sample_days AS (
                SELECT DISTINCT DATE(scraped_at) AS d FROM news_articles
            ),
            last_sample AS (
                SELECT MAX(d) AS ts FROM sample_days
            ),
            entity_stats AS (
                SELECT
                    e.id,
                    e.name,
                    e.entity_type,
                    e.created_at,
                    COUNT(em.id) as mention_count,
                    samples.n as samples_since_creation,
                    LEAST(CEIL(samples.n / 7.0), :max_weeks) as threshold
                FROM entities e
                LEFT JOIN entity_mentions em ON e.id = em.entity_id
                CROSS JOIN LATERAL (
                    SELECT COUNT(*) AS n FROM sample_days sd
                    WHERE sd.d >= e.created_at::date AND sd.d <= (SELECT ts FROM last_sample)
                ) samples
                WHERE
                    -- Skip entities marked for preservation
                    (e.pruning_metadata->>:preserve_key IS NULL OR e.pruning_metadata->>:preserve_key != :preserve_value)
                    -- Only consider entities older than configured minimum age
                    AND e.created_at < NOW() - CAST(:min_days || ' days' AS INTERVAL)
                    -- Never prune an entity other entities have been merged into
                    -- (would violate entities.canonical_id's FK and orphan the merge history)
                    AND e.id NOT IN (
                        SELECT DISTINCT canonical_id FROM entities WHERE canonical_id IS NOT NULL
                    )
                    -- Never prune an alias row either: its mentions still count toward the
                    -- canonical entity (queries aggregate over the whole merge group), so
                    -- deleting it would silently shrink the merged entity's data
                    AND e.canonical_id IS NULL
                GROUP BY e.id, e.name, e.entity_type, e.created_at, samples.n
                HAVING
                    -- Mention count must be greater than the sampling-weeks threshold (not equal)
                    COUNT(em.id) <= LEAST(CEIL(samples.n / 7.0), :max_weeks)
            )
            SELECT
                id,
                name,
                entity_type,
                mention_count,
                samples_since_creation,
                ROUND(samples_since_creation / 7.0, 1) as sampling_weeks_old,
                threshold
            FROM entity_stats
            ORDER BY mention_count, samples_since_creation DESC
        """)

        candidates = session.execute(query, {
            'max_weeks': EntityPruningConfig.MAX_ENTITY_AGE_WEEKS,
            'min_days': EntityPruningConfig.MIN_ENTITY_AGE_DAYS,
            'preserve_key': EntityPruningConfig.PRESERVE_METADATA_KEY,
            'preserve_value': EntityPruningConfig.PRESERVE_METADATA_VALUE
        }).fetchall()

        if not candidates:
            logger.info("No entities to prune")
            return 0

        # Log summary
        logger.info(f"Found {len(candidates)} entities to prune")

        # Show some examples
        examples = candidates[:10]
        for entity in examples:
            logger.info(f"  - {entity.name} ({entity.entity_type}): "
                       f"{entity.mention_count} mentions (needs {entity.threshold}), "
                       f"{entity.sampling_weeks_old} sampling-weeks old "
                       f"(active-scraping-days since creation, not calendar time)")

        if len(candidates) > 10:
            logger.info(f"  ... and {len(candidates) - 10} more")
        
        if dry_run:
            logger.info("DRY RUN - No entities were deleted")
            return len(candidates)
        
        # Delete the entities
        entity_ids = [c.id for c in candidates]
        
        # Delete in batches to avoid overwhelming the database
        batch_size = EntityPruningConfig.PRUNING_BATCH_SIZE
        total_deleted = 0
        
        for i in range(0, len(entity_ids), batch_size):
            batch_ids = entity_ids[i:i + batch_size]
            
            # First delete entity_mentions to avoid foreign key constraint violation
            mentions_result = session.execute(
                text("DELETE FROM entity_mentions WHERE entity_id = ANY(:ids)"),
                {"ids": batch_ids}
            )
            mentions_deleted = mentions_result.rowcount
            
            # Then delete the entities
            entities_result = session.execute(
                text("DELETE FROM entities WHERE id = ANY(:ids)"),
                {"ids": batch_ids}
            )
            
            batch_deleted = entities_result.rowcount
            total_deleted += batch_deleted
            
            logger.info(f"Deleted batch {i//batch_size + 1}: {mentions_deleted} mentions, {batch_deleted} entities")
            session.commit()
        
        logger.info(f"Successfully pruned {total_deleted} low-activity entities")
        
        # Update the running total (Postgres system_metrics counter)
        try:
            new_total = increment_system_metric(session, 'total_entities_deleted', total_deleted)
            logger.info(f"Total entities deleted all-time: {new_total}")
        except Exception as e:
            logger.warning(f"Could not update entity deletion metric: {e}")
        
        return total_deleted
        
    except Exception as e:
        logger.error(f"Error during entity pruning: {e}")
        session.rollback()
        raise

def get_pruning_stats(session: Session):
    """Get statistics about entities that would be pruned."""
    try:
        # Ensure column exists
        add_last_updated_column(session)
        
        # Same sample-based anchoring as prune_low_activity_entities: age is measured in
        # distinct scraping-active days since last_updated, capped at the last real sample -
        # not wall-clock NOW() - so pipeline dormancy doesn't inflate "age".
        stats_query = text("""
            WITH sample_days AS (
                SELECT DISTINCT DATE(scraped_at) AS d FROM news_articles
            ),
            last_sample AS (
                SELECT MAX(d) AS ts FROM sample_days
            ),
            entity_stats AS (
                SELECT
                    e.id,
                    e.entity_type,
                    COUNT(em.id) as mention_count,
                    LEAST(CEIL(samples.n / 7.0), 12) as threshold,
                    CASE
                        WHEN COUNT(em.id) < LEAST(CEIL(samples.n / 7.0), 12)
                             AND samples.n >= 1
                             AND (e.pruning_metadata->>'preserve' IS NULL OR e.pruning_metadata->>'preserve' != 'true')
                        THEN 1
                        ELSE 0
                    END as would_prune
                FROM entities e
                LEFT JOIN entity_mentions em ON e.id = em.entity_id
                CROSS JOIN LATERAL (
                    SELECT COUNT(*) AS n FROM sample_days sd
                    WHERE sd.d >= e.last_updated::date AND sd.d <= (SELECT ts FROM last_sample)
                ) samples
                GROUP BY e.id, e.entity_type, e.last_updated, e.pruning_metadata, samples.n
            )
            SELECT 
                entity_type,
                COUNT(*) as total_entities,
                SUM(would_prune) as prunable_entities,
                AVG(mention_count) as avg_mentions
            FROM entity_stats
            GROUP BY entity_type
            ORDER BY total_entities DESC
        """)
        
        results = session.execute(stats_query).fetchall()
        
        logger.info("\n=== Entity Pruning Statistics ===")
        logger.info(f"{'Type':<25} {'Total':>8} {'Prunable':>10} {'Avg Mentions':>12}")
        logger.info("-" * 60)
        
        total_all = 0
        total_prunable = 0
        
        for row in results:
            logger.info(f"{row.entity_type:<25} {row.total_entities:>8} "
                       f"{row.prunable_entities or 0:>10} {row.avg_mentions:>12.1f}")
            total_all += row.total_entities
            total_prunable += row.prunable_entities or 0
        
        logger.info("-" * 60)
        logger.info(f"{'TOTAL':<25} {total_all:>8} {total_prunable:>10}")
        logger.info(f"\nPruning would remove {total_prunable:,} entities ({total_prunable/total_all*100:.1f}%)")
        
    except Exception as e:
        logger.error(f"Error getting pruning stats: {e}")
        raise