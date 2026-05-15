"""
CleanStat Infrastructure - Zone Model
Geographic operational zone for city management
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Zone(Base):
    """Geographic zone model for city operations"""
    
    __tablename__ = "zones"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Zone identification
    name = Column(String(255), nullable=False)
    zone_code = Column(String(20), unique=True, nullable=False, index=True)
    zone_type = Column(String(50))  # residential, commercial, industrial, mixed
    
    # Geographic boundaries
    boundary_polygon = Column(Text)  # GeoJSON string
    center_latitude = Column(Float)
    center_longitude = Column(Float)
    area_sq_km = Column(Float)
    perimeter_km = Column(Float)
    
    # Population and demographics
    population = Column(Integer)
    households = Column(Integer)
    business_count = Column(Integer)
    
    # Zone details
    description = Column(Text)
    district = Column(String(100))
    borough = Column(String(100))
    
    # Operations
    active_work_orders = Column(Integer, default=0)
    pending_incidents = Column(Integer, default=0)
    priority_level = Column(String(20), default="medium")  # low, medium, high
    
    # Performance metrics
    avg_response_time_minutes = Column(Float)
    avg_resolution_time_hours = Column(Float)
    monthly_cleanups = Column(Integer, default=0)
    
    # Budget
    annual_budget_usd = Column(Float)
    monthly_budget_usd = Column(Float)
    
    # Relationships
    incidents = relationship("Incident", back_populates="zone")
    work_orders = relationship("WorkOrder", back_populates="zone")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
