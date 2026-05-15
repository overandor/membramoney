from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import IncidentCreate, IncidentOut, ClaimCreate, ClaimOut, DisputeCreate, DisputeOut
from src.services.reservations import get_visit

def create_incident(data: IncidentCreate) -> IncidentOut:
    conn = get_connection()
    incident_id = generate_id("inc_")
    conn.execute(
        """
        INSERT INTO incidents (incident_id, visit_id, reporter_id, description, severity, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (incident_id, data.visit_id, data.reporter_id, data.description, data.severity, "open", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_incident(incident_id)

def get_incident(incident_id: str) -> Optional[IncidentOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return IncidentOut(
        incident_id=row["incident_id"],
        visit_id=row["visit_id"],
        reporter_id=row["reporter_id"],
        description=row["description"],
        severity=row["severity"],
        status=row["status"],
        created_at=row["created_at"],
    )

def create_claim(data: ClaimCreate) -> ClaimOut:
    conn = get_connection()
    claim_id = generate_id("clm_")
    conn.execute(
        """
        INSERT INTO claims (claim_id, incident_id, coverage_id, external_claim_id, description, damage_cents, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (claim_id, data.incident_id, data.coverage_id, None, data.description, data.damage_cents, "submitted", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_claim(claim_id)

def get_claim(claim_id: str) -> Optional[ClaimOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return ClaimOut(
        claim_id=row["claim_id"],
        incident_id=row["incident_id"],
        coverage_id=row["coverage_id"],
        external_claim_id=row["external_claim_id"],
        description=row["description"],
        damage_cents=row["damage_cents"],
        status=row["status"],
        created_at=row["created_at"],
    )

def create_dispute(data: DisputeCreate) -> DisputeOut:
    conn = get_connection()
    dispute_id = generate_id("dsp_")
    conn.execute(
        """
        INSERT INTO disputes (dispute_id, visit_id, reason, requested_refund_cents, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (dispute_id, data.visit_id, data.reason, data.requested_refund_cents, "open", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_dispute(dispute_id)

def get_dispute(dispute_id: str) -> Optional[DisputeOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM disputes WHERE dispute_id = ?", (dispute_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return DisputeOut(
        dispute_id=row["dispute_id"],
        visit_id=row["visit_id"],
        reason=row["reason"],
        requested_refund_cents=row["requested_refund_cents"],
        status=row["status"],
        created_at=row["created_at"],
    )
