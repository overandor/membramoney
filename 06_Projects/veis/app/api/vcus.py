from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.vcu import VCU
from app.schemas.vcu import VCUResponse, VCUTransfer
from app.services.vcu_service import VCUService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/vcus", tags=["vcus"])
vcu_service = VCUService()


@router.get("/{vcu_id}", response_model=VCUResponse)
def get_vcu(vcu_id: int, db: Session = Depends(get_db)):
    """Get a VCU by ID"""
    vcu = db.query(VCU).filter(VCU.id == vcu_id).first()
    
    if not vcu:
        raise HTTPException(status_code=404, detail="VCU not found")
    
    return vcu


@router.post("/{vcu_id}/transfer", response_model=VCUResponse)
def transfer_vcu(
    vcu_id: int,
    transfer: VCUTransfer,
    db: Session = Depends(get_db)
):
    """Transfer ownership of a VCU"""
    vcu = db.query(VCU).filter(VCU.id == vcu_id).first()
    
    if not vcu:
        raise HTTPException(status_code=404, detail="VCU not found")
    
    # Perform transfer
    updated_vcu = vcu_service.transfer_vcu(vcu, transfer.new_owner)
    
    db.commit()
    db.refresh(updated_vcu)
    
    logger.info(
        "VCU transferred",
        vcu_id=vcu.id,
        to_owner=transfer.new_owner
    )
    
    return updated_vcu
