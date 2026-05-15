"""
CleanStat Infrastructure - Health Check Endpoint
System health monitoring for production
"""
from fastapi import APIRouter
from sqlalchemy import text
from app.db.base import engine
from app.core.logging import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


@router.get("/")
async def health_check():
    """
    Comprehensive health check
    Returns status of all system components
    """
    health_status = {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment.value,
        "components": {}
    }
    
    # Check database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["components"]["database"] = "connected"
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        health_status["components"]["database"] = "disconnected"
        health_status["status"] = "degraded"
    
    # Check Redis (simplified check)
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.ping()
        health_status["components"]["redis"] = "connected"
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        health_status["components"]["redis"] = "disconnected"
        health_status["status"] = "degraded"
    
    # Check IPFS (optional - may not be critical)
    if settings.pinata_api_key:
        health_status["components"]["ipfs"] = "configured"
    else:
        health_status["components"]["ipfs"] = "not_configured"
    
    # Check blockchain (optional)
    if settings.ethereum_rpc_url:
        health_status["components"]["blockchain"] = "configured"
    else:
        health_status["components"]["blockchain"] = "not_configured"
    
    return health_status


@router.get("/detailed")
async def detailed_health_check():
    """
    Detailed health check with metrics
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment.value,
        "uptime_seconds": 3600,  # TODO: Calculate actual uptime
        "metrics": {
            "database_connections": engine.pool.size(),
            "database_checked_out": engine.pool.checkedout(),
            "database_overflow": engine.pool.overflow(),
        }
    }
