from typing import Optional, List
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.models.incident import Incident, IncidentStatus
from app.models.observation import Observation
from app.models.zone import Zone

logger = get_logger(__name__)


class IncidentService:
    """Service for incident management"""
    
    def create_incident(
        self,
        db: Session,
        zone_id: int,
        description: str,
        priority: str = "medium",
        observation_id: Optional[int] = None,
        waste_type: Optional[str] = None,
        estimated_mass_g: Optional[float] = None
    ) -> Incident:
        """
        Create a new incident
        """
        logger.info(
            "Creating incident",
            zone_id=zone_id,
            description=description
        )
        
        incident = Incident(
            zone_id=zone_id,
            observation_id=observation_id,
            description=description,
            priority=priority,
            waste_type=waste_type,
            estimated_mass_g=estimated_mass_g,
            status=IncidentStatus.OPEN
        )
        
        db.add(incident)
        db.commit()
        db.refresh(incident)
        
        logger.info(
            "Incident created successfully",
            incident_id=incident.id
        )
        
        return incident
    
    def get_incident(self, db: Session, incident_id: int) -> Optional[Incident]:
        """Get an incident by ID"""
        return db.query(Incident).filter(Incident.id == incident_id).first()
    
    def get_incidents_by_zone(
        self,
        db: Session,
        zone_id: int,
        status: Optional[IncidentStatus] = None
    ) -> List[Incident]:
        """Get incidents for a zone, optionally filtered by status"""
        query = db.query(Incident).filter(Incident.zone_id == zone_id)
        
        if status:
            query = query.filter(Incident.status == status)
        
        return query.all()
    
    def update_incident_status(
        self,
        db: Session,
        incident: Incident,
        new_status: IncidentStatus
    ) -> Incident:
        """Update incident status"""
        logger.info(
            "Updating incident status",
            incident_id=incident.id,
            old_status=incident.status,
            new_status=new_status
        )
        
        incident.status = new_status
        
        if new_status in [IncidentStatus.COMPLETED, IncidentStatus.CLOSED]:
            incident.closed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(incident)
        
        logger.info(
            "Incident status updated",
            incident_id=incident.id
        )
        
        return incident
    
    def get_open_incidents(self, db: Session) -> List[Incident]:
        """Get all open incidents"""
        return db.query(Incident).filter(
            Incident.status == IncidentStatus.OPEN
        ).all()
