"""Shared FastAPI dependencies for the consolidated server.

One DatabaseManager (one engine/connection pool) for the whole app. Routers and
the app module all depend on get_db, which closes the session after each request
- database.db.get_session() returns a raw session and was never closed when used
as a FastAPI dependency, which is why server/extension_api.py used to re-declare
router endpoints as wrappers just to swap the session dependency.
"""

import os

from database.db import DatabaseManager

database_url = os.getenv("DATABASE_URL", "postgresql://newsbias:newsbias@localhost:5432/news_bias")
db_manager = DatabaseManager(database_url)


def get_db():
    db = db_manager.get_session()
    try:
        yield db
    finally:
        db.close()
