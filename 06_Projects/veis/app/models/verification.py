from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FRAUD_DETECTED = "fraud_detected"


class Verification(Base):
    """Cleanup verification model"""
    
    __tablename__ = "verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    observation_id = Column(Integer, ForeignKey("observations.id"), nullable=False)
    followup_image_url = Column(String, nullable=False)
    
    # Computed metrics
    removed_mass_g = Column(Float, nullable=False)
    fraud_risk_score = Column(Float, default=0.0)
    similarity_score = Column(Float)
    
    # Verification result
    status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING)
    verification_details = Column(JSON)
    
    # Relationships
    observation = relationship("Observation", back_populates="verifications")
    vcu = relationship("VCU", back_populates="verification", uselist=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True))
