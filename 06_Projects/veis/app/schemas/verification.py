from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FRAUD_DETECTED = "fraud_detected"


class VerificationCreate(BaseModel):
    """Schema for creating a verification"""
    observation_id: int
    followup_image_url: str


class VerificationResponse(BaseModel):
    """Schema for verification response"""
    id: int
    observation_id: int
    followup_image_url: str
    removed_mass_g: float
    fraud_risk_score: float
    similarity_score: Optional[float]
    status: VerificationStatus
    verification_details: Optional[dict]
    created_at: datetime
    verified_at: Optional[datetime]
    
    class Config:
        from_attributes = True
