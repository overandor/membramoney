from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class ObservationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ObservationCreate(BaseModel):
    """Schema for creating an observation"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None
    waste_type: Optional[str] = None
    estimated_mass_g: Optional[float] = Field(None, ge=0)


class ObservationResponse(BaseModel):
    """Schema for observation response"""
    id: int
    image_url: str
    latitude: float
    longitude: float
    address: Optional[str]
    waste_type: Optional[str]
    estimated_mass_g: Optional[float]
    confidence_score: Optional[float]
    status: ObservationStatus
    detection_result: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
