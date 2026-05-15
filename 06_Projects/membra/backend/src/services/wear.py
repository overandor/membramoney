import json
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import WearerCreate, WearerOut, WearableAssetCreate, WearableAssetOut, WearProofSubmit, WearProofOut
from src.core.exceptions import MembraError
from src.services.ads import get_placement

def _json_or_list(val):
    return json.loads(val) if val else []

# ─── Wearers ────────────────────────────────────────────────
def create_wearer(data: WearerCreate) -> WearerOut:
    conn = get_connection()
    wid = generate_id("wear_")
    conn.execute(
        """
        INSERT INTO wearers (wearer_id, user_id, email, name, phone, identity_verified,
            body_size, clothing_prefs, preferred_garments, city, neighborhood, daily_rate_cents,
            is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (wid, data.user_id, data.email, data.name, data.phone, 0,
         data.body_size, data.clothing_prefs, json.dumps(data.preferred_garments),
         data.city, data.neighborhood, data.daily_rate_cents, 1, now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()
    return get_wearer(wid)

def get_wearer(wearer_id: str) -> Optional[WearerOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM wearers WHERE wearer_id = ?", (wearer_id,)).fetchone()
    conn.close()
    return _row_to_wearer(row) if row else None

def get_wearer_by_user(user_id: str) -> Optional[WearerOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM wearers WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return _row_to_wearer(row) if row else None

def list_wearers(city: Optional[str] = None, is_active: bool = True) -> list[WearerOut]:
    conn = get_connection()
    sql = "SELECT * FROM wearers WHERE 1=1"
    params = []
    if city:
        sql += " AND city = ?"
        params.append(city)
    if is_active:
        sql += " AND is_active = 1"
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_wearer(r) for r in rows]

def verify_wearer(wearer_id: str) -> WearerOut:
    conn = get_connection()
    conn.execute("UPDATE wearers SET identity_verified = 1, updated_at = ? WHERE wearer_id = ?", (now_iso(), wearer_id))
    conn.commit()
    conn.close()
    w = get_wearer(wearer_id)
    if not w:
        raise MembraError("Wearer disappeared")
    return w

def _row_to_wearer(row) -> WearerOut:
    return WearerOut(
        wearer_id=row["wearer_id"],
        user_id=row["user_id"],
        email=row["email"],
        name=row["name"],
        phone=row["phone"] or None,
        identity_verified=bool(row["identity_verified"]),
        body_size=row["body_size"] or None,
        clothing_prefs=row["clothing_prefs"] or None,
        preferred_garments=_json_or_list(row["preferred_garments"]),
        city=row["city"] or None,
        neighborhood=row["neighborhood"] or None,
        daily_rate_cents=row["daily_rate_cents"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

# ─── Wearable Assets ──────────────────────────────────────
def create_wearable(data: WearableAssetCreate) -> WearableAssetOut:
    conn = get_connection()
    wid = generate_id("wbl_")
    serial = data.serial_id or f"SN_{generate_id()[:8].upper()}"
    conn.execute(
        """
        INSERT INTO wearable_assets (wearable_id, wearer_id, garment_type, size, color, brand, serial_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (wid, data.wearer_id, data.garment_type, data.size, data.color, data.brand, serial, "available", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_wearable(wid)

def get_wearable(wearable_id: str) -> Optional[WearableAssetOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM wearable_assets WHERE wearable_id = ?", (wearable_id,)).fetchone()
    conn.close()
    return _row_to_wearable(row) if row else None

def list_wearables(wearer_id: Optional[str] = None, status: Optional[str] = None) -> list[WearableAssetOut]:
    conn = get_connection()
    sql = "SELECT * FROM wearable_assets WHERE 1=1"
    params = []
    if wearer_id:
        sql += " AND wearer_id = ?"
        params.append(wearer_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_wearable(r) for r in rows]

def assign_wearable_to_campaign(wearable_id: str, campaign_id: str) -> WearableAssetOut:
    conn = get_connection()
    conn.execute("UPDATE wearable_assets SET campaign_id = ?, status = ? WHERE wearable_id = ?",
                 (campaign_id, "assigned", wearable_id))
    conn.commit()
    conn.close()
    w = get_wearable(wearable_id)
    if not w:
        raise MembraError("Wearable disappeared")
    return w

def _row_to_wearable(row) -> WearableAssetOut:
    return WearableAssetOut(
        wearable_id=row["wearable_id"],
        wearer_id=row["wearer_id"],
        garment_type=row["garment_type"],
        size=row["size"] or None,
        color=row["color"] or None,
        brand=row["brand"] or None,
        serial_id=row["serial_id"] or None,
        qr_id=row["qr_id"] or None,
        nfc_id=row["nfc_id"] or None,
        campaign_id=row["campaign_id"] or None,
        status=row["status"],
        created_at=row["created_at"],
    )

# ─── Wear Proofs ──────────────────────────────────────────
def submit_wear_proof(data: WearProofSubmit) -> WearProofOut:
    placement = get_placement(data.placement_id)
    if not placement:
        raise MembraError("Placement not found")
    conn = get_connection()
    pid = generate_id("wpr_")
    conn.execute(
        """
        INSERT INTO wear_proofs (wear_proof_id, placement_id, campaign_id, wearer_id, selfie_url, latitude, longitude, verified, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (pid, data.placement_id, placement.campaign_id, placement.owner_id,
         data.selfie_url, data.latitude, data.longitude, 0, now_iso()),
    )
    conn.commit()
    conn.close()
    return get_wear_proof(pid)

def get_wear_proof(wear_proof_id: str) -> Optional[WearProofOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM wear_proofs WHERE wear_proof_id = ?", (wear_proof_id,)).fetchone()
    conn.close()
    return _row_to_wear_proof(row) if row else None

def list_wear_proofs(placement_id: Optional[str] = None, campaign_id: Optional[str] = None) -> list[WearProofOut]:
    conn = get_connection()
    sql = "SELECT * FROM wear_proofs WHERE 1=1"
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
    return [_row_to_wear_proof(r) for r in rows]

def review_wear_proof(placement_id: str, verified: bool, reviewer_notes: str = "") -> dict:
    conn = get_connection()
    conn.execute("UPDATE wear_proofs SET verified = ?, reviewer_notes = ? WHERE placement_id = ?",
                 (int(verified), reviewer_notes, placement_id))
    conn.commit()
    if verified:
        from src.models.enums import AdPayoutStatus
        conn.execute("UPDATE ad_payouts SET status = ?, proof_verified = 1 WHERE placement_id = ? AND status = ?",
                     (AdPayoutStatus.eligible.value, placement_id, AdPayoutStatus.pending.value))
        conn.commit()
    conn.close()
    return {"placement_id": placement_id, "verified": verified}

def _row_to_wear_proof(row) -> WearProofOut:
    return WearProofOut(
        wear_proof_id=row["wear_proof_id"],
        placement_id=row["placement_id"],
        campaign_id=row["campaign_id"],
        wearer_id=row["wearer_id"],
        selfie_url=row["selfie_url"] or None,
        latitude=row["latitude"] or None,
        longitude=row["longitude"] or None,
        verified=bool(row["verified"]),
        reviewer_notes=row["reviewer_notes"] or None,
        created_at=row["created_at"],
    )

# ─── Wear Analytics ───────────────────────────────────────
def wear_campaign_analytics(campaign_id: str) -> dict:
    from src.services.ads import get_campaign, list_placements, get_campaign_scans
    campaign = get_campaign(campaign_id)
    if not campaign:
        raise MembraError("Campaign not found")
    placements = list_placements(campaign_id=campaign_id)
    proofs = list_wear_proofs(campaign_id=campaign_id)
    verified = [p for p in proofs if p.verified]
    scans = get_campaign_scans(campaign_id)
    return {
        "campaign_id": campaign_id,
        "title": campaign.title,
        "wearers": len(placements),
        "proofs_submitted": len(proofs),
        "proofs_verified": len(verified),
        "qr_scans": scans,
    }

def wearer_analytics(wearer_id: str) -> dict:
    wearables = list_wearables(wearer_id=wearer_id)
    proofs = list_wear_proofs()
    # Filter proofs by matching placement->wearer
    from src.services.ads import list_payouts
    payouts = list_payouts(owner_id=wearer_id)
    released = [p for p in payouts if p.status == "released"]
    return {
        "wearer_id": wearer_id,
        "garments": len(wearables),
        "campaigns": len([w for w in wearables if w.campaign_id]),
        "total_earnings_cents": sum(p.amount_cents for p in released),
    }
