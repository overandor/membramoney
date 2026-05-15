import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional
from src.core.config import settings

DB_PATH = settings.database_url.replace("sqlite:///.", ".")

INIT_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    user_type TEXT NOT NULL,
    identity_level TEXT NOT NULL DEFAULT 'unverified',
    trust_score REAL NOT NULL DEFAULT 0.5,
    blocked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    host_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    price_cents INTEGER NOT NULL,
    deposit_cents INTEGER NOT NULL DEFAULT 0,
    rules TEXT,
    hours_open TEXT,
    max_guests INTEGER NOT NULL DEFAULT 1,
    insurable INTEGER NOT NULL DEFAULT 1,
    verified INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS visits (
    visit_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    guest_id TEXT NOT NULL,
    host_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    guest_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'requested',
    qr_token TEXT,
    risk_approved INTEGER,
    risk_reason TEXT,
    risk_score REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    visit_id TEXT NOT NULL UNIQUE,
    guest_id TEXT NOT NULL,
    host_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_payment_intent_id TEXT,
    status TEXT NOT NULL,
    subtotal_cents INTEGER NOT NULL,
    insurance_premium_cents INTEGER NOT NULL,
    platform_fee_cents INTEGER NOT NULL,
    deposit_cents INTEGER NOT NULL,
    total_authorized_cents INTEGER NOT NULL,
    total_captured_cents INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS coverages (
    coverage_id TEXT PRIMARY KEY,
    visit_id TEXT NOT NULL UNIQUE,
    external_policy_id TEXT,
    status TEXT NOT NULL,
    premium_cents INTEGER NOT NULL,
    coverage_limit_cents INTEGER NOT NULL,
    deductible_cents INTEGER NOT NULL,
    coverage_start TEXT NOT NULL,
    coverage_end TEXT NOT NULL,
    certificate_url TEXT,
    covered_events TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    visit_id TEXT NOT NULL,
    reporter_id TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'low',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    coverage_id TEXT NOT NULL,
    external_claim_id TEXT,
    description TEXT NOT NULL,
    damage_cents INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS disputes (
    dispute_id TEXT PRIMARY KEY,
    visit_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_refund_cents INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_host ON assets(host_id);
CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category);
CREATE INDEX IF NOT EXISTS idx_visits_guest ON visits(guest_id);
CREATE INDEX IF NOT EXISTS idx_visits_status ON visits(status);
CREATE INDEX IF NOT EXISTS idx_payments_visit ON payments(visit_id);
CREATE INDEX IF NOT EXISTS idx_coverages_visit ON coverages(visit_id);

CREATE TABLE IF NOT EXISTS ad_campaigns (
    campaign_id TEXT PRIMARY KEY,
    advertiser_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    target_city TEXT,
    target_neighborhoods TEXT,
    asset_types TEXT,
    budget_cents INTEGER NOT NULL,
    daily_budget_cents INTEGER,
    start_date TEXT,
    end_date TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    creative_url TEXT,
    approved_creative_url TEXT,
    destination_url TEXT,
    payout_rules TEXT,
    proof_rules TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ad_placements (
    placement_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    daily_rate_cents INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ad_creatives (
    creative_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    asset_type TEXT,
    mockup_url TEXT,
    print_ready_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewer_notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ad_proofs (
    proof_id TEXT PRIMARY KEY,
    placement_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    proof_type TEXT NOT NULL,
    photo_url TEXT,
    latitude REAL,
    longitude REAL,
    verified INTEGER NOT NULL DEFAULT 0,
    reviewer_notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ad_payouts (
    payout_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    placement_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    proof_verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    released_at TEXT
);

CREATE TABLE IF NOT EXISTS qr_tags (
    qr_id TEXT PRIMARY KEY,
    placement_id TEXT,
    campaign_id TEXT,
    tracking_url TEXT,
    redirect_url TEXT,
    scan_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ad_scan_events (
    scan_id TEXT PRIMARY KEY,
    qr_id TEXT,
    campaign_id TEXT,
    placement_id TEXT,
    ip_address TEXT,
    user_agent TEXT,
    latitude REAL,
    longitude REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ad_campaigns_advertiser ON ad_campaigns(advertiser_id);
CREATE INDEX IF NOT EXISTS idx_ad_placements_campaign ON ad_placements(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_placements_owner ON ad_placements(owner_id);
CREATE INDEX IF NOT EXISTS idx_ad_proofs_placement ON ad_proofs(placement_id);
CREATE INDEX IF NOT EXISTS idx_qr_tags_placement ON qr_tags(placement_id);

CREATE TABLE IF NOT EXISTS wearers (
    wearer_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    identity_verified INTEGER NOT NULL DEFAULT 0,
    body_size TEXT,
    clothing_prefs TEXT,
    preferred_garments TEXT,
    city TEXT,
    neighborhood TEXT,
    daily_rate_cents INTEGER DEFAULT 1500,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wearable_assets (
    wearable_id TEXT PRIMARY KEY,
    wearer_id TEXT NOT NULL,
    garment_type TEXT NOT NULL,
    size TEXT,
    color TEXT,
    brand TEXT,
    serial_id TEXT,
    qr_id TEXT,
    nfc_id TEXT,
    campaign_id TEXT,
    status TEXT NOT NULL DEFAULT 'available',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wear_proofs (
    wear_proof_id TEXT PRIMARY KEY,
    placement_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    wearer_id TEXT NOT NULL,
    selfie_url TEXT,
    latitude REAL,
    longitude REAL,
    verified INTEGER NOT NULL DEFAULT 0,
    reviewer_notes TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wearers_user ON wearers(user_id);
CREATE INDEX IF NOT EXISTS idx_wearable_wearer ON wearable_assets(wearer_id);
CREATE INDEX IF NOT EXISTS idx_wearable_campaign ON wearable_assets(campaign_id);
CREATE INDEX IF NOT EXISTS idx_wear_proofs_placement ON wear_proofs(placement_id);

-- ─── CompanyOS: Orchestration ─────────────────────────────
CREATE TABLE IF NOT EXISTS objectives (
    objective_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    priority TEXT NOT NULL DEFAULT 'medium',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    objective_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    assignee_type TEXT NOT NULL DEFAULT 'unassigned',
    assignee_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    priority TEXT NOT NULL DEFAULT 'medium',
    deadline TEXT,
    proof_requirement TEXT,
    depends_on TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ─── CompanyOS: Agents ────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    description TEXT,
    tools TEXT,
    permissions TEXT,
    blocked_actions TEXT,
    output_schema TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

-- ─── CompanyOS: Jobs ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    task_id TEXT,
    job_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    reward_cents INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'open',
    assignee_id TEXT,
    proof_required INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ─── CompanyOS: Company structure ─────────────────────────
CREATE TABLE IF NOT EXISTS departments (
    department_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    parent_id TEXT,
    kpi_targets TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sops (
    sop_id TEXT PRIMARY KEY,
    department_id TEXT NOT NULL,
    title TEXT NOT NULL,
    steps TEXT NOT NULL,
    trigger_events TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operating_units (
    unit_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department_id TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    territory TEXT,
    kpi_snapshot TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

-- ─── CompanyOS: Governance ────────────────────────────────
CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    rules TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    request_type TEXT NOT NULL,
    request_id TEXT NOT NULL,
    requester_id TEXT NOT NULL,
    approver_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    risk_score REAL,
    reason TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL
);

-- ─── CompanyOS: ProofBook ─────────────────────────────────
CREATE TABLE IF NOT EXISTS proof_records (
    proof_id TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    hash TEXT NOT NULL,
    raw_data TEXT,
    signatures TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- ─── CompanyOS: Settlement ──────────────────────────────
CREATE TABLE IF NOT EXISTS settlement_eligibility (
    eligibility_id TEXT PRIMARY KEY,
    party_id TEXT NOT NULL,
    party_type TEXT NOT NULL,
    job_id TEXT,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'pending',
    proof_id TEXT,
    settlement_rail TEXT,
    settlement_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ─── CompanyOS: WorldBridge extended assets ───────────────
CREATE TABLE IF NOT EXISTS world_assets (
    world_asset_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    address TEXT,
    latitude REAL,
    longitude REAL,
    capabilities TEXT,
    availability_schedule TEXT,
    media_urls TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_objective ON tasks(objective_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_jobs_task ON jobs(task_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_approvals_request ON approvals(request_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_audit_events_target ON audit_events(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_proof_records_record ON proof_records(record_type, record_id);
CREATE INDEX IF NOT EXISTS idx_settlement_party ON settlement_eligibility(party_id);
CREATE INDEX IF NOT EXISTS idx_world_assets_owner ON world_assets(owner_id);
CREATE INDEX IF NOT EXISTS idx_world_assets_type ON world_assets(asset_type);
"""

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db() -> None:
    conn = get_connection()
    conn.executescript(INIT_SQL)
    conn.commit()
    conn.close()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def generate_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"
