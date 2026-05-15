from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.observation import Observation
from app.models.verification import Verification, VerificationStatus
from app.schemas.verification import VerificationCreate, VerificationResponse
from app.services.verification_service import VerificationService
from app.services.vcu_service import VCUService
from app.core.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)
router = APIRouter(prefix="/verifications", tags=["verifications"])
verification_service = VerificationService()
vcu_service = VCUService()


@router.post("/", response_model=VerificationResponse)
async def create_verification(
    verification: VerificationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a cleanup verification
    """
    # Get observation
    observation = db.query(Observation).filter(
        Observation.id == verification.observation_id
    ).first()
    
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")
    
    # Perform verification
    result = await verification_service.verify_cleanup(
        observation=observation,
        followup_image_url=verification.followup_image_url
    )
    
    # Create verification record
    verification_record = Verification(
        observation_id=verification.observation_id,
        followup_image_url=verification.followup_image_url,
        removed_mass_g=result["removed_mass_g"],
        fraud_risk_score=result["fraud_risk_score"],
        similarity_score=result["similarity_score"],
        status=result["status"],
        verification_details=result["verification_details"],
        verified_at=datetime.utcnow()
    )
    
    db.add(verification_record)
    db.commit()
    db.refresh(verification_record)
    
    # Generate VCU if verified
    if result["status"] == VerificationStatus.VERIFIED:
        vcu = vcu_service.generate_vcu(
            verification=verification_record,
            amount_kg=result["removed_mass_g"],
            owner="system"  # In production, this would be the submitter
        )
        db.add(vcu)
        db.commit()
    
    logger.info(
        "Verification created",
        verification_id=verification_record.id,
        status=result["status"]
    )
    
    return verification_record


@router.get("/{verification_id}", response_model=VerificationResponse)
def get_verification(verification_id: int, db: Session = Depends(get_db)):
    """Get a verification by ID"""
    verification = db.query(Verification).filter(
        Verification.id == verification_id
    ).first()
    
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    return verification
