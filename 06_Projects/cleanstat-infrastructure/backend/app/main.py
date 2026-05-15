"""
CleanStat Infrastructure - Main Application
Production-hardened FastAPI application
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import structlog
from contextlib import asynccontextmanager

from app.config import settings
from app.core.logging import configure_logging
from app.core.metrics import metrics_middleware, get_metrics
from app.db.base import engine
from app.models.base import Base
from app.routers import auth_router, observations_router
from app.middleware.rate_limit import limiter

# Configure logging
configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info(
        "Starting CleanStat Infrastructure",
        environment=settings.ENVIRONMENT
    )
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down CleanStat Infrastructure")


# Create FastAPI application
app = FastAPI(
    title="CleanStat Infrastructure",
    version="1.0.0",
    description="Digital infrastructure for municipal sanitation verification",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# ============================================================
# MIDDLEWARE
# ============================================================

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Prometheus metrics
app.middleware("http")(metrics_middleware)

# ============================================================
# EXCEPTION HANDLERS
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc):
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred"
        }
    )

# ============================================================
# ROUTERS
# ============================================================

app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(observations_router, prefix="/observations", tags=["observations"])

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": "CleanStat Infrastructure",
        "version": "1.0.0",
        "status": "operational",
        "environment": settings.ENVIRONMENT,
        "health": "/health",
        "metrics": "/metrics"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return await get_metrics()


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=4 if settings.ENVIRONMENT == "production" else 1,
        reload=settings.DEBUG,
        log_level="info"
    )
