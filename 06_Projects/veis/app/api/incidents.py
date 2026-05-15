from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentResponse
from app.services.incident_service import IncidentService
from app.services.dispatch_service import DispatchService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/incidents", tags=["incidents"])
incident_service = IncidentService()
dispatch_service = DispatchService()


@router.post("/", response_model=IncidentResponse)
def create_incident(
    incident: IncidentCreate,
    db: Session = Depends(get_db)
):
    """Create a new incident"""
    new_incident = incident_service.create_incident(
        db=db,
        zone_id=incident.zone_id,
        description=incident.description,
        priority=incident.priority,
        observation_id=incident.observation_id,
        waste_type=incident.waste_type,
        estimated_mass_g=incident.estimated_mass_g
    )
    
    return new_incident


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Get an incident by ID"""
    incident = incident_service.get_incident(db, incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return incident


@router.get("/", response_model=list[IncidentResponse])
def list_incidents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all incidents with pagination"""
    incidents = db.query(Incident).offset(skip).limit(limit).all()
    return incidents


@router.post("/{incident_id}/dispatch")
def dispatch_incident(incident_id: int, db: Session = Depends(get_db)):
    """
    Auto-dispatch a work order for an incident
    """
    incident = incident_service.get_incident(db, incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    work_order = dispatch_service.auto_dispatch(db, incident)
    
    if not work_order:
        raise HTTPException(status_code=400, detail="Could not dispatch work order")
    
    return {"work_order_id": work_order.id, "status": "dispatched"}
