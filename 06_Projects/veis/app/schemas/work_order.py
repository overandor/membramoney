from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class WorkOrderStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"


class WorkOrderCreate(BaseModel):
    """Schema for creating a work order"""
    incident_id: int
    zone_id: int
    assigned_to: str
    description: str
    estimated_duration_hours: Optional[float] = Field(None, ge=0)


class WorkOrderResponse(BaseModel):
    """Schema for work order response"""
    id: int
    incident_id: int
    zone_id: int
    assigned_to: str
    assigned_at: Optional[datetime]
    description: str
    estimated_duration_hours: Optional[float]
    actual_duration_hours: Optional[float]
    status: WorkOrderStatus
    completed_at: Optional[datetime]
    verification_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
