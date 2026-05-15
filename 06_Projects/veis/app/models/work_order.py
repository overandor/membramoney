from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class WorkOrderStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"


class WorkOrder(Base):
    """Work order model for cleanup assignments"""
    
    __tablename__ = "work_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    
    # Assignment details
    assigned_to = Column(String, nullable=False)  # Worker ID or team
    assigned_at = Column(DateTime(timezone=True))
    
    # Work details
    description = Column(Text, nullable=False)
    estimated_duration_hours = Column(Float)
    actual_duration_hours = Column(Float)
    
    # Status
    status = Column(SQLEnum(WorkOrderStatus), default=WorkOrderStatus.PENDING)
    
    # Completion
    completed_at = Column(DateTime(timezone=True))
    verification_id = Column(Integer, ForeignKey("verifications.id"))
    
    # Relationships
    incident = relationship("Incident", back_populates="work_orders")
    zone = relationship("Zone", back_populates="work_orders")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
