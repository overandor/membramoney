from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from typing import Optional

from src.models.schemas import *
from src.models.enums import *
from src.services.identity import create_user, get_user, verify_identity, list_users
from src.services.assets import create_asset, get_asset, list_assets, nearby_assets
from src.services.reservations import create_reservation, get_visit, update_visit_status, apply_risk_decision, list_visits
from src.services.risk import evaluate_risk
from src.services.payments import calculate_quote, authorize_payment, capture_payment, refund_payment, release_payout, get_payment_by_visit
from src.services.insurance import request_quote, bind_coverage, get_coverage, get_coverage_by_visit, cancel_coverage
from src.services.access import access_ready, issue_qr, verify_qr, check_in, check_out
from src.services.incidents import create_incident, get_incident, create_claim, get_claim, create_dispute, get_dispute
from src.services.ads import (
    create_campaign, get_campaign, list_campaigns, update_campaign_status,
    create_placement, get_placement, list_placements, update_placement_status,
    submit_creative, get_creative, update_creative_status,
    submit_proof, get_proof, list_proofs, review_proof,
    create_payout, get_payout, release_payout, list_payouts,
    generate_qr, get_qr, record_scan, campaign_analytics, owner_analytics,
)
from src.services.wear import (
    create_wearer, get_wearer, get_wearer_by_user, list_wearers, verify_wearer,
    create_wearable, get_wearable, list_wearables, assign_wearable_to_campaign,
    submit_wear_proof, get_wear_proof, list_wear_proofs, review_wear_proof,
    wear_campaign_analytics, wearer_analytics,
)
from src.services.kpi import dashboard_summary, time_series_metrics, top_assets_by_revenue, top_hosts_by_revenue
from src.services.orchestration import create_objective, get_objective, list_objectives, update_objective_status, create_task, get_task, list_tasks, update_task_status
from src.services.agents import create_agent, get_agent, list_agents, update_agent_status
from src.services.jobs import create_job, get_job, list_jobs, assign_job, complete_job
from src.services.company import create_department, get_department, list_departments, create_sop, get_sop, list_sops, create_operating_unit, get_operating_unit, list_operating_units
from src.services.governance import create_policy, get_policy, list_policies, create_approval, get_approval, list_approvals, resolve_approval, log_audit_event, list_audit_events
from src.services.proofbook import create_proof_record, get_proof_record, list_proof_records, verify_proof
from src.services.settlement import create_eligibility, get_eligibility, list_eligibilities, mark_paid
from src.services.worldbridge import create_world_asset, get_world_asset, list_world_assets, update_world_asset_status
from src.services.concierge import parse_intent
from src.core.exceptions import MembraError, IdentityError, RiskDeniedError, PaymentError, InsuranceError, AccessDeniedError, CoverageNotActiveError

router = APIRouter(prefix="/v1")

# ─── Identity ───────────────────────────────────────────────
@router.post("/hosts", response_model=UserOut)
def post_host(data: UserCreate):
    data.user_type = UserType.host
    return create_user(data)

@router.post("/guests", response_model=UserOut)
def post_guest(data: UserCreate):
    data.user_type = UserType.guest
    return create_user(data)

@router.post("/identity/verify", response_model=IdentityVerifyOut)
def post_identity_verify(data: IdentityVerify):
    return verify_identity(data.user_id, data.document_type)

@router.get("/users")
def get_users(user_type: Optional[UserType] = None):
    return list_users(user_type)

# ─── Assets ───────────────────────────────────────────────
@router.post("/assets", response_model=AssetOut)
def post_asset(data: AssetCreate):
    return create_asset(data)

@router.get("/assets")
def get_assets(category: Optional[AssetCategory] = None):
    return list_assets(category)

@router.get("/assets/nearby")
def get_assets_nearby(lat: float, lng: float, radius_miles: float = 5.0, category: Optional[AssetCategory] = None):
    q = NearbyQuery(lat=lat, lng=lng, radius_miles=radius_miles, category=category)
    return nearby_assets(q)

@router.get("/assets/{asset_id}", response_model=AssetOut)
def get_asset_by_id(asset_id: str):
    a = get_asset(asset_id)
    if not a:
        raise HTTPException(404, "Asset not found")
    return a

# ─── Reservations ─────────────────────────────────────────
@router.post("/reservations", response_model=ReservationOut)
def post_reservation(data: ReservationCreate):
    return create_reservation(data)

@router.get("/reservations/{id}", response_model=ReservationOut)
def get_reservation(id: str):
    v = get_visit(id)
    if not v:
        raise HTTPException(404, "Reservation not found")
    return v

@router.post("/reservations/{id}/risk", response_model=ReservationOut)
def post_reservation_risk(id: str):
    visit = get_visit(id)
    if not visit:
        raise HTTPException(404, "Reservation not found")
    if visit.status == VisitStatus.requested:
        # Auto-advance to identity_verified for demo
        update_visit_status(id, VisitStatus.identity_verified)
        visit = get_visit(id)
    if visit.status != VisitStatus.identity_verified:
        raise HTTPException(400, f"Reservation must be identity_verified, got {visit.status}")
    decision = evaluate_risk(visit)
    return apply_risk_decision(id, decision)

@router.post("/reservations/{id}/approve", response_model=ReservationOut)
def post_reservation_approve(id: str):
    visit = get_visit(id)
    if not visit:
        raise HTTPException(404, "Reservation not found")
    # Auto-advance through full pipeline for demo
    if visit.status == VisitStatus.requested:
        # Auto-verify guest identity for demo
        from src.services.identity import verify_identity
        verify_identity(visit.guest_id)
        update_visit_status(id, VisitStatus.identity_verified)
        visit = get_visit(id)
    if visit.status == VisitStatus.identity_verified:
        decision = evaluate_risk(visit)
        apply_risk_decision(id, decision)
        visit = get_visit(id)
    if visit.status == VisitStatus.risk_preapproved:
        from src.services.assets import get_asset
        asset = get_asset(visit.asset_id)
        if asset and asset.insurable:
            request_quote(InsuranceQuoteRequest(visit_id=id, asset_category=asset.category, coverage_limit_cents=10000))
        else:
            update_visit_status(id, VisitStatus.insurance_quoted)
        visit = get_visit(id)
    if visit.status == VisitStatus.insurance_quoted:
        # Simulate authorized payment for demo
        authorize_payment(PaymentAuthorize(visit_id=id, provider="stripe", provider_payment_method_id="pm_demo"))
        visit = get_visit(id)
    if visit.status == VisitStatus.payment_authorized:
        bind_coverage(InsuranceBindRequest(visit_id=id, quote_id="demo"))
        visit = get_visit(id)
    if visit.status == VisitStatus.coverage_bound:
        issue_qr(id)
    return get_visit(id)

@router.post("/reservations/{id}/cancel", response_model=ReservationOut)
def post_reservation_cancel(id: str):
    visit = get_visit(id)
    if not visit:
        raise HTTPException(404, "Reservation not found")
    cancel_coverage(id)
    try:
        refund_payment(id)
    except PaymentError:
        pass
    return update_visit_status(id, VisitStatus.cancelled)

# ─── Insurance ────────────────────────────────────────────
@router.post("/insurance/quote", response_model=InsuranceQuoteOut)
def post_insurance_quote(data: InsuranceQuoteRequest):
    return request_quote(data)

@router.post("/insurance/bind", response_model=CoverageOut)
def post_insurance_bind(data: InsuranceBindRequest):
    return bind_coverage(data)

@router.get("/insurance/coverages/{coverage_id}", response_model=CoverageOut)
def get_coverage_by_id(coverage_id: str):
    c = get_coverage(coverage_id)
    if not c:
        raise HTTPException(404, "Coverage not found")
    return c

# ─── Payments ─────────────────────────────────────────────
@router.post("/payments/quote", response_model=PaymentQuote)
def post_payments_quote(data: dict):
    visit_id = data.get("visit_id")
    if not visit_id:
        raise HTTPException(400, "visit_id required")
    return calculate_quote(visit_id)

@router.post("/payments/authorize", response_model=PaymentOut)
def post_payments_authorize(data: PaymentAuthorize):
    return authorize_payment(data)

@router.post("/payments/capture", response_model=PaymentOut)
def post_payments_capture(data: dict):
    visit_id = data.get("visit_id")
    if not visit_id:
        raise HTTPException(400, "visit_id required")
    return capture_payment(visit_id)

@router.post("/payments/refund", response_model=PaymentOut)
def post_payments_refund(data: dict):
    visit_id = data.get("visit_id")
    if not visit_id:
        raise HTTPException(400, "visit_id required")
    return refund_payment(visit_id)

@router.post("/payouts/release", response_model=PaymentOut)
def post_payouts_release(data: PayoutRelease):
    return release_payout(data)

# ─── Access ───────────────────────────────────────────────
@router.post("/access/{visit_id}/qr")
def post_access_qr(visit_id: str):
    try:
        token = issue_qr(visit_id)
        return {"qr_token": token}
    except AccessDeniedError as e:
        raise HTTPException(403, str(e))

@router.post("/access/verify", response_model=QRVerifyOut)
def post_access_verify(data: QRVerify):
    return verify_qr(data.qr_payload)

@router.post("/access/check-in", response_model=CheckInOutResult)
def post_access_check_in(data: CheckInOut):
    try:
        return check_in(data.visit_id)
    except AccessDeniedError as e:
        raise HTTPException(403, str(e))

@router.post("/access/check-out", response_model=CheckInOutResult)
def post_access_check_out(data: CheckInOut):
    try:
        return check_out(data.visit_id)
    except AccessDeniedError as e:
        raise HTTPException(403, str(e))

# ─── Incidents / Claims / Disputes ────────────────────────
@router.post("/incidents", response_model=IncidentOut)
def post_incident(data: IncidentCreate):
    return create_incident(data)

@router.post("/claims", response_model=ClaimOut)
def post_claim(data: ClaimCreate):
    return create_claim(data)

@router.get("/claims/{claim_id}", response_model=ClaimOut)
def get_claim_by_id(claim_id: str):
    c = get_claim(claim_id)
    if not c:
        raise HTTPException(404, "Claim not found")
    return c

@router.post("/disputes", response_model=DisputeOut)
def post_dispute(data: DisputeCreate):
    return create_dispute(data)

# ─── Health / Debug ───────────────────────────────────────
@router.get("/health")
def health():
    return {"status": "ok", "service": "membra"}

@router.get("/access-gate/{visit_id}")
def debug_access_gate(visit_id: str):
    visit = get_visit(visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    payment = get_payment_by_visit(visit_id)
    coverage = get_coverage_by_visit(visit_id)
    risk = evaluate_risk(visit)
    if not payment or not coverage:
        return {
            "ready": False,
            "visit_status": visit.status.value,
            "payment_status": payment.status.value if payment else None,
            "coverage_status": coverage.status.value if coverage else None,
            "risk_approved": risk.approved,
        }
    ready = access_ready(visit, payment, coverage, risk)
    return {
        "ready": ready,
        "visit_status": visit.status.value,
        "payment_status": payment.status.value,
        "coverage_status": coverage.status.value,
        "external_policy_id": coverage.external_policy_id,
        "risk_approved": risk.approved,
        "risk_score": risk.risk_score,
        "message": "Access ready" if ready else "Access blocked",
    }

# ─── Ads: Campaigns ─────────────────────────────────────────
@router.post("/ad-campaigns", response_model=AdCampaignOut)
def post_ad_campaign(data: AdCampaignCreate):
    return create_campaign(data)

@router.get("/ad-campaigns")
def get_ad_campaigns(status: Optional[AdCampaignStatus] = None):
    return list_campaigns(status)

@router.get("/ad-campaigns/available")
def get_ad_campaigns_available(city: Optional[str] = None):
    campaigns = list_campaigns(AdCampaignStatus.funded)
    if city:
        campaigns = [c for c in campaigns if c.target_city and city.lower() in c.target_city.lower()]
    return campaigns

@router.get("/ad-campaigns/{campaign_id}", response_model=AdCampaignOut)
def get_ad_campaign(campaign_id: str):
    c = get_campaign(campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c

@router.post("/ad-campaigns/{campaign_id}/submit-creative")
def post_ad_submit_creative(campaign_id: str, data: AdCreativeSubmit):
    data.campaign_id = campaign_id
    return submit_creative(data)

@router.post("/ad-campaigns/{campaign_id}/approve-creative")
def post_ad_approve_creative(campaign_id: str, approved: bool = True, reviewer_notes: str = ""):
    creatives = list_creatives_for_campaign(campaign_id)
    for cr in creatives:
        update_creative_status(cr.creative_id, approved, reviewer_notes)
    if approved:
        update_campaign_status(campaign_id, AdCampaignStatus.creative_approved)
    return {"campaign_id": campaign_id, "approved": approved}

@router.post("/ad-campaigns/{campaign_id}/fund")
def post_ad_fund_campaign(campaign_id: str):
    return update_campaign_status(campaign_id, AdCampaignStatus.funded)

@router.post("/ad-campaigns/{campaign_id}/launch")
def post_ad_launch_campaign(campaign_id: str):
    return update_campaign_status(campaign_id, AdCampaignStatus.launched)

@router.post("/ad-campaigns/{campaign_id}/complete")
def post_ad_complete_campaign(campaign_id: str):
    return update_campaign_status(campaign_id, AdCampaignStatus.completed)

# ─── Ads: Placements ──────────────────────────────────────
@router.post("/ad-placements", response_model=AdPlacementOut)
def post_ad_placement(data: AdPlacementCreate):
    return create_placement(data)

@router.get("/ad-placements")
def get_ad_placements(campaign_id: Optional[str] = None, owner_id: Optional[str] = None):
    return list_placements(campaign_id, owner_id)

@router.get("/ad-placements/{placement_id}", response_model=AdPlacementOut)
def get_ad_placement(placement_id: str):
    p = get_placement(placement_id)
    if not p:
        raise HTTPException(404, "Placement not found")
    return p

class _AdAcceptBody(BaseModel):
    asset_id: str
    owner_id: str
    daily_rate_cents: int

@router.post("/ad-campaigns/{campaign_id}/accept")
def post_ad_accept_campaign(campaign_id: str, data: _AdAcceptBody):
    return create_placement(AdPlacementCreate(campaign_id=campaign_id, asset_id=data.asset_id, owner_id=data.owner_id, daily_rate_cents=data.daily_rate_cents))

# ─── Ads: Proofs ──────────────────────────────────────────
@router.post("/ad-proofs", response_model=AdProofOut)
def post_ad_proof(data: AdProofSubmit):
    return submit_proof(data)

@router.get("/ad-proofs")
def get_ad_proofs(placement_id: Optional[str] = None, campaign_id: Optional[str] = None):
    return list_proofs(placement_id, campaign_id)

@router.post("/ad-proofs/{placement_id}/review")
def post_ad_review_proof(placement_id: str, verified: bool = True, reviewer_notes: str = ""):
    return review_proof(placement_id, verified, reviewer_notes)

# ─── Ads: QR / Scan ───────────────────────────────────────
@router.post("/ad-placements/{placement_id}/qr")
def post_ad_placement_qr(placement_id: str):
    p = get_placement(placement_id)
    if not p:
        raise HTTPException(404, "Placement not found")
    return generate_qr(placement_id, p.campaign_id)

@router.post("/ad-qr-scan")
def post_ad_qr_scan(qr_id: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
    return record_scan(qr_id, ip_address, user_agent)

# ─── Ads: Payouts ─────────────────────────────────────────
@router.post("/ad-payouts")
def post_ad_payout(owner_id: str, placement_id: str, campaign_id: str, amount_cents: int):
    return create_payout(owner_id, placement_id, campaign_id, amount_cents)

@router.get("/ad-payouts/{payout_id}", response_model=AdPayoutOut)
def get_ad_payout(payout_id: str):
    p = get_payout(payout_id)
    if not p:
        raise HTTPException(404, "Payout not found")
    return p

@router.post("/ad-payouts/{payout_id}/release")
def post_ad_release_payout(payout_id: str):
    return release_payout(payout_id)

# ─── Ads: Analytics ───────────────────────────────────────
@router.get("/ad-analytics/campaign/{campaign_id}")
def get_ad_campaign_analytics(campaign_id: str):
    return campaign_analytics(campaign_id)

@router.get("/ad-analytics/owner/{owner_id}")
def get_ad_owner_analytics(owner_id: str):
    return owner_analytics(owner_id)

# Helper for creative listing
from src.db.database import get_connection
def list_creatives_for_campaign(campaign_id: str) -> list[AdCreativeOut]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM ad_creatives WHERE campaign_id = ?", (campaign_id,)).fetchall()
    conn.close()
    from src.services.ads import _row_to_creative
    return [_row_to_creative(r) for r in rows]

# ─── Wear: Wearers ────────────────────────────────────────
@router.post("/wearers", response_model=WearerOut)
def post_wearer(data: WearerCreate):
    return create_wearer(data)

@router.get("/wearers/{wearer_id}", response_model=WearerOut)
def get_wearer_by_id(wearer_id: str):
    w = get_wearer(wearer_id)
    if not w:
        raise HTTPException(404, "Wearer not found")
    return w

@router.get("/wearers/by-user/{user_id}", response_model=WearerOut)
def get_wearer_by_user_id(user_id: str):
    w = get_wearer_by_user(user_id)
    if not w:
        raise HTTPException(404, "Wearer not found")
    return w

@router.get("/wearers")
def get_wearers(city: Optional[str] = None):
    return list_wearers(city)

@router.post("/wearers/{wearer_id}/verify", response_model=WearerOut)
def post_verify_wearer(wearer_id: str):
    return verify_wearer(wearer_id)

# ─── Wear: Wearable Assets ─────────────────────────────────
@router.post("/wearables", response_model=WearableAssetOut)
def post_wearable(data: WearableAssetCreate):
    return create_wearable(data)

@router.get("/wearables/{wearable_id}", response_model=WearableAssetOut)
def get_wearable_by_id(wearable_id: str):
    w = get_wearable(wearable_id)
    if not w:
        raise HTTPException(404, "Wearable not found")
    return w

@router.get("/wearables")
def get_wearables(wearer_id: Optional[str] = None, status: Optional[str] = None):
    return list_wearables(wearer_id, status)

@router.post("/wearables/{wearable_id}/assign")
def post_assign_wearable(wearable_id: str, campaign_id: str):
    return assign_wearable_to_campaign(wearable_id, campaign_id)

# ─── Wear: Proofs ─────────────────────────────────────────
@router.post("/wear-proofs", response_model=WearProofOut)
def post_wear_proof(data: WearProofSubmit):
    return submit_wear_proof(data)

@router.get("/wear-proofs")
def get_wear_proofs(placement_id: Optional[str] = None, campaign_id: Optional[str] = None):
    return list_wear_proofs(placement_id, campaign_id)

@router.post("/wear-proofs/{placement_id}/review")
def post_review_wear_proof(placement_id: str, verified: bool = True, reviewer_notes: str = ""):
    return review_wear_proof(placement_id, verified, reviewer_notes)

# ─── Wear: Analytics ───────────────────────────────────────
@router.get("/wear-analytics/campaign/{campaign_id}")
def get_wear_campaign_analytics(campaign_id: str):
    return wear_campaign_analytics(campaign_id)

@router.get("/wear-analytics/wearer/{wearer_id}")
def get_wearer_analytics(wearer_id: str):
    return wearer_analytics(wearer_id)

# ─── KPI / Dashboard ──────────────────────────────────────
@router.get("/kpi/summary")
def get_kpi_summary():
    return dashboard_summary()

@router.get("/kpi/timeseries")
def get_kpi_timeseries(days: int = 30):
    return time_series_metrics(days)

@router.get("/kpi/top-assets")
def get_kpi_top_assets(limit: int = 10):
    return top_assets_by_revenue(limit)

@router.get("/kpi/top-hosts")
def get_kpi_top_hosts(limit: int = 10):
    return top_hosts_by_revenue(limit)

# ─── OrchestrationOS ────────────────────────────────────
@router.post("/objectives", response_model=ObjectiveOut)
def post_objective(data: ObjectiveCreate):
    return create_objective(data)

@router.get("/objectives/{objective_id}", response_model=ObjectiveOut)
def get_objective_by_id(objective_id: str):
    o = get_objective(objective_id)
    if not o:
        raise HTTPException(404, "Objective not found")
    return o

@router.get("/objectives")
def get_objectives(owner_id: Optional[str] = None, status: Optional[str] = None):
    return list_objectives(owner_id, status)

@router.patch("/objectives/{objective_id}/status")
def patch_objective_status(objective_id: str, status: str):
    return update_objective_status(objective_id, status)

@router.post("/tasks", response_model=TaskOut)
def post_task(data: TaskCreate):
    return create_task(data)

@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task_by_id(task_id: str):
    t = get_task(task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    return t

@router.get("/tasks")
def get_tasks(objective_id: Optional[str] = None, assignee_id: Optional[str] = None, status: Optional[str] = None):
    return list_tasks(objective_id, assignee_id, status)

@router.patch("/tasks/{task_id}/status")
def patch_task_status(task_id: str, status: str, assignee_id: Optional[str] = None):
    return update_task_status(task_id, status, assignee_id)

# ─── AgentOS ────────────────────────────────────────────
@router.post("/agents", response_model=AgentOut)
def post_agent(data: AgentCreate):
    return create_agent(data)

@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent_by_id(agent_id: str):
    a = get_agent(agent_id)
    if not a:
        raise HTTPException(404, "Agent not found")
    return a

@router.get("/agents")
def get_agents(role: Optional[str] = None, status: Optional[str] = None):
    return list_agents(role, status)

@router.patch("/agents/{agent_id}/status")
def patch_agent_status(agent_id: str, status: str):
    return update_agent_status(agent_id, status)

# ─── JobOS ──────────────────────────────────────────────
@router.post("/jobs", response_model=JobOut)
def post_job(data: JobCreate):
    return create_job(data)

@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job_by_id(job_id: str):
    j = get_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j

@router.get("/jobs")
def get_jobs(job_type: Optional[str] = None, status: Optional[str] = None, assignee_id: Optional[str] = None):
    return list_jobs(job_type, status, assignee_id)

@router.post("/jobs/{job_id}/assign")
def post_assign_job(job_id: str, assignee_id: str):
    return assign_job(job_id, assignee_id)

@router.post("/jobs/{job_id}/complete")
def post_complete_job(job_id: str):
    return complete_job(job_id)

# ─── CompanyOS ──────────────────────────────────────────
@router.post("/departments", response_model=DepartmentOut)
def post_department(data: DepartmentCreate):
    return create_department(data)

@router.get("/departments")
def get_departments():
    return list_departments()

@router.get("/departments/{department_id}", response_model=DepartmentOut)
def get_department_by_id(department_id: str):
    d = get_department(department_id)
    if not d:
        raise HTTPException(404, "Department not found")
    return d

@router.post("/sops", response_model=SOPOut)
def post_sop(data: SOPCreate):
    return create_sop(data)

@router.get("/sops")
def get_sops(department_id: Optional[str] = None):
    return list_sops(department_id)

@router.get("/sops/{sop_id}", response_model=SOPOut)
def get_sop_by_id(sop_id: str):
    s = get_sop(sop_id)
    if not s:
        raise HTTPException(404, "SOP not found")
    return s

@router.post("/operating-units", response_model=OperatingUnitOut)
def post_operating_unit(data: OperatingUnitCreate):
    return create_operating_unit(data)

@router.get("/operating-units")
def get_operating_units(department_id: Optional[str] = None):
    return list_operating_units(department_id)

@router.get("/operating-units/{unit_id}", response_model=OperatingUnitOut)
def get_operating_unit_by_id(unit_id: str):
    u = get_operating_unit(unit_id)
    if not u:
        raise HTTPException(404, "Operating unit not found")
    return u

# ─── GovernanceOS ───────────────────────────────────────
@router.post("/policies", response_model=PolicyOut)
def post_policy(data: PolicyCreate):
    return create_policy(data)

@router.get("/policies")
def get_policies(status: Optional[str] = None):
    return list_policies(status)

@router.get("/policies/{policy_id}", response_model=PolicyOut)
def get_policy_by_id(policy_id: str):
    p = get_policy(policy_id)
    if not p:
        raise HTTPException(404, "Policy not found")
    return p

@router.post("/approvals", response_model=ApprovalOut)
def post_approval(data: ApprovalCreate):
    return create_approval(data)

@router.get("/approvals")
def get_approvals(request_id: Optional[str] = None, status: Optional[str] = None):
    return list_approvals(request_id, status)

@router.get("/approvals/{approval_id}", response_model=ApprovalOut)
def get_approval_by_id(approval_id: str):
    a = get_approval(approval_id)
    if not a:
        raise HTTPException(404, "Approval not found")
    return a

@router.post("/approvals/{approval_id}/resolve")
def post_resolve_approval(approval_id: str, approver_id: str, status: str, reason: str = ""):
    return resolve_approval(approval_id, approver_id, status, reason)

@router.get("/audit-events")
def get_audit_events(target_type: Optional[str] = None, target_id: Optional[str] = None, limit: int = 100):
    return list_audit_events(target_type, target_id, limit)

# ─── ProofBook ──────────────────────────────────────────
@router.post("/proof-records", response_model=ProofRecordOut)
def post_proof_record(data: ProofRecordCreate):
    return create_proof_record(data)

@router.get("/proof-records/{proof_id}", response_model=ProofRecordOut)
def get_proof_by_id(proof_id: str):
    p = get_proof_record(proof_id)
    if not p:
        raise HTTPException(404, "Proof record not found")
    return p

@router.get("/proof-records")
def get_proof_records(record_type: Optional[str] = None, record_id: Optional[str] = None, limit: int = 100):
    return list_proof_records(record_type, record_id, limit)

@router.post("/proof-records/{proof_id}/verify")
def post_verify_proof(proof_id: str):
    return verify_proof(proof_id)

# ─── SettlementOS ─────────────────────────────────────
@router.post("/settlement-eligibility", response_model=SettlementEligibilityOut)
def post_settlement_eligibility(data: SettlementEligibilityCreate):
    return create_eligibility(data)

@router.get("/settlement-eligibility/{eligibility_id}", response_model=SettlementEligibilityOut)
def get_settlement_eligibility_by_id(eligibility_id: str):
    e = get_eligibility(eligibility_id)
    if not e:
        raise HTTPException(404, "Eligibility not found")
    return e

@router.get("/settlement-eligibility")
def get_settlement_eligibilities(party_id: Optional[str] = None, status: Optional[str] = None):
    return list_eligibilities(party_id, status)

@router.post("/settlement-eligibility/{eligibility_id}/mark-paid")
def post_mark_paid(eligibility_id: str, settlement_ref: str):
    return mark_paid(eligibility_id, settlement_ref)

# ─── WorldBridge ────────────────────────────────────────
@router.post("/world-assets", response_model=WorldAssetOut)
def post_world_asset(data: WorldAssetCreate):
    return create_world_asset(data)

@router.get("/world-assets/{world_asset_id}", response_model=WorldAssetOut)
def get_world_asset_by_id(world_asset_id: str):
    w = get_world_asset(world_asset_id)
    if not w:
        raise HTTPException(404, "World asset not found")
    return w

@router.get("/world-assets")
def get_world_assets(asset_type: Optional[str] = None, owner_id: Optional[str] = None, status: Optional[str] = None):
    return list_world_assets(asset_type, owner_id, status)

@router.patch("/world-assets/{world_asset_id}/status")
def patch_world_asset_status(world_asset_id: str, status: str):
    return update_world_asset_status(world_asset_id, status)

# ─── IntentOS / Concierge ───────────────────────────────
@router.post("/intent", response_model=IntentOut)
def post_intent(data: IntentRequest):
    return parse_intent(data)

# ─── Production Boundaries ──────────────────────────────
@router.get("/system/production-boundaries")
def get_production_boundaries():
    return {
        "system": "MEMBRA CompanyOS",
        "version": "0.2.0",
        "boundaries": {
            "no_fake_payments": True,
            "no_custody": True,
            "no_guaranteed_profit": True,
            "owner_consent_required": True,
            "external_settlement_only": True,
            "proof_and_governance_required": True,
            "ai_recommends_human_approves": True,
        },
        "orchestration": "AI structures tasks; humans or policy gates authorize execution.",
        "settlement": "External rails handle money movement. MEMBRA tracks eligibility only.",
        "governance": "Every real-world action requires proof, policy check, and audit trail.",
    }
