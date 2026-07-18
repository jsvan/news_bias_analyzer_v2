"""Routers for the single consolidated FastAPI app (server/extension_api.py).

Every endpoint is declared in exactly one place - no wrapper re-declarations.
All routers use server.deps.get_db so sessions are closed per request.
"""
