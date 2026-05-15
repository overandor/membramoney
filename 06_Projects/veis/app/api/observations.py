from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.observation import Observation, ObservationStatus
from app.schemas.observation import ObservationCreate, ObservationResponse
from app.services.detection_service import DetectionService
from app.workers.tasks import process_observation_task
from app.core.logging import get_logger
import os
from datetime import datetime

logger = get_logger(__name__)
router = APIRouter(prefix="/observations", tags=["observations"])
detection_service = DetectionService()


@router.post("/", response_model=ObservationResponse)
async def create_observation(
    latitude: float,
    longitude: float,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    address: str = None,
    waste_type: str = None,
    estimated_mass_g: float = None
):
    """
    Create a new waste observation with image upload
    """
    # Validate file
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save uploaded file
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = f"{upload_dir}/{datetime.utcnow().timestamp()}_{file.filename}"
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Create observation record
    observation = Observation(
        image_url=file_path,
        latitude=latitude,
        longitude=longitude,
        address=address,
        waste_type=waste_type,
        estimated_mass_g=estimated_mass_g,
        status=ObservationStatus.PENDING
    )
    
    db.add(observation)
    db.commit()
    db.refresh(observation)
    
    # Trigger async processing
    process_observation_task.delay(observation.id)
    
    logger.info(
        "Observation created and processing started",
        observation_id=observation.id
    )
    
    return observation


@router.get("/{observation_id}", response_model=ObservationResponse)
def get_observation(observation_id: int, db: Session = Depends(get_db)):
    """Get an observation by ID"""
    observation = db.query(Observation).filter(Observation.id == observation_id).first()
    
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")
    
    return observation


@router.get("/", response_model=list[ObservationResponse])
def list_observations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all observations with pagination"""
    observations = db.query(Observation).offset(skip).limit(limit).all()
    return observations
