from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.work_order import WorkOrder
from app.schemas.work_order import WorkOrderCreate, WorkOrderResponse
from app.services.dispatch_service import DispatchService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/work-orders", tags=["work-orders"])
dispatch_service = DispatchService()


@router.post("/", response_model=WorkOrderResponse)
def create_work_order(
    work_order: WorkOrderCreate,
    db: Session = Depends(get_db)
):
    """Create a new work order"""
    new_work_order = dispatch_service.assign_work_order(
        db=db,
        incident_id=work_order.incident_id,
        zone_id=work_order.zone_id,
        assigned_to=work_order.assigned_to,
        description=work_order.description,
        estimated_duration_hours=work_order.estimated_duration_hours
    )
    
    return new_work_order


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order(work_order_id: int, db: Session = Depends(get_db)):
    """Get a work order by ID"""
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    
    return work_order


@router.post("/{work_order_id}/complete", response_model=WorkOrderResponse)
def complete_work_order(
    work_order_id: int,
    actual_duration_hours: float,
    verification_id: int = None,
    db: Session = Depends(get_db)
):
    """Mark a work order as complete"""
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    
    completed_work_order = dispatch_service.complete_work_order(
        db=db,
        work_order=work_order,
        actual_duration_hours=actual_duration_hours,
        verification_id=verification_id
    )
    
    return completed_work_order
