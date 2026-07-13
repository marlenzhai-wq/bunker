"""Telegram handlers."""

from app.handlers.admin import router as admin_router
from app.handlers.game import router as game_router

__all__ = ("admin_router", "game_router")
