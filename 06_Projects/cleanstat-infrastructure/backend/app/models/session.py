"""
CleanStat Infrastructure - Session Model
JWT session management with refresh tokens
"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.models.base import Base

class Session(Base):
    __tablename__ = "sessions"
    
    jti = Column(String(36), primary_key=True)  # JWT ID
    wallet_address = Column(String(42), ForeignKey("users.wallet_address"), nullable=False)
    refresh_token = Column(String(255))
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    revoked = Column(Boolean, default=False)
    ip_address = Column(String(45))
    user_agent = Column(String(255))
