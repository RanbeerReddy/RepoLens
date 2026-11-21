"""API layer — routers and dependency injection."""

from app.api.dependencies import get_db, get_settings

__all__ = [
    "get_db",
    "get_settings",
]
