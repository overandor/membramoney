from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.enums import CoverageStatus, VisitStatus
from src.models.schemas import (
    InsuranceQuoteRequest, InsuranceQuoteOut, InsuranceBindRequest, CoverageOut,
)
from src.core.exceptions import InsuranceError
from src.services.reservations import get_visit, update_visit_status

def request_quote(req: InsuranceQuoteRequest) -> InsuranceQuoteOut:
    visit = get_visit(req.visit_id)
    if not visit:
        raise InsuranceError("Visit not found")
    if visit.status != VisitStatus.risk_preapproved:
        raise InsuranceError(f"Cannot quote insurance from status {visit.status}")

    # Vendor-neutral adapter: simulate external quote
    premium = int(req.coverage_limit_cents * 0.07)
    quote_id = generate_id("quo_")
    external_quote_id = generate_id("extq_")

    quote = InsuranceQuoteOut(
        quote_id=quote_id,
        external_quote_id=external_quote_id,
        visit_id=req.visit_id,
        premium_cents=premium,
        currency="USD",
        quote_expires_at=now_iso(),
        coverage_limit_cents=req.coverage_limit_cents,
        deductible_cents=min(5000, req.coverage_limit_cents // 10),
        covered_events=["theft", "damage", "liability"],
        terms_url="https://membra.insurance/terms",
    )

    # Advance visit to insurance_quoted
    update_visit_status(req.visit_id, VisitStatus.insurance_quoted)
    return quote

def bind_coverage(req: InsuranceBindRequest) -> CoverageOut:
    visit = get_visit(req.visit_id)
    if not visit:
        raise InsuranceError("Visit not found")
    if visit.status != VisitStatus.payment_authorized:
        raise InsuranceError(f"Cannot bind coverage from status {visit.status}")

    # Vendor-neutral adapter: simulate external bind
    coverage_id = generate_id("cov_")
    external_policy_id = generate_id("pol_")
    premium = 350  # Would come from quote object in real impl

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO coverages (coverage_id, visit_id, external_policy_id, status, premium_cents,
            coverage_limit_cents, deductible_cents, coverage_start, coverage_end, certificate_url,
            covered_events, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            coverage_id, req.visit_id, external_policy_id, CoverageStatus.active.value,
            premium, 10000, 500, visit.start_time, visit.end_time,
            "https://membra.insurance/cert/" + external_policy_id,
            "theft,damage,liability", now_iso(),
        ),
    )
    conn.commit()
    conn.close()

    update_visit_status(req.visit_id, VisitStatus.coverage_bound)
    return get_coverage(coverage_id)

def get_coverage(coverage_id: str) -> Optional[CoverageOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM coverages WHERE coverage_id = ?", (coverage_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_coverage(row)

def get_coverage_by_visit(visit_id: str) -> Optional[CoverageOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM coverages WHERE visit_id = ?", (visit_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_coverage(row)

def cancel_coverage(visit_id: str) -> Optional[CoverageOut]:
    cov = get_coverage_by_visit(visit_id)
    if not cov:
        return None
    conn = get_connection()
    conn.execute(
        "UPDATE coverages SET status = ? WHERE coverage_id = ?",
        (CoverageStatus.cancelled.value, cov.coverage_id),
    )
    conn.commit()
    conn.close()
    return get_coverage(cov.coverage_id)

def _row_to_coverage(row: dict) -> CoverageOut:
    return CoverageOut(
        coverage_id=row["coverage_id"],
        visit_id=row["visit_id"],
        external_policy_id=row["external_policy_id"],
        status=CoverageStatus(row["status"]),
        premium_cents=row["premium_cents"],
        coverage_limit_cents=row["coverage_limit_cents"],
        deductible_cents=row["deductible_cents"],
        coverage_start=row["coverage_start"],
        coverage_end=row["coverage_end"],
        certificate_url=row["certificate_url"],
        covered_events=row["covered_events"].split(",") if row["covered_events"] else [],
        created_at=row["created_at"],
    )
