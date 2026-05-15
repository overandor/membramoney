"""
CleanStat Infrastructure - User Model
Production-hardened user model with organization support
"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import enum

class UserRole(str, enum.Enum):
    """User roles for RBAC"""
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class User(Base):
    __tablename__ = "users"
    
    wallet_address = Column(String(42), primary_key=True)  # Ethereum address
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VIEWER)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)

    organization = relationship("Organization", backref="users")
