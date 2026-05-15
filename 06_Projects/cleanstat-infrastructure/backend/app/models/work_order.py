"""
CleanStat Infrastructure - Work Order Model
Cleanup crew assignment and tracking
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class WorkOrderStatus(str, enum.Enum):
    """Work order status"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    CANCELLED = "cancelled"


class WorkOrder(Base):
    """Work order model for cleanup crew assignments"""
    
    __tablename__ = "work_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    
    # Work order details
    work_order_number = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="medium")
    
    # Assignment
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_team_id = Column(String(50))
    assigned_team_name = Column(String(100))
    assigned_at = Column(DateTime(timezone=True))
    
    # Scheduling
    scheduled_start = Column(DateTime(timezone=True))
    scheduled_end = Column(DateTime(timezone=True))
    estimated_duration_hours = Column(Float)
    actual_duration_hours = Column(Float)
    
    # Work details
    equipment_required = Column(Text)  # JSON string
    personnel_required = Column(Integer)
    special_instructions = Column(Text)
    
    # Status
    status = Column(SQLEnum(WorkOrderStatus), default=WorkOrderStatus.PENDING)
    
    # Completion
    completed_at = Column(DateTime(timezone=True))
    verification_id = Column(Integer, ForeignKey("verifications.id"))
    completion_notes = Column(Text)
    completion_photos = Column(Text)  # JSON string of photo URLs
    
    # Metrics
    cost_usd = Column(Float)
    labor_hours = Column(Float)
    equipment_hours = Column(Float)
    
    # Relationships
    incident = relationship("Incident", back_populates="work_orders")
    zone = relationship("Zone", back_populates="work_orders")
    assigned_to_user = relationship("User", back_populates="work_orders", foreign_keys=[assigned_to])
    
    # Audit
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))
    verified_by = Column(Integer, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
