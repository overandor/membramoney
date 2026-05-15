from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class VCUStatus(str, Enum):
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    REDEEMED = "redeemed"
    EXPIRED = "expired"


class VCUTransfer(BaseModel):
    """Schema for transferring a VCU"""
    new_owner: str


class VCUResponse(BaseModel):
    """Schema for VCU response"""
    id: int
    verification_id: int
    token_id: str
    amount: float
    current_owner: str
    original_owner: str
    status: VCUStatus
    transfer_history: Optional[str]
    metadata: Optional[dict]
    created_at: datetime
    transferred_at: Optional[datetime]
    expires_at: Optional[datetime]
    
    class Config:
        from_attributes = True
