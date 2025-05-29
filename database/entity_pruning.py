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
from statistical_database.db_manager import StatisticalDBManager

logger = logging.getLogger(__name__)

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
    Prune entities based on dynamic threshold.
    
    Threshold = min(weeks_since_last_update, 12)
    
    Args:
        session: Database session
        dry_run: If True, only report what would be deleted
    
    Returns:
        Number of entities pruned
    """
    try:
        # First ensure we have the last_updated column and trigger
        add_last_updated_column(session)
        update_entity_last_updated_trigger(session)
        
        # Find entities to prune
        query = text("""
            WITH entity_stats AS (
                SELECT 
                    e.id,
                    e.name,
                    e.entity_type,
                    e.last_updated,
                    COUNT(em.id) as mention_count,
                    EXTRACT(EPOCH FROM (NOW() - e.last_updated)) / 604800 as weeks_old,
                    LEAST(CEIL(EXTRACT(EPOCH FROM (NOW() - e.last_updated)) / 604800), 12) as threshold
                FROM entities e
                LEFT JOIN entity_mentions em ON e.id = em.entity_id
                WHERE 
                    -- Skip entities marked for preservation
                    (e.pruning_metadata->>'preserve' IS NULL OR e.pruning_metadata->>'preserve' != 'true')
                    -- Only consider entities older than 1 week
                    AND e.last_updated < NOW() - INTERVAL '7 days'
                GROUP BY e.id, e.name, e.entity_type, e.last_updated
                HAVING 
                    -- Mention count is below the dynamic threshold
                    COUNT(em.id) < LEAST(CEIL(EXTRACT(EPOCH FROM (NOW() - e.last_updated)) / 604800), 12)
            )
            SELECT 
                id, 
                name, 
                entity_type, 
                mention_count, 
                ROUND(weeks_old::numeric, 1) as weeks_old,
                threshold
            FROM entity_stats
            ORDER BY mention_count, weeks_old DESC
        """)
        
        candidates = session.execute(query).fetchall()
        
        if not candidates:
            logger.info("No entities to prune")
            return 0
        
        # Log summary
        logger.info(f"Found {len(candidates)} entities to prune")
        
        # Show some examples
        examples = candidates[:10]
        for entity in examples:
            logger.info(f"  - {entity.name} ({entity.entity_type}): "
                       f"{entity.mention_count} mentions, "
                       f"{entity.weeks_old} weeks old, "
                       f"threshold: {entity.threshold}")
        
        if len(candidates) > 10:
            logger.info(f"  ... and {len(candidates) - 10} more")
        
        if dry_run:
            logger.info("DRY RUN - No entities were deleted")
            return len(candidates)
        
        # Delete the entities
        entity_ids = [c.id for c in candidates]
        
        # Delete in batches to avoid overwhelming the database
        batch_size = 1000
        total_deleted = 0
        
        for i in range(0, len(entity_ids), batch_size):
            batch_ids = entity_ids[i:i + batch_size]
            
            # Note: CASCADE will handle entity_mentions deletion
            result = session.execute(
                text("DELETE FROM entities WHERE id = ANY(:ids)"),
                {"ids": batch_ids}
            )
            
            batch_deleted = result.rowcount
            total_deleted += batch_deleted
            
            logger.info(f"Deleted batch {i//batch_size + 1}: {batch_deleted} entities")
            session.commit()
        
        logger.info(f"Successfully pruned {total_deleted} low-activity entities")
        
        # Update the running total in statistical database
        try:
            stats_db = StatisticalDBManager()
            new_total = stats_db.increment_system_metric('total_entities_deleted', total_deleted)
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
        
        stats_query = text("""
            WITH entity_stats AS (
                SELECT 
                    e.id,
                    e.entity_type,
                    COUNT(em.id) as mention_count,
                    LEAST(CEIL(EXTRACT(EPOCH FROM (NOW() - e.last_updated)) / 604800), 12) as threshold,
                    CASE 
                        WHEN COUNT(em.id) < LEAST(CEIL(EXTRACT(EPOCH FROM (NOW() - e.last_updated)) / 604800), 12)
                             AND e.last_updated < NOW() - INTERVAL '7 days'
                             AND (e.pruning_metadata->>'preserve' IS NULL OR e.pruning_metadata->>'preserve' != 'true')
                        THEN 1 
                        ELSE 0 
                    END as would_prune
                FROM entities e
                LEFT JOIN entity_mentions em ON e.id = em.entity_id
                GROUP BY e.id, e.entity_type, e.last_updated, e.pruning_metadata
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