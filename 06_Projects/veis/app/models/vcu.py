from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class VCUStatus(str, enum.Enum):
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    REDEEMED = "redeemed"
    EXPIRED = "expired"


class VCU(Base):
    """Verified Cleanup Unit (VCU) model"""
    
    __tablename__ = "vcus"
    
    id = Column(Integer, primary_key=True, index=True)
    verification_id = Column(Integer, ForeignKey("verifications.id"), nullable=False)
    token_id = Column(String, unique=True, nullable=False)  # Blockchain/token ID
    amount = Column(Float, nullable=False)  # Amount in kg CO2 equivalent
    
    # Ownership
    current_owner = Column(String, nullable=False)
    original_owner = Column(String, nullable=False)
    
    # Status
    status = Column(SQLEnum(VCUStatus), default=VCUStatus.ACTIVE)
    transfer_history = Column(String)  # JSON string of transfer history
    
    # Metadata
    metadata = Column(String)  # JSON string for additional metadata
    
    # Relationships
    verification = relationship("Verification", back_populates="vcu")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    transferred_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
