from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.core.config import settings
from app.db.base import Base, engine
from app.api import auth, chats, google

# Create tables
Base.metadata.create_all(bind=engine)

# Rate limiter (disabled for minimal setup)
# limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Chat Provenance API", version="1.0.0")
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for UI
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(chats.router, prefix="/api/chats", tags=["chats"])
app.include_router(google.router, prefix="/api/google", tags=["google-drive"])


@app.get("/")
def root():
    # Serve the UI if static files exist
    ui_path = os.path.join(static_dir, "index.html")
    if os.path.exists(ui_path):
        return FileResponse(ui_path)
    return {
        "message": "Chat Provenance API",
        "version": "1.0.0",
        "docs": "/docs",
        "ui": "/static/index.html"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
