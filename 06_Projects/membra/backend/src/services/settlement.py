from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import SettlementEligibilityCreate, SettlementEligibilityOut
from src.core.exceptions import MembraError

def create_eligibility(data: SettlementEligibilityCreate) -> SettlementEligibilityOut:
    conn = get_connection()
    eid = generate_id("stl_")
    conn.execute(
        """
        INSERT INTO settlement_eligibility (eligibility_id, party_id, party_type, job_id, amount_cents, currency, status, proof_id, settlement_rail, settlement_ref, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (eid, data.party_id, data.party_type, data.job_id, data.amount_cents, data.currency,
         "pending", data.proof_id, data.settlement_rail, None, now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()
    return get_eligibility(eid)

def get_eligibility(eligibility_id: str) -> Optional[SettlementEligibilityOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM settlement_eligibility WHERE eligibility_id = ?", (eligibility_id,)).fetchone()
    conn.close()
    return _row_to_eligibility(row) if row else None

def list_eligibilities(party_id: Optional[str] = None, status: Optional[str] = None) -> list[SettlementEligibilityOut]:
    conn = get_connection()
    sql = "SELECT * FROM settlement_eligibility WHERE 1=1"
    params = []
    if party_id:
        sql += " AND party_id = ?"
        params.append(party_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_eligibility(r) for r in rows]

def mark_paid(eligibility_id: str, settlement_ref: str) -> SettlementEligibilityOut:
    conn = get_connection()
    conn.execute(
        "UPDATE settlement_eligibility SET status = ?, settlement_ref = ?, updated_at = ? WHERE eligibility_id = ?",
        ("paid", settlement_ref, now_iso(), eligibility_id),
    )
    conn.commit()
    conn.close()
    e = get_eligibility(eligibility_id)
    if not e:
        raise MembraError("Eligibility record disappeared")
    return e

def _row_to_eligibility(row) -> SettlementEligibilityOut:
    return SettlementEligibilityOut(
        eligibility_id=row["eligibility_id"],
        party_id=row["party_id"],
        party_type=row["party_type"],
        job_id=row["job_id"] or None,
        amount_cents=row["amount_cents"],
        currency=row["currency"],
        status=row["status"],
        proof_id=row["proof_id"] or None,
        settlement_rail=row["settlement_rail"] or None,
        settlement_ref=row["settlement_ref"] or None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
