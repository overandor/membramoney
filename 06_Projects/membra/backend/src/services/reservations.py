from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.enums import VisitStatus
from src.models.schemas import ReservationCreate, ReservationOut, RiskDecision
from src.core.exceptions import MembraError
from src.services.identity import get_user
from src.services.assets import get_asset

def create_reservation(data: ReservationCreate) -> ReservationOut:
    guest = get_user(data.guest_id)
    if not guest:
        raise MembraError("Guest not found")
    if guest.blocked:
        raise MembraError("Guest is blocked")

    asset = get_asset(data.asset_id)
    if not asset:
        raise MembraError("Asset not found")
    if not asset.active:
        raise MembraError("Asset is not active")

    if data.guest_count > asset.max_guests:
        raise MembraError(f"Max guests for this asset is {asset.max_guests}")

    conn = get_connection()
    visit_id = generate_id("vis_")
    conn.execute(
        """
        INSERT INTO visits (visit_id, asset_id, guest_id, host_id, start_time, end_time, guest_count, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (visit_id, data.asset_id, data.guest_id, asset.host_id,
         data.start_time.isoformat(), data.end_time.isoformat(), data.guest_count,
         VisitStatus.requested.value, now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()
    return get_visit(visit_id)

def get_visit(visit_id: str) -> Optional[ReservationOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM visits WHERE visit_id = ?", (visit_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_visit(row)

def update_visit_status(visit_id: str, status: VisitStatus, **fields) -> ReservationOut:
    conn = get_connection()
    set_clauses = ["status = ?", "updated_at = ?"]
    params = [status.value, now_iso()]
    for k, v in fields.items():
        set_clauses.append(f"{k} = ?")
        params.append(v)
    params.append(visit_id)
    conn.execute(f"UPDATE visits SET {', '.join(set_clauses)} WHERE visit_id = ?", params)
    conn.commit()
    conn.close()
    visit = get_visit(visit_id)
    if not visit:
        raise MembraError("Visit disappeared")
    return visit

def apply_risk_decision(visit_id: str, decision: RiskDecision) -> ReservationOut:
    visit = get_visit(visit_id)
    if not visit:
        raise MembraError("Visit not found")
    if visit.status != VisitStatus.identity_verified:
        raise MembraError(f"Cannot apply risk decision from status {visit.status}")

    if decision.approved:
        return update_visit_status(
            visit_id, VisitStatus.risk_preapproved,
            risk_approved=1, risk_reason=decision.reason, risk_score=decision.risk_score
        )
    else:
        return update_visit_status(
            visit_id, VisitStatus.risk_denied,
            risk_approved=0, risk_reason=decision.reason, risk_score=decision.risk_score
        )

def list_visits(guest_id: Optional[str] = None, status: Optional[VisitStatus] = None) -> list[ReservationOut]:
    conn = get_connection()
    sql = "SELECT * FROM visits WHERE 1=1"
    params: list = []
    if guest_id:
        sql += " AND guest_id = ?"
        params.append(guest_id)
    if status:
        sql += " AND status = ?"
        params.append(status.value)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_visit(r) for r in rows]

def _row_to_visit(row: dict) -> ReservationOut:
    return ReservationOut(
        visit_id=row["visit_id"],
        asset_id=row["asset_id"],
        guest_id=row["guest_id"],
        host_id=row["host_id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        guest_count=row["guest_count"],
        status=VisitStatus(row["status"]),
        qr_token=row["qr_token"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
