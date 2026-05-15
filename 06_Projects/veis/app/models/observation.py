from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class ObservationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Observation(Base):
    """Waste observation model"""
    
    __tablename__ = "observations"
    
    id = Column(Integer, primary_key=True, index=True)
    image_url = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String)
    waste_type = Column(String)  # plastic, organic, hazardous, etc.
    estimated_mass_g = Column(Float)
    confidence_score = Column(Float)
    status = Column(SQLEnum(ObservationStatus), default=ObservationStatus.PENDING)
    detection_result = Column(Text)  # JSON string
    error_message = Column(Text)
    
    # Relationships
    verifications = relationship("Verification", back_populates="observation")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True))
