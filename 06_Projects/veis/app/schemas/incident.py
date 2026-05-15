from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class IncidentStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_VERIFIED = "completed_verified"
    CLOSED = "closed"


class IncidentCreate(BaseModel):
    """Schema for creating an incident"""
    zone_id: int
    observation_id: Optional[int] = None
    description: str
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    waste_type: Optional[str] = None
    estimated_mass_g: Optional[float] = Field(None, ge=0)


class IncidentResponse(BaseModel):
    """Schema for incident response"""
    id: int
    zone_id: int
    observation_id: Optional[int]
    description: str
    priority: str
    waste_type: Optional[str]
    estimated_mass_g: Optional[float]
    status: IncidentStatus
    nyc_311_complaint_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    closed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
