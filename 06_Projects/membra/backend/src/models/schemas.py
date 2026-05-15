from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from src.models.enums import (
    VisitStatus,
    PaymentStatus,
    CoverageStatus,
    AssetCategory,
    IdentityLevel,
    UserType,
)

# ─── Identity ───────────────────────────────────────────────
class UserCreate(BaseModel):
    email: str
    name: str
    phone: Optional[str] = None
    user_type: UserType

class UserOut(BaseModel):
    user_id: str
    email: str
    name: str
    phone: Optional[str]
    user_type: UserType
    identity_level: IdentityLevel
    trust_score: float = Field(ge=0.0, le=1.0)
    blocked: bool = False
    created_at: datetime

class IdentityVerify(BaseModel):
    user_id: str
    document_type: str = "passport"

class IdentityVerifyOut(BaseModel):
    user_id: str
    identity_level: IdentityLevel
    verified_at: datetime

# ─── Assets ─────────────────────────────────────────────────
class AssetCreate(BaseModel):
    host_id: str
    title: str
    description: str
    category: AssetCategory
    address: str
    latitude: float
    longitude: float
    price_cents: int = Field(gt=0)
    deposit_cents: int = 0
    rules: Optional[str] = None
    hours_open: Optional[str] = None
    max_guests: int = 1
    insurable: bool = True

class AssetOut(BaseModel):
    asset_id: str
    host_id: str
    title: str
    description: str
    category: AssetCategory
    address: str
    latitude: float
    longitude: float
    price_cents: int
    deposit_cents: int
    rules: Optional[str]
    hours_open: Optional[str]
    max_guests: int
    insurable: bool
    verified: bool = False
    active: bool = True
    created_at: datetime

class NearbyQuery(BaseModel):
    lat: float
    lng: float
    radius_miles: float = 5.0
    category: Optional[AssetCategory] = None

# ─── Reservations / Visits ──────────────────────────────────
class ReservationCreate(BaseModel):
    asset_id: str
    guest_id: str
    start_time: datetime
    end_time: datetime
    guest_count: int = 1

class ReservationOut(BaseModel):
    visit_id: str
    asset_id: str
    guest_id: str
    host_id: str
    start_time: datetime
    end_time: datetime
    guest_count: int
    status: VisitStatus
    qr_token: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class RiskDecision(BaseModel):
    visit_id: str
    approved: bool
    reason: Optional[str] = None
    risk_score: float = Field(ge=0.0, le=1.0)

# ─── Insurance ──────────────────────────────────────────────
class InsuranceQuoteRequest(BaseModel):
    visit_id: str
    asset_category: AssetCategory
    coverage_limit_cents: int

class InsuranceQuoteOut(BaseModel):
    quote_id: str
    external_quote_id: str
    visit_id: str
    premium_cents: int
    currency: str = "USD"
    quote_expires_at: datetime
    coverage_limit_cents: int
    deductible_cents: int
    covered_events: list[str]
    terms_url: str

class InsuranceBindRequest(BaseModel):
    visit_id: str
    quote_id: str

class CoverageOut(BaseModel):
    coverage_id: str
    visit_id: str
    external_policy_id: Optional[str]
    status: CoverageStatus
    premium_cents: int
    coverage_limit_cents: int
    deductible_cents: int
    coverage_start: datetime
    coverage_end: datetime
    certificate_url: Optional[str]
    covered_events: list[str]
    created_at: datetime

# ─── Payments ─────────────────────────────────────────────
class PaymentQuote(BaseModel):
    visit_id: str
    subtotal_cents: int
    insurance_premium_cents: int
    platform_fee_cents: int
    deposit_cents: int
    total_cents: int

class PaymentAuthorize(BaseModel):
    visit_id: str
    provider: str = "stripe"
    provider_payment_method_id: str

class PaymentOut(BaseModel):
    payment_id: str
    visit_id: str
    guest_id: str
    host_id: str
    provider: str
    provider_payment_intent_id: Optional[str]
    status: PaymentStatus
    subtotal_cents: int
    insurance_premium_cents: int
    platform_fee_cents: int
    deposit_cents: int
    total_authorized_cents: int
    total_captured_cents: int = 0
    currency: str = "USD"
    created_at: datetime
    updated_at: datetime

class PayoutRelease(BaseModel):
    payment_id: str

# ─── Access ───────────────────────────────────────────────
class QRVerify(BaseModel):
    qr_payload: str

class QRVerifyOut(BaseModel):
    valid: bool
    visit_id: Optional[str] = None
    asset_id: Optional[str] = None
    guest_id: Optional[str] = None
    status: Optional[str] = None
    message: str

class CheckInOut(BaseModel):
    visit_id: str

class CheckInOutResult(BaseModel):
    visit_id: str
    status: VisitStatus
    timestamp: datetime

# ─── Incidents / Claims ───────────────────────────────────
class IncidentCreate(BaseModel):
    visit_id: str
    reporter_id: str
    description: str
    severity: str = "low"

class IncidentOut(BaseModel):
    incident_id: str
    visit_id: str
    reporter_id: str
    description: str
    severity: str
    status: str
    created_at: datetime

class ClaimCreate(BaseModel):
    incident_id: str
    coverage_id: str
    description: str
    damage_cents: int

class ClaimOut(BaseModel):
    claim_id: str
    incident_id: str
    coverage_id: str
    external_claim_id: Optional[str]
    description: str
    damage_cents: int
    status: str
    created_at: datetime

class DisputeCreate(BaseModel):
    visit_id: str
    reason: str
    requested_refund_cents: int

class DisputeOut(BaseModel):
    dispute_id: str
    visit_id: str
    reason: str
    requested_refund_cents: int
    status: str
    created_at: datetime

# ─── Ads ──────────────────────────────────────────────────────
class AdCampaignCreate(BaseModel):
    advertiser_id: str
    title: str
    description: Optional[str] = None
    target_city: Optional[str] = None
    target_neighborhoods: list[str] = []
    asset_types: list[str] = []
    budget_cents: int
    daily_budget_cents: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    destination_url: Optional[str] = None
    payout_rules: Optional[dict] = None

class AdCampaignOut(BaseModel):
    campaign_id: str
    advertiser_id: str
    title: str
    description: Optional[str]
    target_city: Optional[str]
    target_neighborhoods: list[str]
    asset_types: list[str]
    budget_cents: int
    daily_budget_cents: Optional[int]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    status: str
    creative_url: Optional[str]
    approved_creative_url: Optional[str]
    destination_url: Optional[str]
    payout_rules: Optional[dict]
    created_at: datetime
    updated_at: datetime

class AdPlacementCreate(BaseModel):
    campaign_id: str
    asset_id: str
    owner_id: str
    daily_rate_cents: int

class AdPlacementOut(BaseModel):
    placement_id: str
    campaign_id: str
    asset_id: str
    owner_id: str
    daily_rate_cents: int
    status: str
    created_at: datetime

class AdCreativeSubmit(BaseModel):
    campaign_id: Optional[str] = None
    asset_type: str
    mockup_url: str
    print_ready_url: str

class AdCreativeOut(BaseModel):
    creative_id: str
    campaign_id: str
    asset_type: Optional[str]
    mockup_url: Optional[str]
    print_ready_url: Optional[str]
    status: str
    reviewer_notes: Optional[str]
    created_at: datetime

class AdProofSubmit(BaseModel):
    placement_id: str
    proof_type: str
    photo_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class AdProofOut(BaseModel):
    proof_id: str
    placement_id: str
    campaign_id: str
    owner_id: str
    proof_type: str
    photo_url: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    verified: bool
    reviewer_notes: Optional[str]
    created_at: datetime

class AdPayoutOut(BaseModel):
    payout_id: str
    owner_id: str
    placement_id: str
    campaign_id: str
    amount_cents: int
    status: str
    proof_verified: bool
    created_at: datetime
    released_at: Optional[datetime]

class QRTagOut(BaseModel):
    qr_id: str
    placement_id: Optional[str]
    campaign_id: Optional[str]
    tracking_url: Optional[str]
    redirect_url: Optional[str]
    scan_count: int
    is_active: bool
    created_at: datetime

# ─── Wear ─────────────────────────────────────────────────────
class WearerCreate(BaseModel):
    user_id: str
    email: str
    name: str
    phone: Optional[str] = None
    body_size: Optional[str] = None
    clothing_prefs: Optional[str] = None
    preferred_garments: list[str] = []
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    daily_rate_cents: int = 1500

class WearerOut(BaseModel):
    wearer_id: str
    user_id: str
    email: str
    name: str
    phone: Optional[str]
    identity_verified: bool
    body_size: Optional[str]
    clothing_prefs: Optional[str]
    preferred_garments: list[str]
    city: Optional[str]
    neighborhood: Optional[str]
    daily_rate_cents: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

class WearableAssetCreate(BaseModel):
    wearer_id: str
    garment_type: str
    size: Optional[str] = None
    color: Optional[str] = None
    brand: Optional[str] = None
    serial_id: Optional[str] = None

class WearableAssetOut(BaseModel):
    wearable_id: str
    wearer_id: str
    garment_type: str
    size: Optional[str]
    color: Optional[str]
    brand: Optional[str]
    serial_id: Optional[str]
    qr_id: Optional[str]
    nfc_id: Optional[str]
    campaign_id: Optional[str]
    status: str
    created_at: datetime

class WearProofSubmit(BaseModel):
    placement_id: str
    selfie_url: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class WearProofOut(BaseModel):
    wear_proof_id: str
    placement_id: str
    campaign_id: str
    wearer_id: str
    selfie_url: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    verified: bool
    reviewer_notes: Optional[str]
    created_at: datetime

# ─── OrchestrationOS ────────────────────────────────────────
class ObjectiveCreate(BaseModel):
    owner_id: str
    title: str
    description: Optional[str] = None
    priority: str = "medium"

class ObjectiveOut(BaseModel):
    objective_id: str
    owner_id: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime

class TaskCreate(BaseModel):
    objective_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    assignee_type: str = "unassigned"
    assignee_id: Optional[str] = None
    priority: str = "medium"
    deadline: Optional[datetime] = None
    proof_requirement: Optional[str] = None
    depends_on: Optional[str] = None

class TaskOut(BaseModel):
    task_id: str
    objective_id: Optional[str]
    title: str
    description: Optional[str]
    assignee_type: str
    assignee_id: Optional[str]
    status: str
    priority: str
    deadline: Optional[datetime]
    proof_requirement: Optional[str]
    depends_on: Optional[str]
    created_at: datetime
    updated_at: datetime

# ─── AgentOS ──────────────────────────────────────────────
class AgentCreate(BaseModel):
    name: str
    role: str
    description: Optional[str] = None
    tools: Optional[list[str]] = None
    permissions: Optional[list[str]] = None
    blocked_actions: Optional[list[str]] = None
    output_schema: Optional[dict] = None

class AgentOut(BaseModel):
    agent_id: str
    name: str
    role: str
    description: Optional[str]
    tools: Optional[list[str]]
    permissions: Optional[list[str]]
    blocked_actions: Optional[list[str]]
    output_schema: Optional[dict]
    status: str
    created_at: datetime

# ─── JobOS ────────────────────────────────────────────────
class JobCreate(BaseModel):
    task_id: Optional[str] = None
    job_type: str
    title: str
    description: Optional[str] = None
    reward_cents: int = 0
    currency: str = "USD"
    proof_required: bool = True

class JobOut(BaseModel):
    job_id: str
    task_id: Optional[str]
    job_type: str
    title: str
    description: Optional[str]
    reward_cents: int
    currency: str
    status: str
    assignee_id: Optional[str]
    proof_required: bool
    created_at: datetime
    updated_at: datetime

# ─── CompanyOS ────────────────────────────────────────────
class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    kpi_targets: Optional[dict] = None

class DepartmentOut(BaseModel):
    department_id: str
    name: str
    description: Optional[str]
    parent_id: Optional[str]
    kpi_targets: Optional[dict]
    status: str
    created_at: datetime

class SOPCreate(BaseModel):
    department_id: str
    title: str
    steps: list[str]
    trigger_events: Optional[list[str]] = None

class SOPOut(BaseModel):
    sop_id: str
    department_id: str
    title: str
    steps: list[str]
    trigger_events: Optional[list[str]]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

class OperatingUnitCreate(BaseModel):
    name: str
    department_id: str
    unit_type: str
    territory: Optional[str] = None
    kpi_snapshot: Optional[dict] = None

class OperatingUnitOut(BaseModel):
    unit_id: str
    name: str
    department_id: str
    unit_type: str
    territory: Optional[str]
    kpi_snapshot: Optional[dict]
    status: str
    created_at: datetime

# ─── GovernanceOS ─────────────────────────────────────────
class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rules: dict

class PolicyOut(BaseModel):
    policy_id: str
    name: str
    description: Optional[str]
    rules: dict
    version: int
    status: str
    created_at: datetime
    updated_at: datetime

class ApprovalCreate(BaseModel):
    request_type: str
    request_id: str
    requester_id: str
    risk_score: Optional[float] = None
    reason: Optional[str] = None

class ApprovalOut(BaseModel):
    approval_id: str
    request_type: str
    request_id: str
    requester_id: str
    approver_id: Optional[str]
    status: str
    risk_score: Optional[float]
    reason: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]

class AuditEventOut(BaseModel):
    event_id: str
    event_type: str
    actor_id: str
    target_type: str
    target_id: str
    details: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

# ─── ProofBook ────────────────────────────────────────────
class ProofRecordCreate(BaseModel):
    record_type: str
    record_id: str
    raw_data: Optional[dict] = None
    signatures: Optional[list[str]] = None

class ProofRecordOut(BaseModel):
    proof_id: str
    record_type: str
    record_id: str
    hash: str
    raw_data: Optional[dict]
    signatures: Optional[list[str]]
    verified: bool
    created_at: datetime

# ─── SettlementOS ───────────────────────────────────────
class SettlementEligibilityCreate(BaseModel):
    party_id: str
    party_type: str
    job_id: Optional[str] = None
    amount_cents: int
    currency: str = "USD"
    proof_id: Optional[str] = None
    settlement_rail: Optional[str] = None

class SettlementEligibilityOut(BaseModel):
    eligibility_id: str
    party_id: str
    party_type: str
    job_id: Optional[str]
    amount_cents: int
    currency: str
    status: str
    proof_id: Optional[str]
    settlement_rail: Optional[str]
    settlement_ref: Optional[str]
    created_at: datetime
    updated_at: datetime

# ─── WorldBridge ──────────────────────────────────────────
class WorldAssetCreate(BaseModel):
    owner_id: str
    asset_type: str
    title: str
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capabilities: Optional[list[str]] = None
    availability_schedule: Optional[dict] = None
    media_urls: Optional[list[str]] = None

class WorldAssetOut(BaseModel):
    world_asset_id: str
    owner_id: str
    asset_type: str
    title: str
    description: Optional[str]
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    capabilities: Optional[list[str]]
    availability_schedule: Optional[dict]
    media_urls: Optional[list[str]]
    status: str
    created_at: datetime

# ─── LLM Concierge / IntentOS ─────────────────────────────
class IntentRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    context: Optional[dict] = None

class IntentOut(BaseModel):
    intent_id: str
    user_id: Optional[str]
    original_message: str
    parsed_objective: str
    suggested_actions: list[dict]
    created_at: datetime
