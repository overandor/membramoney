from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Zone(Base):
    """Geographic zone model for city operations"""
    
    __tablename__ = "zones"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    zone_code = Column(String, unique=True, nullable=False)
    
    # Geographic boundaries
    boundary_polygon = Column(Text)  # GeoJSON string
    center_latitude = Column(Float)
    center_longitude = Column(Float)
    
    # Zone details
    description = Column(Text)
    area_sq_km = Column(Float)
    population = Column(Integer)
    
    # Operations
    active_work_orders = Column(Integer, default=0)
    priority_level = Column(String, default="medium")
    
    # Relationships
    incidents = relationship("Incident", back_populates="zone")
    work_orders = relationship("WorkOrder", back_populates="zone")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
