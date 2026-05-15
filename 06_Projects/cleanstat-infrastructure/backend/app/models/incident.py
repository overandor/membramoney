"""
CleanStat Infrastructure - Incident Model
Waste management incident for city operations
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class IncidentStatus(str, enum.Enum):
    """Incident status"""
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_VERIFIED = "completed_verified"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class IncidentPriority(str, enum.Enum):
    """Incident priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class Incident(Base):
    """Waste management incident model"""
    
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    observation_id = Column(Integer, ForeignKey("observations.id"), unique=True, nullable=True)
    
    # Incident details
    incident_number = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    priority = Column(SQLEnum(IncidentPriority), default=IncidentPriority.MEDIUM)
    
    # Waste information
    waste_type = Column(String(50))
    estimated_mass_g = Column(Float)
    estimated_volume_m3 = Column(Float)
    waste_description = Column(Text)
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(String(500))
    
    # Status
    status = Column(SQLEnum(IncidentStatus), default=IncidentStatus.OPEN)
    
    # External references
    nyc_311_complaint_id = Column(String(50), unique=True, nullable=True)
    external_reference = Column(String(100))
    
    # Assignment
    assigned_team_id = Column(String(50))
    assigned_team_name = Column(String(100))
    
    # Resolution
    resolution_notes = Column(Text)
    resolution_image_url = Column(String(500))
    resolution_image_hash = Column(String(64))
    
    # Metrics
    response_time_minutes = Column(Integer)
    resolution_time_hours = Column(Float)
    cost_usd = Column(Float)
    
    # Relationships
    zone = relationship("Zone", back_populates="incidents")
    observation = relationship("Observation", back_populates="incident")
    work_orders = relationship("WorkOrder", back_populates="incident")
    
    # Audit
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))
    closed_by = Column(Integer, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    assigned_at = Column(DateTime(timezone=True))
    in_progress_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    verified_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
