from enum import StrEnum

class VisitStatus(StrEnum):
    requested = "requested"
    identity_verified = "identity_verified"
    risk_preapproved = "risk_preapproved"
    risk_denied = "risk_denied"
    insurance_quoted = "insurance_quoted"
    payment_authorized = "payment_authorized"
    coverage_bound = "coverage_bound"
    access_issued = "access_issued"
    checked_in = "checked_in"
    checked_out = "checked_out"
    completed = "completed"
    cancelled = "cancelled"
    incident_reported = "incident_reported"
    disputed = "disputed"

class PaymentStatus(StrEnum):
    intent_created = "intent_created"
    authorized = "authorized"
    captured = "captured"
    refunded = "refunded"
    cancelled = "cancelled"
    failed = "failed"

class CoverageStatus(StrEnum):
    quote_requested = "quote_requested"
    quoted = "quoted"
    payment_authorized = "payment_authorized"
    bind_requested = "bind_requested"
    active = "active"
    expired = "expired"
    cancelled = "cancelled"
    denied = "denied"
    failed = "failed"
    claimable = "claimable"

class AssetCategory(StrEnum):
    restroom = "restroom"
    luggage_drop = "luggage_drop"
    parking = "parking"
    ev_charger = "ev_charger"
    storage_locker = "storage_locker"
    coworking_desk = "coworking_desk"
    laundry = "laundry"
    printer = "printer"
    shower = "shower"

class IdentityLevel(StrEnum):
    unverified = "unverified"
    email_verified = "email_verified"
    id_verified = "id_verified"
    biometric_verified = "biometric_verified"

class UserType(StrEnum):
    guest = "guest"
    host = "host"
    admin = "admin"

class AdCampaignStatus(StrEnum):
    draft = "draft"
    creative_submitted = "creative_submitted"
    creative_approved = "creative_approved"
    funded = "funded"
    launched = "launched"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"

class AdPlacementStatus(StrEnum):
    pending = "pending"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    proof_rejected = "proof_rejected"

class AdPayoutStatus(StrEnum):
    pending = "pending"
    eligible = "eligible"
    released = "released"
    failed = "failed"

class TokenSaleStatus(StrEnum):
    draft = "draft"
    active = "active"
    paused = "paused"
    finalized = "finalized"
    cancelled = "cancelled"
    liquidity_migrated = "liquidity_migrated"

class ContributionStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    failed = "failed"
    refunded = "refunded"

class RebateClaimStatus(StrEnum):
    pending = "pending"
    eligible = "eligible"
    claimed = "claimed"
    expired = "expired"
    denied = "denied"

class TokenCurrency(StrEnum):
    SOL = "SOL"
    USDC = "USDC"
