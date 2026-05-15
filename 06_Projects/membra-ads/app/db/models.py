import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, ForeignKey,
    Numeric, JSON, Enum, create_engine, event
)
from sqlalchemy.orm import declarative_base, relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()

def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"

class CampaignStatus(PyEnum):
    draft = "draft"
    creative_submitted = "creative_submitted"
    creative_approved = "creative_approved"
    funded = "funded"
    launched = "launched"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"

class ProofType(PyEnum):
    photo = "photo"
    location = "location"
    qr_scan = "qr_scan"
    nfc_tap = "nfc_tap"
    review = "review"

class PaymentStatus(PyEnum):
    pending = "pending"
    authorized = "authorized"
    captured = "captured"
    failed = "failed"
    refunded = "refunded"

class PayoutStatus(PyEnum):
    pending = "pending"
    eligible = "eligible"
    released = "released"
    failed = "failed"

class KitStatus(PyEnum):
    pending = "pending"
    ordered = "ordered"
    shipped = "shipped"
    received = "received"
    installed = "installed"
    rejected = "rejected"

class Owner(Base):
    __tablename__ = "owners"
    owner_id = Column(String(32), primary_key=True, default=lambda: gen_id("own"))
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(50))
    stripe_connect_account_id = Column(String(255))
    identity_verified = Column(Boolean, default=False)
    city = Column(String(100))
    neighborhood = Column(String(100))
    payout_method = Column(String(50), default="stripe_transfer")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    assets = relationship("AdAsset", back_populates="owner")
    payouts = relationship("Payout", back_populates="owner")

class Advertiser(Base):
    __tablename__ = "advertisers"
    advertiser_id = Column(String(32), primary_key=True, default=lambda: gen_id("adv"))
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    company = Column(String(255))
    stripe_customer_id = Column(String(255))
    billing_address = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    campaigns = relationship("Campaign", back_populates="advertiser")

class AdAsset(Base):
    __tablename__ = "ad_assets"
    asset_id = Column(String(32), primary_key=True, default=lambda: gen_id("ast"))
    owner_id = Column(String(32), ForeignKey("owners.owner_id"), nullable=False)
    asset_type = Column(String(50), nullable=False)  # window, vehicle, wearable
    title = Column(String(255))
    description = Column(Text)
    address = Column(Text)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    city = Column(String(100))
    neighborhood = Column(String(100))
    daily_rate_cents = Column(Integer, default=500)
    photos = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    owner = relationship("Owner", back_populates="assets")
    placements = relationship("AcceptedPlacement", back_populates="asset")

class WindowAsset(Base):
    __tablename__ = "window_assets"
    window_id = Column(String(32), primary_key=True, default=lambda: gen_id("win"))
    asset_id = Column(String(32), ForeignKey("ad_assets.asset_id"))
    dimensions = Column(String(50))
    facing = Column(String(50))
    foot_traffic_estimate = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

class VehicleAsset(Base):
    __tablename__ = "vehicle_assets"
    vehicle_id = Column(String(32), primary_key=True, default=lambda: gen_id("veh"))
    asset_id = Column(String(32), ForeignKey("ad_assets.asset_id"))
    vehicle_type = Column(String(50))
    make_model = Column(String(100))
    color = Column(String(50))
    daily_miles_estimate = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

class WearableAsset(Base):
    __tablename__ = "wearable_assets"
    wearable_id = Column(String(32), primary_key=True, default=lambda: gen_id("wear"))
    asset_id = Column(String(32), ForeignKey("ad_assets.asset_id"))
    garment_type = Column(String(50))
    size = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())

class Campaign(Base):
    __tablename__ = "campaigns"
    campaign_id = Column(String(32), primary_key=True, default=lambda: gen_id("cmp"))
    advertiser_id = Column(String(32), ForeignKey("advertisers.advertiser_id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    target_city = Column(String(100))
    target_neighborhoods = Column(JSON, default=list)
    asset_types = Column(JSON, default=list)  # ["window", "vehicle", "wearable"]
    budget_cents = Column(Integer, nullable=False)
    daily_budget_cents = Column(Integer)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(String(50), default=CampaignStatus.draft.value)
    creative_url = Column(String(500))
    approved_creative_url = Column(String(500))
    destination_url = Column(String(500))
    payout_rules = Column(JSON, default=dict)  # {"window": 500, "vehicle": 300, "wearable": 500}
    proof_rules = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    advertiser = relationship("Advertiser", back_populates="campaigns")
    media_kits = relationship("MediaKit", back_populates="campaign")
    accepted_placements = relationship("AcceptedPlacement", back_populates="campaign")

class CampaignCreative(Base):
    __tablename__ = "campaign_creatives"
    creative_id = Column(String(32), primary_key=True, default=lambda: gen_id("crt"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    asset_type = Column(String(50))
    mockup_url = Column(String(500))
    print_ready_url = Column(String(500))
    status = Column(String(50), default="pending")  # pending, approved, rejected
    reviewer_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class AcceptedPlacement(Base):
    __tablename__ = "accepted_placements"
    placement_id = Column(String(32), primary_key=True, default=lambda: gen_id("plc"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    asset_id = Column(String(32), ForeignKey("ad_assets.asset_id"))
    owner_id = Column(String(32), ForeignKey("owners.owner_id"))
    daily_rate_cents = Column(Integer)
    status = Column(String(50), default="pending")  # pending, active, completed, cancelled
    created_at = Column(DateTime, server_default=func.now())

    campaign = relationship("Campaign", back_populates="accepted_placements")
    asset = relationship("AdAsset", back_populates="placements")

class MediaKit(Base):
    __tablename__ = "media_kits"
    kit_id = Column(String(32), primary_key=True, default=lambda: gen_id("kit"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    placement_id = Column(String(32), ForeignKey("accepted_placements.placement_id"))
    asset_type = Column(String(50))
    status = Column(String(50), default=KitStatus.pending.value)
    qr_tag_id = Column(String(32))
    nfc_tag_id = Column(String(32))
    tracking_url = Column(String(500))
    vendor = Column(String(50))
    vendor_order_id = Column(String(100))
    shipping_tracking = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    campaign = relationship("Campaign", back_populates="media_kits")

class QRTag(Base):
    __tablename__ = "qr_tags"
    qr_id = Column(String(32), primary_key=True, default=lambda: gen_id("qr"))
    kit_id = Column(String(32), ForeignKey("media_kits.kit_id"))
    tracking_url = Column(String(500))
    redirect_url = Column(String(500))
    scan_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class NFCTag(Base):
    __tablename__ = "nfc_tags"
    nfc_id = Column(String(32), primary_key=True, default=lambda: gen_id("nfc"))
    kit_id = Column(String(32), ForeignKey("media_kits.kit_id"))
    uid = Column(String(100), unique=True)
    tracking_url = Column(String(500))
    redirect_url = Column(String(500))
    tap_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class ProofEvent(Base):
    __tablename__ = "proof_events"
    proof_id = Column(String(32), primary_key=True, default=lambda: gen_id("prf"))
    placement_id = Column(String(32), ForeignKey("accepted_placements.placement_id"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    owner_id = Column(String(32), ForeignKey("owners.owner_id"))
    proof_type = Column(String(50), nullable=False)
    photo_url = Column(String(500))
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    verified = Column(Boolean, default=False)
    reviewer_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class ScanEvent(Base):
    __tablename__ = "scan_events"
    scan_id = Column(String(32), primary_key=True, default=lambda: gen_id("scn"))
    qr_id = Column(String(32), ForeignKey("qr_tags.qr_id"))
    nfc_id = Column(String(32), ForeignKey("nfc_tags.nfc_id"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    placement_id = Column(String(32), ForeignKey("accepted_placements.placement_id"))
    ip_address = Column(String(100))
    user_agent = Column(Text)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    created_at = Column(DateTime, server_default=func.now())

class Payment(Base):
    __tablename__ = "payments"
    payment_id = Column(String(32), primary_key=True, default=lambda: gen_id("pay"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    advertiser_id = Column(String(32), ForeignKey("advertisers.advertiser_id"))
    stripe_payment_intent_id = Column(String(100))
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(50), default=PaymentStatus.pending.value)
    payment_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())

class Payout(Base):
    __tablename__ = "payouts"
    payout_id = Column(String(32), primary_key=True, default=lambda: gen_id("pout"))
    owner_id = Column(String(32), ForeignKey("owners.owner_id"))
    placement_id = Column(String(32), ForeignKey("accepted_placements.placement_id"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    amount_cents = Column(Integer, nullable=False)
    stripe_transfer_id = Column(String(100))
    status = Column(String(50), default=PayoutStatus.pending.value)
    proof_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    released_at = Column(DateTime)

    owner = relationship("Owner", back_populates="payouts")

class Claim(Base):
    __tablename__ = "claims"
    claim_id = Column(String(32), primary_key=True, default=lambda: gen_id("clm"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    placement_id = Column(String(32), ForeignKey("accepted_placements.placement_id"))
    owner_id = Column(String(32), ForeignKey("owners.owner_id"))
    advertiser_id = Column(String(32), ForeignKey("advertisers.advertiser_id"))
    claim_type = Column(String(50))  # damage, missing, fraud, quality
    description = Column(Text)
    status = Column(String(50), default="open")  # open, reviewing, resolved, rejected
    resolution = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class TapEvent(Base):
    __tablename__ = "tap_events"
    tap_id = Column(String(32), primary_key=True, default=lambda: gen_id("tap"))
    nfc_id = Column(String(32), ForeignKey("nfc_tags.nfc_id"))
    campaign_id = Column(String(32), ForeignKey("campaigns.campaign_id"))
    placement_id = Column(String(32), ForeignKey("accepted_placements.placement_id"))
    ip_address = Column(String(100))
    user_agent = Column(Text)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    created_at = Column(DateTime, server_default=func.now())

class AuditEvent(Base):
    __tablename__ = "audit_events"
    audit_id = Column(String(32), primary_key=True, default=lambda: gen_id("aud"))
    entity_type = Column(String(50))
    entity_id = Column(String(32))
    action = Column(String(50))
    actor_id = Column(String(32))
    details = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
