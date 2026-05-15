"""
CleanStat Infrastructure - Audit Log Model
Comprehensive audit logging for compliance
"""
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func
from app.models.base import Base
import uuid

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False)  # auth.success, auth.failure, observation.created, etc.
    wallet_address = Column(String(42), index=True)
    organization_id = Column(String(36), index=True)
    ip_address = Column(String(45))
    user_agent = Column(String(255))
    details = Column(JSON)
    created_at = Column(DateTime, server_default=func.now(), index=True)
