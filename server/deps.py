"""Shared FastAPI dependencies for the consolidated server.

One DatabaseManager (one engine/connection pool) for the whole app. Routers and
the app module all depend on get_db, which closes the session after each request
- database.db.get_session() returns a raw session and was never closed when used
as a FastAPI dependency, which is why server/extension_api.py used to re-declare
router endpoints as wrappers just to swap the session dependency.
"""

import os

from sqlalchemy import func, text

from database.db import DatabaseManager
from database.models import Entity

database_url = os.getenv("DATABASE_URL", "postgresql://newsbias:newsbias@localhost:5432/news_bias")
db_manager = DatabaseManager(database_url)


def get_db():
    db = db_manager.get_session()
    try:
        yield db
    finally:
        db.close()


def resolve_entity_group(db, entity_id: int):
    """Resolve an entity id to its canonical row plus every id merged into it.

    Merges are pointer-based (Entity.canonical_id, set by
    analyzer/entity_resolution.py's weekly job) and mentions stay attached to
    the alias rows, so any per-entity aggregate must filter on the whole id
    group, not just the requested id. Alias ids are accepted: the caller gets
    the canonical row back for display.

    Returns (canonical_entity | None, [entity ids in the group]).
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        return None, []
    canonical = entity
    if entity.canonical_id:
        canonical = db.query(Entity).filter(
            Entity.id == entity.canonical_id).first() or entity
    group_ids = [eid for (eid,) in db.query(Entity.id).filter(
        func.coalesce(Entity.canonical_id, Entity.id) == canonical.id)]
    return canonical, group_ids or [entity.id]


# An entity's "all time" drops the leading weeks that together hold under
# max(JUNK_PREFIX_MIN, JUNK_PREFIX_SHARE of total) mentions, rather than using
# the raw MIN(week_start): ~290 articles carry bogus pre-corpus publish dates
# (min 2016-08), which put stray phantom weeks in mv_source_entity_week and
# leaked "all scored coverage (2017-03-27 to …)" onto public entity pages. A
# share-based rule (not a flat count) because mega-entities accumulate 50+
# junk-dated mentions across years of phantom weeks — any flat floor small
# enough to spare thin entities is met inside a mega-entity's junk tail.
JUNK_PREFIX_SHARE = 0.02
JUNK_PREFIX_MIN = 10


def first_solid_week(db, entity_id: int):
    """First mv_source_entity_week week for `entity_id` (a CANONICAL id — the
    MV pre-resolves aliases) once the junk-dated prefix is dropped: the first
    week where cumulative mentions exceed max(JUNK_PREFIX_MIN,
    JUNK_PREFIX_SHARE * total). Real first weeks clear that immediately;
    phantom prefix weeks never do. None when the entity has no scored weeks.
    """
    return db.execute(text("""
        SELECT MIN(week_start) FROM (
            SELECT week_start,
                   SUM(SUM(n)) OVER (ORDER BY week_start) AS cum_n,
                   SUM(SUM(n)) OVER () AS total_n
            FROM mv_source_entity_week
            WHERE entity_id = :entity_id
            GROUP BY week_start
        ) cums
        WHERE cum_n > GREATEST(:abs_min, :share * total_n)
    """), {"entity_id": entity_id, "abs_min": JUNK_PREFIX_MIN,
           "share": JUNK_PREFIX_SHARE}).scalar()
