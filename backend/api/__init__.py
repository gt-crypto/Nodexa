"""API route definitions."""
from backend.api.health import router as health_router
from backend.api.data import router as data_router

__all__ = [
    "health_router",
    "data_router",
]
