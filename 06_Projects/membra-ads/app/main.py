from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.db.database import init_db, get_db
from app.api import owners, advertisers, assets, campaigns, media_kits, proof, payments, analytics, webhooks

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Membra Ads API",
    description="Certified campaign kit system. Membra controls campaign IDs, QR/NFC tracking, proof verification, and payouts. Vendors handle printing and shipping.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/v1/health")
def health():
    return {"status": "ok", "service": "membra-ads"}

# Router mounts
app.include_router(owners.router, prefix="/v1")
app.include_router(advertisers.router, prefix="/v1")
app.include_router(assets.router, prefix="/v1")
app.include_router(campaigns.router, prefix="/v1")
app.include_router(media_kits.router, prefix="/v1")
app.include_router(proof.router, prefix="/v1")
app.include_router(payments.router, prefix="/v1")
app.include_router(analytics.router, prefix="/v1")
app.include_router(webhooks.router, prefix="/v1")

# Public QR redirect
@app.get("/t/{qr_id}")
def track_qr(qr_id: str, request: Request, db=Depends(get_db)):
    from app.db.models import QRTag, ScanEvent
    from sqlalchemy.orm import Session
    import json

    qr = db.query(QRTag).filter(QRTag.qr_id == qr_id).first()
    if not qr or not qr.is_active:
        raise HTTPException(404, "QR not found")

    # Log scan event
    scan = ScanEvent(
        qr_id=qr_id,
        campaign_id=qr.kit_id,  # simplified; fetch from kit in real impl
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(scan)
    qr.scan_count = (qr.scan_count or 0) + 1
    db.commit()

    return RedirectResponse(url=qr.redirect_url or "https://membra.app")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
