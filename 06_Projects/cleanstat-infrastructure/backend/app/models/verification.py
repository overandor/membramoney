"""
CleanStat Infrastructure - Verification Model
Cleanup verification comparing baseline and follow-up images
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class VerificationStatus(str, enum.Enum):
    """Verification status"""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FRAUD_DETECTED = "fraud_detected"
    NEEDS_REVIEW = "needs_review"


class Verification(Base):
    """Cleanup verification model"""
    
    __tablename__ = "verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    observation_id = Column(Integer, ForeignKey("observations.id"), nullable=False)
    
    # Follow-up image data
    followup_image_url = Column(String(500), nullable=False)
    followup_image_hash = Column(String(64), unique=True, nullable=False)
    followup_thumbnail_url = Column(String(500))
    
    # Verification metrics
    removed_mass_g = Column(Float, nullable=False)
    removed_volume_m3 = Column(Float)
    similarity_score = Column(Float)  # 0.0 = identical, 1.0 = completely different
    fraud_risk_score = Column(Float, default=0.0)  # 0.0 = no risk, 1.0 = high risk
    confidence_score = Column(Float)
    
    # Verification details
    status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING)
    verification_method = Column(String(50))  # image_similarity, manual, hybrid
    verification_details = Column(JSON)
    
    # AI analysis
    ai_model_version = Column(String(20))
    ai_analysis_result = Column(JSON)
    
    # IPFS
    ipfs_cid = Column(String(64))
    ipfs_gateway_url = Column(String(500))
    
    # Blockchain
    transaction_hash = Column(String(66))
    block_number = Column(Integer)
    
    # Relationships
    observation = relationship("Observation", back_populates="verifications")
    vcu = relationship("VCU", back_populates="verification", uselist=False)
    
    # Audit
    verified_by = Column(Integer, ForeignKey("users.id"))
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    review_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    verified_at = Column(DateTime(timezone=True))
    reviewed_at = Column(DateTime(timezone=True))
