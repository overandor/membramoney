import json
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.enums import AdCampaignStatus, AdPlacementStatus, AdPayoutStatus
from src.models.schemas import (
    AdCampaignCreate, AdCampaignOut, AdPlacementCreate, AdPlacementOut,
    AdCreativeSubmit, AdCreativeOut, AdProofSubmit, AdProofOut,
    AdPayoutOut, QRTagOut,
)
from src.core.exceptions import MembraError

def _json_or_none(val):
    return json.loads(val) if val else None

def _json_or_list(val):
    return json.loads(val) if val else []

# ─── Campaigns ────────────────────────────────────────────────
def create_campaign(data: AdCampaignCreate) -> AdCampaignOut:
    conn = get_connection()
    cid = generate_id("cmp_")
    conn.execute(
        """
        INSERT INTO ad_campaigns (campaign_id, advertiser_id, title, description, target_city,
            target_neighborhoods, asset_types, budget_cents, daily_budget_cents, start_date, end_date,
            status, destination_url, payout_rules, proof_rules, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cid, data.advertiser_id, data.title, data.description or "", data.target_city or "",
            json.dumps(data.target_neighborhoods), json.dumps(data.asset_types), data.budget_cents,
            data.daily_budget_cents or 0,
            data.start_date.isoformat() if data.start_date else None,
            data.end_date.isoformat() if data.end_date else None,
            AdCampaignStatus.draft.value, data.destination_url or "",
            json.dumps(data.payout_rules) if data.payout_rules else None,
            None, now_iso(), now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    return get_campaign(cid)

def get_campaign(campaign_id: str) -> Optional[AdCampaignOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM ad_campaigns WHERE campaign_id = ?", (campaign_id,)).fetchone()
    conn.close()
    return _row_to_campaign(row) if row else None

def list_campaigns(status: Optional[AdCampaignStatus] = None) -> list[AdCampaignOut]:
    conn = get_connection()
    sql = "SELECT * FROM ad_campaigns ORDER BY created_at DESC"
    params = ()
    if status:
        sql = "SELECT * FROM ad_campaigns WHERE status = ? ORDER BY created_at DESC"
        params = (status.value,)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_campaign(r) for r in rows]

def update_campaign_status(campaign_id: str, status: AdCampaignStatus, **fields) -> AdCampaignOut:
    conn = get_connection()
    set_clauses = ["status = ?", "updated_at = ?"]
    params = [status.value, now_iso()]
    for k, v in fields.items():
        set_clauses.append(f"{k} = ?")
        params.append(v)
    params.append(campaign_id)
    conn.execute(f"UPDATE ad_campaigns SET {', '.join(set_clauses)} WHERE campaign_id = ?", params)
    conn.commit()
    conn.close()
    c = get_campaign(campaign_id)
    if not c:
        raise MembraError("Campaign disappeared")
    return c

def _row_to_campaign(row) -> AdCampaignOut:
    return AdCampaignOut(
        campaign_id=row["campaign_id"],
        advertiser_id=row["advertiser_id"],
        title=row["title"],
        description=row["description"] or None,
        target_city=row["target_city"] or None,
        target_neighborhoods=_json_or_list(row["target_neighborhoods"]),
        asset_types=_json_or_list(row["asset_types"]),
        budget_cents=row["budget_cents"],
        daily_budget_cents=row["daily_budget_cents"] or None,
        start_date=row["start_date"],
        end_date=row["end_date"],
        status=row["status"],
        creative_url=row["creative_url"] or None,
        approved_creative_url=row["approved_creative_url"] or None,
        destination_url=row["destination_url"] or None,
        payout_rules=_json_or_none(row["payout_rules"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

# ─── Placements ───────────────────────────────────────────────
def create_placement(data: AdPlacementCreate) -> AdPlacementOut:
    conn = get_connection()
    pid = generate_id("plc_")
    conn.execute(
        "INSERT INTO ad_placements (placement_id, campaign_id, asset_id, owner_id, daily_rate_cents, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (pid, data.campaign_id, data.asset_id, data.owner_id, data.daily_rate_cents, AdPlacementStatus.pending.value, now_iso()),
    )
    conn.commit()
    conn.close()
    return get_placement(pid)

def get_placement(placement_id: str) -> Optional[AdPlacementOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM ad_placements WHERE placement_id = ?", (placement_id,)).fetchone()
    conn.close()
    return _row_to_placement(row) if row else None

def list_placements(campaign_id: Optional[str] = None, owner_id: Optional[str] = None) -> list[AdPlacementOut]:
    conn = get_connection()
    sql = "SELECT * FROM ad_placements WHERE 1=1"
    params = []
    if campaign_id:
        sql += " AND campaign_id = ?"
        params.append(campaign_id)
    if owner_id:
        sql += " AND owner_id = ?"
        params.append(owner_id)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_placement(r) for r in rows]

def update_placement_status(placement_id: str, status: AdPlacementStatus) -> AdPlacementOut:
    conn = get_connection()
    conn.execute("UPDATE ad_placements SET status = ? WHERE placement_id = ?", (status.value, placement_id))
    conn.commit()
    conn.close()
    p = get_placement(placement_id)
    if not p:
        raise MembraError("Placement disappeared")
    return p

def _row_to_placement(row) -> AdPlacementOut:
    return AdPlacementOut(
        placement_id=row["placement_id"],
        campaign_id=row["campaign_id"],
        asset_id=row["asset_id"],
        owner_id=row["owner_id"],
        daily_rate_cents=row["daily_rate_cents"],
        status=row["status"],
        created_at=row["created_at"],
    )

# ─── Creatives ──────────────────────────────────────────────
def submit_creative(data: AdCreativeSubmit) -> AdCreativeOut:
    conn = get_connection()
    cid = generate_id("crt_")
    conn.execute(
        "INSERT INTO ad_creatives (creative_id, campaign_id, asset_type, mockup_url, print_ready_url, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cid, data.campaign_id, data.asset_type, data.mockup_url, data.print_ready_url, "pending", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_creative(cid)

def get_creative(creative_id: str) -> Optional[AdCreativeOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM ad_creatives WHERE creative_id = ?", (creative_id,)).fetchone()
    conn.close()
    return _row_to_creative(row) if row else None

def update_creative_status(creative_id: str, approved: bool, reviewer_notes: str = "") -> AdCreativeOut:
    conn = get_connection()
    status = "approved" if approved else "rejected"
    conn.execute("UPDATE ad_creatives SET status = ?, reviewer_notes = ? WHERE creative_id = ?", (status, reviewer_notes, creative_id))
    conn.commit()
    conn.close()
    return get_creative(creative_id)

def _row_to_creative(row) -> AdCreativeOut:
    return AdCreativeOut(
        creative_id=row["creative_id"],
        campaign_id=row["campaign_id"],
        asset_type=row["asset_type"] or None,
        mockup_url=row["mockup_url"] or None,
        print_ready_url=row["print_ready_url"] or None,
        status=row["status"],
        reviewer_notes=row["reviewer_notes"] or None,
        created_at=row["created_at"],
    )

# ─── Proofs ─────────────────────────────────────────────────
def submit_proof(data: AdProofSubmit) -> AdProofOut:
    placement = get_placement(data.placement_id)
    if not placement:
        raise MembraError("Placement not found")
    conn = get_connection()
    pid = generate_id("prf_")
    conn.execute(
        """
        INSERT INTO ad_proofs (proof_id, placement_id, campaign_id, owner_id, proof_type, photo_url, latitude, longitude, verified, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (pid, data.placement_id, placement.campaign_id, placement.owner_id, data.proof_type,
         data.photo_url, data.latitude, data.longitude, 0, now_iso()),
    )
    conn.commit()
    conn.close()
    return get_proof(pid)

def get_proof(proof_id: str) -> Optional[AdProofOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM ad_proofs WHERE proof_id = ?", (proof_id,)).fetchone()
    conn.close()
    return _row_to_proof(row) if row else None

def list_proofs(placement_id: Optional[str] = None, campaign_id: Optional[str] = None) -> list[AdProofOut]:
    conn = get_connection()
    sql = "SELECT * FROM ad_proofs WHERE 1=1"
    params = []
    if placement_id:
        sql += " AND placement_id = ?"
        params.append(placement_id)
    if campaign_id:
        sql += " AND campaign_id = ?"
        params.append(campaign_id)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_proof(r) for r in rows]

def review_proof(placement_id: str, verified: bool, reviewer_notes: str = "") -> dict:
    conn = get_connection()
    conn.execute("UPDATE ad_proofs SET verified = ?, reviewer_notes = ? WHERE placement_id = ?", (int(verified), reviewer_notes, placement_id))
    conn.commit()
    # Update payouts to eligible if verified
    if verified:
        conn.execute("UPDATE ad_payouts SET status = ?, proof_verified = 1 WHERE placement_id = ? AND status = ?",
                     (AdPayoutStatus.eligible.value, placement_id, AdPayoutStatus.pending.value))
        conn.commit()
    conn.close()
    return {"placement_id": placement_id, "verified": verified}

def _row_to_proof(row) -> AdProofOut:
    return AdProofOut(
        proof_id=row["proof_id"],
        placement_id=row["placement_id"],
        campaign_id=row["campaign_id"],
        owner_id=row["owner_id"],
        proof_type=row["proof_type"],
        photo_url=row["photo_url"] or None,
        latitude=row["latitude"] or None,
        longitude=row["longitude"] or None,
        verified=bool(row["verified"]),
        reviewer_notes=row["reviewer_notes"] or None,
        created_at=row["created_at"],
    )

# ─── Payouts ──────────────────────────────────────────────────
def create_payout(owner_id: str, placement_id: str, campaign_id: str, amount_cents: int) -> AdPayoutOut:
    conn = get_connection()
    pid = generate_id("pout_")
    conn.execute(
        "INSERT INTO ad_payouts (payout_id, owner_id, placement_id, campaign_id, amount_cents, status, proof_verified, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, owner_id, placement_id, campaign_id, amount_cents, AdPayoutStatus.pending.value, 0, now_iso()),
    )
    conn.commit()
    conn.close()
    return get_payout(pid)

def get_payout(payout_id: str) -> Optional[AdPayoutOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM ad_payouts WHERE payout_id = ?", (payout_id,)).fetchone()
    conn.close()
    return _row_to_payout(row) if row else None

def release_payout(payout_id: str) -> AdPayoutOut:
    conn = get_connection()
    conn.execute("UPDATE ad_payouts SET status = ?, released_at = ? WHERE payout_id = ?",
                 (AdPayoutStatus.released.value, now_iso(), payout_id))
    conn.commit()
    conn.close()
    p = get_payout(payout_id)
    if not p:
        raise MembraError("Payout disappeared")
    return p

def list_payouts(owner_id: Optional[str] = None, campaign_id: Optional[str] = None) -> list[AdPayoutOut]:
    conn = get_connection()
    sql = "SELECT * FROM ad_payouts WHERE 1=1"
    params = []
    if owner_id:
        sql += " AND owner_id = ?"
        params.append(owner_id)
    if campaign_id:
        sql += " AND campaign_id = ?"
        params.append(campaign_id)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_payout(r) for r in rows]

def _row_to_payout(row) -> AdPayoutOut:
    return AdPayoutOut(
        payout_id=row["payout_id"],
        owner_id=row["owner_id"],
        placement_id=row["placement_id"],
        campaign_id=row["campaign_id"],
        amount_cents=row["amount_cents"],
        status=row["status"],
        proof_verified=bool(row["proof_verified"]),
        created_at=row["created_at"],
        released_at=row["released_at"] or None,
    )

# ─── QR Tags ────────────────────────────────────────────────
def generate_qr(placement_id: str, campaign_id: str, redirect_url: Optional[str] = None) -> QRTagOut:
    conn = get_connection()
    qid = generate_id("qr_")
    tracking_url = f"https://membra.app/t/{qid}"
    conn.execute(
        "INSERT INTO qr_tags (qr_id, placement_id, campaign_id, tracking_url, redirect_url, scan_count, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (qid, placement_id, campaign_id, tracking_url, redirect_url or "", 0, 1, now_iso()),
    )
    conn.commit()
    conn.close()
    return get_qr(qid)

def get_qr(qr_id: str) -> Optional[QRTagOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM qr_tags WHERE qr_id = ?", (qr_id,)).fetchone()
    conn.close()
    return _row_to_qr(row) if row else None

def record_scan(qr_id: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                latitude: Optional[float] = None, longitude: Optional[float] = None) -> dict:
    qr = get_qr(qr_id)
    if not qr or not qr.is_active:
        raise MembraError("QR not found or inactive")
    conn = get_connection()
    sid = generate_id("scn_")
    conn.execute(
        "INSERT INTO ad_scan_events (scan_id, qr_id, campaign_id, placement_id, ip_address, user_agent, latitude, longitude, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, qr_id, qr.campaign_id, qr.placement_id, ip_address, user_agent, latitude, longitude, now_iso()),
    )
    conn.execute("UPDATE qr_tags SET scan_count = scan_count + 1 WHERE qr_id = ?", (qr_id,))
    conn.commit()
    conn.close()
    return {"scan_id": sid, "qr_id": qr_id, "redirect_url": qr.redirect_url}

def get_campaign_scans(campaign_id: str) -> int:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM ad_scan_events WHERE campaign_id = ?", (campaign_id,)).fetchone()[0]
    conn.close()
    return count

def _row_to_qr(row) -> QRTagOut:
    return QRTagOut(
        qr_id=row["qr_id"],
        placement_id=row["placement_id"] or None,
        campaign_id=row["campaign_id"] or None,
        tracking_url=row["tracking_url"] or None,
        redirect_url=row["redirect_url"] or None,
        scan_count=row["scan_count"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
    )

# ─── Analytics ──────────────────────────────────────────────
def campaign_analytics(campaign_id: str) -> dict:
    campaign = get_campaign(campaign_id)
    if not campaign:
        raise MembraError("Campaign not found")
    placements = list_placements(campaign_id=campaign_id)
    proofs = list_proofs(campaign_id=campaign_id)
    verified_proofs = [p for p in proofs if p.verified]
    scans = get_campaign_scans(campaign_id)
    payouts = list_payouts(campaign_id=campaign_id)
    released_payouts = [p for p in payouts if p.status == "released"]
    total_released_cents = sum(p.amount_cents for p in released_payouts)
    return {
        "campaign_id": campaign_id,
        "title": campaign.title,
        "status": campaign.status,
        "budget_cents": campaign.budget_cents,
        "total_placements": len(placements),
        "active_placements": len([p for p in placements if p.status == "active"]),
        "total_proofs": len(proofs),
        "verified_proofs": len(verified_proofs),
        "total_scans": scans,
        "total_payouts": len(payouts),
        "released_payouts": len(released_payouts),
        "total_released_cents": total_released_cents,
    }

def owner_analytics(owner_id: str) -> dict:
    placements = list_placements(owner_id=owner_id)
    payouts = list_payouts(owner_id=owner_id)
    released = [p for p in payouts if p.status == "released"]
    eligible = [p for p in payouts if p.status == "eligible"]
    return {
        "owner_id": owner_id,
        "total_placements": len(placements),
        "active_placements": len([p for p in placements if p.status == "active"]),
        "total_earnings_cents": sum(p.amount_cents for p in released),
        "pending_earnings_cents": sum(p.amount_cents for p in eligible),
        "total_payouts": len(payouts),
    }
