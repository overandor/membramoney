"""
CleanStat Infrastructure - Observation Model
Waste observation with image and GPS data
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class ObservationStatus(str, enum.Enum):
    """Observation processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class Observation(Base):
    """Waste observation model"""
    
    __tablename__ = "observations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Image data
    image_url = Column(String(500), nullable=False)
    image_hash = Column(String(64), unique=True, nullable=False, index=True)  # IPFS hash
    thumbnail_url = Column(String(500))
    
    # Location data
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float)
    accuracy = Column(Float)  # GPS accuracy in meters
    
    # Address data
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(50))
    zip_code = Column(String(10))
    country = Column(String(50), default="USA")
    
    # Waste data
    waste_type = Column(String(50))  # plastic, organic, hazardous, etc.
    estimated_mass_g = Column(Float)
    estimated_volume_m3 = Column(Float)
    waste_description = Column(Text)
    
    # AI detection results
    confidence_score = Column(Float)
    detection_model_version = Column(String(20))
    detection_result = Column(JSON)  # Full AI detection output
    bounding_boxes = Column(JSON)  # Detected waste bounding boxes
    
    # Processing status
    status = Column(SQLEnum(ObservationStatus), default=ObservationStatus.PENDING)
    error_message = Column(Text)
    processing_time_ms = Column(Integer)
    
    # IPFS metadata
    ipfs_cid = Column(String(64))
    ipfs_gateway_url = Column(String(500))
    
    # Blockchain
    transaction_hash = Column(String(66))
    block_number = Column(Integer)
    
    # Relationships
    verifications = relationship("Verification", back_populates="observation")
    incident = relationship("Incident", back_populates="observation", uselist=False)
    
    # Audit
    submitted_by = Column(Integer, ForeignKey("users.id"))
    verified_by = Column(Integer, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True))
    verified_at = Column(DateTime(timezone=True))
