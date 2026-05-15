from typing import List
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.models.incident import Incident, IncidentStatus
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.models.zone import Zone

logger = get_logger(__name__)


class DispatchService:
    """Service for dispatching work orders to cleanup crews"""
    
    def assign_work_order(
        self,
        db: Session,
        incident_id: int,
        zone_id: int,
        assigned_to: str,
        description: str,
        estimated_duration_hours: float = 2.0
    ) -> WorkOrder:
        """
        Assign a work order to a cleanup crew
        """
        logger.info(
            "Assigning work order",
            incident_id=incident_id,
            assigned_to=assigned_to
        )
        
        work_order = WorkOrder(
            incident_id=incident_id,
            zone_id=zone_id,
            assigned_to=assigned_to,
            assigned_at=datetime.utcnow(),
            description=description,
            estimated_duration_hours=estimated_duration_hours,
            status=WorkOrderStatus.ASSIGNED
        )
        
        db.add(work_order)
        db.commit()
        db.refresh(work_order)
        
        # Update incident status
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if incident:
            incident.status = IncidentStatus.ASSIGNED
            db.commit()
        
        # Update zone active work orders count
        zone = db.query(Zone).filter(Zone.id == zone_id).first()
        if zone:
            zone.active_work_orders += 1
            db.commit()
        
        logger.info(
            "Work order assigned successfully",
            work_order_id=work_order.id
        )
        
        return work_order
    
    def auto_dispatch(
        self,
        db: Session,
        incident: Incident
    ) -> Optional[WorkOrder]:
        """
        Automatically dispatch a work order based on incident priority and zone
        """
        logger.info(
            "Auto-dispatching work order",
            incident_id=incident.id
        )
        
        # Get zone
        zone = db.query(Zone).filter(Zone.id == incident.zone_id).first()
        if not zone:
            logger.warning("Zone not found for incident", incident_id=incident.id)
            return None
        
        # Simple dispatch logic: assign to zone team
        # In production, this would use more sophisticated scheduling
        assigned_to = f"zone_{zone.zone_code}_team"
        
        description = f"Cleanup required: {incident.description}"
        
        if incident.priority == "urgent":
            estimated_duration = 1.0
        elif incident.priority == "high":
            estimated_duration = 2.0
        else:
            estimated_duration = 4.0
        
        work_order = self.assign_work_order(
            db=db,
            incident_id=incident.id,
            zone_id=zone.id,
            assigned_to=assigned_to,
            description=description,
            estimated_duration_hours=estimated_duration
        )
        
        return work_order
    
    def get_pending_work_orders(
        self,
        db: Session,
        zone_id: Optional[int] = None
    ) -> List[WorkOrder]:
        """Get pending work orders, optionally filtered by zone"""
        query = db.query(WorkOrder).filter(
            WorkOrder.status == WorkOrderStatus.PENDING
        )
        
        if zone_id:
            query = query.filter(WorkOrder.zone_id == zone_id)
        
        return query.all()
    
    def complete_work_order(
        self,
        db: Session,
        work_order: WorkOrder,
        actual_duration_hours: float,
        verification_id: Optional[int] = None
    ) -> WorkOrder:
        """
        Mark a work order as complete
        """
        logger.info(
            "Completing work order",
            work_order_id=work_order.id
        )
        
        work_order.status = WorkOrderStatus.COMPLETED
        work_order.completed_at = datetime.utcnow()
        work_order.actual_duration_hours = actual_duration_hours
        work_order.verification_id = verification_id
        
        db.commit()
        db.refresh(work_order)
        
        # Update incident status
        incident = db.query(Incident).filter(
            Incident.id == work_order.incident_id
        ).first()
        if incident:
            if verification_id:
                incident.status = IncidentStatus.COMPLETED_VERIFIED
            else:
                incident.status = IncidentStatus.COMPLETED
            db.commit()
        
        # Update zone active work orders count
        zone = db.query(Zone).filter(Zone.id == work_order.zone_id).first()
        if zone and zone.active_work_orders > 0:
            zone.active_work_orders -= 1
            db.commit()
        
        logger.info(
            "Work order completed",
            work_order_id=work_order.id
        )
        
        return work_order
