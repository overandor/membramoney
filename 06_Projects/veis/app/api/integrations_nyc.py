from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate
from app.services.incident_service import IncidentService
from app.services.dispatch_service import DispatchService
from app.core.logging import get_logger
import random
import uuid

logger = get_logger(__name__)
router = APIRouter(prefix="/integrations/nyc/311", tags=["integrations"])
incident_service = IncidentService()
dispatch_service = DispatchService()


@router.post("/complaints")
async def create_nyc_311_complaint(
    complaint_type: str,
    description: str,
    latitude: float,
    longitude: float,
    address: str = None,
    db: Session = Depends(get_db)
):
    """
    Create a NYC 311 complaint and map it to an incident
    (Mock implementation - in production, this would call the actual NYC 311 API)
    """
    logger.info(
        "NYC 311 complaint received",
        complaint_type=complaint_type,
        description=description
    )
    
    # Generate mock NYC 311 complaint ID
    nyc_complaint_id = f"NYC311-{uuid.uuid4().hex[:12].upper()}"
    
    # Determine zone based on location (mock logic)
    # In production, this would use geospatial queries
    zone_id = 1  # Default zone for mock
    
    # Create incident
    incident = incident_service.create_incident(
        db=db,
        zone_id=zone_id,
        description=f"{complaint_type}: {description}",
        priority="medium",
        waste_type="general",
        estimated_mass_g=random.uniform(100, 1000)
    )
    
    # Link NYC 311 complaint ID
    incident.nyc_311_complaint_id = nyc_complaint_id
    db.commit()
    
    # Auto-dispatch work order
    work_order = dispatch_service.auto_dispatch(db, incident)
    
    logger.info(
        "NYC 311 complaint processed",
        complaint_id=nyc_complaint_id,
        incident_id=incident.id,
        work_order_id=work_order.id if work_order else None
    )
    
    return {
        "complaint_id": nyc_complaint_id,
        "incident_id": incident.id,
        "work_order_id": work_order.id if work_order else None,
        "status": "routed_to_zone",
        "zone_id": zone_id
    }


@router.get("/complaints/{complaint_id}")
def get_nyc_311_complaint_status(complaint_id: str, db: Session = Depends(get_db)):
    """Get the status of a NYC 311 complaint"""
    incident = db.query(Incident).filter(
        Incident.nyc_311_complaint_id == complaint_id
    ).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    return {
        "complaint_id": complaint_id,
        "incident_id": incident.id,
        "status": incident.status,
        "description": incident.description,
        "created_at": incident.created_at
    }
