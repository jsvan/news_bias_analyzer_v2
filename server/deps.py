"""Shared FastAPI dependencies for the consolidated server.

One DatabaseManager (one engine/connection pool) for the whole app. Routers and
the app module all depend on get_db, which closes the session after each request
- database.db.get_session() returns a raw session and was never closed when used
as a FastAPI dependency, which is why server/extension_api.py used to re-declare
router endpoints as wrappers just to swap the session dependency.
"""

import os

from sqlalchemy import func

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
