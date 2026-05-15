"""API routers"""
from app.routers.auth import router as auth_router
from app.routers.observations import router as observations_router

__all__ = ["auth_router", "observations_router"]
