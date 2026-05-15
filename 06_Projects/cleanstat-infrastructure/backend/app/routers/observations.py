"""
CleanStat Infrastructure - Observations Router
Observation endpoint with idempotency and Celery processing
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from app.middleware.tenant import get_current_user, tenant_filter
from app.models.observation import Observation
from app.tasks.observation_tasks import process_observation
from app.db.session import get_db
from app.db.redis_client import redis_client
from app.middleware.rate_limit import limiter
from sqlalchemy.orm import Session
import uuid

router = APIRouter()

class ObservationCreate(BaseModel):
    image_cid: str
    gps_lat: float
    gps_lon: float
    bin_id: str

@router.post("/", status_code=202)
@limiter.limit("100/minute")
async def create_observation(
    data: ObservationCreate,
    request: Request,
    idempotency_key: str = Header(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create observation with idempotency support"""
    # Idempotency check using Redis
    if idempotency_key:
        existing = redis_client.get(f"idem:{idempotency_key}")
        if existing:
            return {"id": existing, "status": "already_processed"}

    obs = Observation(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        creator_wallet=current_user.wallet_address,
        image_cid=data.image_cid,
        gps_lat=data.gps_lat,
        gps_lon=data.gps_lon,
        bin_id=data.bin_id,
        status="pending"
    )
    db.add(obs)
    db.commit()

    # Store idempotency key
    if idempotency_key:
        redis_client.setex(f"idem:{idempotency_key}", 3600, obs.id)

    # Queue async processing
    process_observation.delay(obs.id)

    return {"id": obs.id, "status_url": f"/observations/{obs.id}/status"}

@router.get("/{observation_id}")
async def get_observation(
    observation_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get observation by ID with tenant filtering"""
    query = db.query(Observation).filter(Observation.id == observation_id)
    query = tenant_filter(query, current_user)
    obs = query.first()
    
    if not obs:
        raise HTTPException(404, "Observation not found")
    
    return obs

@router.get("/")
async def list_observations(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """List observations with tenant filtering"""
    query = db.query(Observation)
    query = tenant_filter(query, current_user)
    query = query.offset(skip).limit(limit)
    
    observations = query.all()
    return {"observations": observations, "count": len(observations)}

@router.get("/{observation_id}/status")
async def get_observation_status(
    observation_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get observation processing status"""
    query = db.query(Observation).filter(Observation.id == observation_id)
    query = tenant_filter(query, current_user)
    obs = query.first()
    
    if not obs:
        raise HTTPException(404, "Observation not found")
    
    return {
        "id": obs.id,
        "status": obs.status,
        "created_at": obs.created_at,
        "processed_at": obs.processed_at
    }
