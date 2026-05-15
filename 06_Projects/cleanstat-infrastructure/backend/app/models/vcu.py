"""
CleanStat Infrastructure - VCU Model
Verified Cleanup Unit - Tokenized environmental credit
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class VCUStatus(str, enum.Enum):
    """VCU status"""
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class VCU(Base):
    """Verified Cleanup Unit (VCU) - Tokenized environmental credit"""
    
    __tablename__ = "vcus"
    
    id = Column(Integer, primary_key=True, index=True)
    verification_id = Column(Integer, ForeignKey("verifications.id"), nullable=False, unique=True)
    
    # Token information
    token_id = Column(String(64), unique=True, nullable=False, index=True)  # Blockchain token ID
    token_standard = Column(String(20), default="ERC-1155")
    contract_address = Column(String(42))
    
    # Environmental value
    amount = Column(Float, nullable=False)  # Amount in kg CO2 equivalent
    baseline_mass_g = Column(Float)
    verified_mass_g = Column(Float)
    co2_equivalent_kg = Column(Float)
    
    # Ownership
    current_owner = Column(String(42), nullable=False, index=True)
    original_owner = Column(String(42), nullable=False)
    
    # Status
    status = Column(SQLEnum(VCUStatus), default=VCUStatus.ACTIVE)
    
    # Transfer history
    transfer_count = Column(Integer, default=0)
    transfer_history = Column(Text)  # JSON string of transfer history
    last_transferred_at = Column(DateTime(timezone=True))
    
    # Metadata
    metadata = Column(Text)  # JSON string for additional metadata
    ipfs_metadata_cid = Column(String(64))
    
    # Expiration
    expires_at = Column(DateTime(timezone=True))
    is_expired = Column(Boolean, default=False)
    
    # Pricing
    mint_price_usd = Column(Float)
    current_price_usd = Column(Float)
    price_history = Column(Text)  # JSON string of price history
    
    # Relationships
    verification = relationship("Verification", back_populates="vcu")
    
    # Audit
    minted_by = Column(Integer, ForeignKey("users.id"))
    minted_transaction_hash = Column(String(66))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    minted_at = Column(DateTime(timezone=True), server_default=func.now())
    transferred_at = Column(DateTime(timezone=True))
    redeemed_at = Column(DateTime(timezone=True))
    expired_at = Column(DateTime(timezone=True))
