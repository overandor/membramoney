#!/usr/bin/env python3
"""
MEMBRA CompanyOS Seed Script
Populates the database with demo data for all CompanyOS layers.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db.database import get_connection, now_iso, generate_id, init_db
from src.services.orchestration import create_objective, create_task
from src.services.agents import create_agent
from src.services.jobs import create_job
from src.services.company import create_department, create_sop, create_operating_unit
from src.services.governance import create_policy, create_approval
from src.services.proofbook import create_proof_record
from src.services.settlement import create_eligibility
from src.services.worldbridge import create_world_asset
from src.models.schemas import *

init_db()

print("Seeding MEMBRA CompanyOS demo data...")

# ─── 1. AgentOS: Register 9 core agents ───────────────────
agents = [
    ("Strategy Agent", "strategy", "Decides what MEMBRA should build next"),
    ("Product Agent", "product", "Converts strategy into product requirements"),
    ("Engineering Agent", "engineering", "Builds software and deploys services"),
    ("Ops Agent", "operations", "Creates SOPs, fulfillment flows, support processes"),
    ("Sales Agent", "sales", "Generates offers, landing pages, outreach, partner flows"),
    ("Finance Agent", "finance", "Tracks unit economics, payout eligibility, margin, runway"),
    ("Legal/Risk Agent", "legal", "Flags lease, local-rule, privacy, insurance, campaign risks"),
    ("Governance Agent", "governance", "Controls approvals, policies, permissions, escalation"),
    ("Proof Agent", "proof", "Writes every meaningful action into ProofBook"),
]

agent_ids = {}
for name, role, desc in agents:
    a = create_agent(AgentCreate(
        name=name, role=role, description=desc,
        tools=["api_call", "database_query", "report_generation"],
        permissions=["read", "recommend", "create_draft"],
        blocked_actions=["bypass_governance", "fake_payment", "guarantee_profit"],
    ))
    agent_ids[role] = a.agent_id
    print(f"  Agent: {name} ({a.agent_id})")

# ─── 2. OrchestrationOS: Create objectives & tasks ─────────
obj1 = create_objective(ObjectiveCreate(
    owner_id="usr_demo_001",
    title="Turn local apartment into monetized micro-warehouse",
    description="Use MEMBRA to convert underutilized apartment space into ad inventory, storage SKUs, and local fulfillment nodes.",
    priority="high"
))
print(f"  Objective: {obj1.title}")

tasks = [
    (obj1.objective_id, "Register apartment as WorldBridge asset", "worldbridge", None, "high"),
    (obj1.objective_id, "Photograph and catalog available spaces", "agent", agent_ids["product"], "high"),
    (obj1.objective_id, "Run risk assessment on local rules", "agent", agent_ids["legal"], "high"),
    (obj1.objective_id, "Create ad campaign for window visibility", "agent", agent_ids["sales"], "medium"),
    (obj1.objective_id, "Set up KPI tracking dashboard", "agent", agent_ids["finance"], "medium"),
]

for oid, title, assignee_type, assignee_id, priority in tasks:
    t = create_task(TaskCreate(
        objective_id=oid, title=title, assignee_type=assignee_type,
        assignee_id=assignee_id, priority=priority,
        proof_requirement="photo_or_document",
    ))
    print(f"    Task: {title}")

# ─── 3. JobOS: Create jobs from tasks ──────────────────────
job_types = [
    ("apartment_task", "Clean and stage apartment for ad photos", 5000),
    ("car_ad_task", "Apply car wrap advertising for local business", 12000),
    ("window_ad_task", "Install QR poster in first-floor window", 3000),
    ("kpi_analysis_task", "Analyze weekly KPI trends and suggest actions", 8000),
    ("fulfillment_task", "Pack and deliver neighborhood micro-orders", 4500),
]

for jt, title, reward in job_types:
    j = create_job(JobCreate(
        job_type=jt, title=title, description=f"Local job: {title}",
        reward_cents=reward, currency="USD", proof_required=True,
    ))
    print(f"  Job: {title} (${reward/100:.0f})")

# ─── 4. CompanyOS: Departments, SOPs, Operating Units ──────
deps = [
    ("Strategy", "Long-term direction and market analysis"),
    ("Product", "Feature development and user experience"),
    ("Engineering", "Software, infrastructure, and DevOps"),
    ("Operations", "Fulfillment, SOPs, and local execution"),
    ("Sales & Marketing", "Growth, partnerships, and revenue"),
    ("Finance", "Unit economics, payouts, and runway"),
    ("Legal & Risk", "Compliance, policies, and dispute handling"),
]

dept_ids = {}
for name, desc in deps:
    d = create_department(DepartmentCreate(
        name=name, description=desc,
        kpi_targets={"monthly_revenue_cents": 100000, "task_completion_rate": 0.85},
    ))
    dept_ids[name] = d.department_id
    print(f"  Dept: {name}")

# SOPs
sops = [
    (dept_ids["Operations"], "Register New WorldBridge Asset", [
        "Owner submits asset via Concierge",
        "Legal/Risk Agent runs local-rule check",
        "Product Agent catalogs capabilities",
        "Engineering Agent adds to inventory system",
        "Proof Agent writes hash to ProofBook",
    ]),
    (dept_ids["Sales & Marketing"], "Launch Ad Campaign", [
        "Advertiser creates campaign with budget",
        "Sales Agent matches to available placements",
        "Owner accepts placement and daily rate",
        "Creative submitted and reviewed",
        "Campaign funded and launched",
        "Proof verified before payout eligibility",
    ]),
    (dept_ids["Finance"], "Process Payout Eligibility", [
        "Job completed and proof submitted",
        "Proof Agent verifies hash",
        "Finance Agent calculates amount",
        "Governance Agent checks policy compliance",
        "Settlement eligibility record created",
        "External rail processes payment",
    ]),
]

for dept_id, title, steps in sops:
    s = create_sop(SOPCreate(
        department_id=dept_id, title=title, steps=steps,
        trigger_events=["asset_registered", "campaign_funded", "job_completed"],
    ))
    print(f"    SOP: {title}")

# Operating Units
units = [
    ("Downtown NYC Hub", dept_ids["Operations"], "micro_warehouse", "Manhattan, NYC"),
    ("Brooklyn Street Team", dept_ids["Sales & Marketing"], "mobile_inventory", "Brooklyn, NYC"),
    ("Remote KPI Analytics", dept_ids["Finance"], "analytics", "Global"),
]

for name, dept_id, unit_type, territory in units:
    u = create_operating_unit(OperatingUnitCreate(
        name=name, department_id=dept_id, unit_type=unit_type,
        territory=territory,
        kpi_snapshot={"active_assets": 12, "monthly_jobs": 45, "revenue_cents": 150000},
    ))
    print(f"  Unit: {name}")

# ─── 5. GovernanceOS: Policies & Approvals ─────────────────
policies = [
    ("Owner Consent Required", {"rule": "No real-world action without explicit owner consent", "severity": "blocking"}),
    ("No Guaranteed Profit", {"rule": "AI may not promise or guarantee income", "severity": "blocking"}),
    ("External Settlement Only", {"rule": "All money movement through external rails", "severity": "blocking"}),
    ("Proof Before Payout", {"rule": "Every payout requires verified proof record", "severity": "blocking"}),
    ("Local Rule Check", {"rule": "Asset listings require local regulation review", "severity": "warn"}),
]

for name, rules in policies:
    p = create_policy(PolicyCreate(name=name, rules=rules))
    print(f"  Policy: {name}")

# Approvals
approvals = [
    ("listing_visibility", "lst_001", "usr_demo_001", 0.3, "Request to make apartment listing public"),
    ("ad_campaign_launch", "camp_001", "usr_demo_002", 0.6, "New advertiser campaign targeting residential areas"),
    ("payout_release", "pay_001", "usr_demo_001", 0.2, "Job completion payout for window ad installation"),
]

for request_type, request_id, requester_id, risk, reason in approvals:
    a = create_approval(ApprovalCreate(
        request_type=request_type, request_id=request_id,
        requester_id=requester_id, risk_score=risk, reason=reason,
    ))
    print(f"  Approval: {request_type} ({a.approval_id})")

# ─── 6. ProofBook: Hash records ────────────────────────────
proofs = [
    ("task", "tsk_demo_001", {"action": "task_created", "by": "Strategy Agent"}),
    ("approval", "apr_demo_001", {"decision": "owner_consent_granted", "asset": "window_nyc_42"}),
    ("job", "job_demo_001", {"completion": "photo_verified", "payout_eligible": True}),
    ("policy", "pol_demo_001", {"violation_check": "passed", "risk_score": 0.15}),
]

for record_type, record_id, raw_data in proofs:
    pr = create_proof_record(ProofRecordCreate(
        record_type=record_type, record_id=record_id, raw_data=raw_data,
    ))
    print(f"  Proof: {record_type}/{record_id} -> {pr.hash[:16]}...")

# ─── 7. SettlementOS: Eligibility records ──────────────────
eligibilities = [
    ("usr_demo_001", "host", "job_demo_001", 5000, "stripe"),
    ("usr_demo_002", "agent", None, 8000, "stripe"),
    ("usr_demo_003", "operator", "job_demo_002", 12000, "wise"),
]

for party_id, party_type, job_id, amount, rail in eligibilities:
    e = create_eligibility(SettlementEligibilityCreate(
        party_id=party_id, party_type=party_type, job_id=job_id,
        amount_cents=amount, currency="USD", settlement_rail=rail,
    ))
    print(f"  Eligibility: {party_id} -> ${amount/100:.0f} ({rail})")

# ─── 8. WorldBridge: Real-world assets ─────────────────────
world_assets = [
    ("usr_demo_001", "apartment", "Downtown Studio", "First-floor studio with street-facing window", 40.7128, -74.0060),
    ("usr_demo_002", "vehicle", "Honda Civic 2019", "Daily commuter with rooftop ad potential", 40.6782, -73.9442),
    ("usr_demo_003", "window", "Storefront Window", "High-traffic corner window in SoHo", 40.7233, -74.0030),
    ("usr_demo_004", "tool", "DeWalt Drill Set", "Available for neighborhood task supply", 40.7500, -73.9800),
    ("usr_demo_005", "wearable", "MEMBRA Campaign Shirt", "QR-badge shirt for event campaigns", 40.6900, -73.9500),
]

for owner_id, asset_type, title, desc, lat, lng in world_assets:
    wa = create_world_asset(WorldAssetCreate(
        owner_id=owner_id, asset_type=asset_type, title=title, description=desc,
        latitude=lat, longitude=lng,
        capabilities=["ad_inventory", "local_fulfillment"] if asset_type in ["apartment", "window"] else ["mobile_ad", "delivery"],
    ))
    print(f"  WorldAsset: {title} ({asset_type})")

print("\nDone. MEMBRA CompanyOS seeded with demo data.")
print("Start backend: uvicorn main:app --reload --port 8000")
print("Start frontend: cd frontend && npm run dev")
