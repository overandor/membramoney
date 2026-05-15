from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.db.database import init_db
from src.api.v1 import router as v1_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Membra API",
    description="Insured, identity-verified, payment-backed QR access for nearby physical assets.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)

@app.get("/")
def root():
    return {
        "name": "Membra",
        "tagline": "Insured, identity-verified, payment-backed QR access for nearby physical assets.",
        "docs": "/docs",
    }
