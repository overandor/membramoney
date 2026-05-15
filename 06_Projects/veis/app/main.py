from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import engine, Base
from app.api import (
    observations_router,
    verifications_router,
    vcus_router,
    incidents_router,
    work_orders_router,
    zones_router,
    nyc_router,
    auth_router
)
from app.auth_service import create_gradio_app
import gradio as gr

# Configure logging
configure_logging()
logger = get_logger(__name__)
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Verified Environmental Intelligence System (VEIS) - Municipal waste management platform",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://veis.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(observations_router)
app.include_router(verifications_router)
app.include_router(vcus_router)
app.include_router(incidents_router)
app.include_router(work_orders_router)
app.include_router(zones_router)
app.include_router(nyc_router)
app.include_router(auth_router)

# Mount Gradio app
demo = create_gradio_app()
app = gr.mount_gradio_app(app, demo, path="/app")


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info(
        "Starting VEIS application",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment
    )
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    logger.info("Database tables created")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("Shutting down VEIS application")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "healthy",
        "environment": settings.environment
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
