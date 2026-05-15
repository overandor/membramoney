from app.api.observations import router as observations_router
from app.api.verifications import router as verifications_router
from app.api.vcus import router as vcus_router
from app.api.incidents import router as incidents_router
from app.api.work_orders import router as work_orders_router
from app.api.zones import router as zones_router
from app.api.integrations_nyc import router as nyc_router
from app.api.auth import router as auth_router

__all__ = [
    "observations_router",
    "verifications_router",
    "vcus_router",
    "incidents_router",
    "work_orders_router",
    "zones_router",
    "nyc_router",
    "auth_router"
]
