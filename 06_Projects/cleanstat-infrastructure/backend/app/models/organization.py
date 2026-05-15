"""
CleanStat Infrastructure - Organization Model
Multi-tenant organization support
"""
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.models.base import Base
import uuid

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    is_active = Column(Boolean, default=True)
