from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ZoneCreate(BaseModel):
    """Schema for creating a zone"""
    name: str
    zone_code: str = Field(..., min_length=2, max_length=10)
    boundary_polygon: Optional[str] = None
    center_latitude: Optional[float] = Field(None, ge=-90, le=90)
    center_longitude: Optional[float] = Field(None, ge=-180, le=180)
    description: Optional[str] = None
    area_sq_km: Optional[float] = Field(None, ge=0)
    population: Optional[int] = Field(None, ge=0)
    priority_level: str = Field(default="medium", pattern="^(low|medium|high)$")


class ZoneResponse(BaseModel):
    """Schema for zone response"""
    id: int
    name: str
    zone_code: str
    boundary_polygon: Optional[str]
    center_latitude: Optional[float]
    center_longitude: Optional[float]
    description: Optional[str]
    area_sq_km: Optional[float]
    population: Optional[int]
    active_work_orders: int
    priority_level: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
