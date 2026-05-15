from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_VERIFIED = "completed_verified"
    CLOSED = "closed"


class Incident(Base):
    """Incident model for waste management issues"""
    
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    observation_id = Column(Integer, ForeignKey("observations.id"))
    
    # Incident details
    description = Column(Text, nullable=False)
    priority = Column(String, default="medium")  # low, medium, high, urgent
    waste_type = Column(String)
    estimated_mass_g = Column(Float)
    
    # Status
    status = Column(SQLEnum(IncidentStatus), default=IncidentStatus.OPEN)
    
    # External references
    nyc_311_complaint_id = Column(String, unique=True)
    
    # Relationships
    zone = relationship("Zone", back_populates="incidents")
    work_orders = relationship("WorkOrder", back_populates="incident")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True))
