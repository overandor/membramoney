import hmac
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
from src.core.config import settings
from src.core.exceptions import AccessDeniedError, CoverageNotActiveError
from src.models.enums import VisitStatus, PaymentStatus, CoverageStatus
from src.models.schemas import ReservationOut, PaymentOut, CoverageOut, RiskDecision, QRVerifyOut, CheckInOutResult
from src.services.reservations import get_visit, update_visit_status
from src.services.payments import get_payment_by_visit
from src.services.insurance import get_coverage_by_visit
from src.services.risk import evaluate_risk

def access_ready(visit: ReservationOut, payment: PaymentOut, coverage: CoverageOut, risk: RiskDecision) -> bool:
    """
    The whole company right here.
    No verified identity → no reservation
    No risk approval → no quote/bind
    No payment authorization → no insurance bind
    No active bound coverage → no QR access
    No backend QR verification → no entry
    """
    if visit.status not in (
        VisitStatus.coverage_bound,
        VisitStatus.access_issued,
        VisitStatus.checked_in,
        VisitStatus.checked_out,
        VisitStatus.completed,
    ):
        return False
    if not risk.approved:
        return False
    if payment.status != PaymentStatus.authorized:
        return False
    if coverage.status != CoverageStatus.active:
        return False
    if not coverage.external_policy_id:
        return False
    try:
        cov_start = coverage.coverage_start if isinstance(coverage.coverage_start, datetime) else datetime.fromisoformat(coverage.coverage_start)
        cov_end = coverage.coverage_end if isinstance(coverage.coverage_end, datetime) else datetime.fromisoformat(coverage.coverage_end)
        visit_start = visit.start_time if isinstance(visit.start_time, datetime) else datetime.fromisoformat(visit.start_time)
        visit_end = visit.end_time if isinstance(visit.end_time, datetime) else datetime.fromisoformat(visit.end_time)
    except (TypeError, ValueError):
        return False
    return cov_start <= visit_start and cov_end >= visit_end

def _assert_access_ready(visit_id: str) -> tuple[ReservationOut, PaymentOut, CoverageOut, RiskDecision]:
    visit = get_visit(visit_id)
    if not visit:
        raise AccessDeniedError("Visit not found")
    payment = get_payment_by_visit(visit_id)
    if not payment:
        raise AccessDeniedError("Payment not found")
    coverage = get_coverage_by_visit(visit_id)
    if not coverage:
        raise CoverageNotActiveError("No coverage found")
    # Reconstruct risk decision from stored fields
    risk = RiskDecision(
        visit_id=visit_id,
        approved=bool(getattr(visit, 'risk_approved', True)),
        reason=getattr(visit, 'risk_reason', None),
        risk_score=getattr(visit, 'risk_score', 0.0) or 0.0,
    )
    if not access_ready(visit, payment, coverage, risk):
        raise AccessDeniedError(
            "Access blocked. Payment, risk, and active insurance are required."
        )
    return visit, payment, coverage, risk

def _iso(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)

def issue_qr(visit_id: str) -> str:
    visit, payment, coverage, risk = _assert_access_ready(visit_id)
    payload = {
        "v": visit_id,
        "a": visit.asset_id,
        "g": visit.guest_id,
        "s": _iso(visit.start_time),
        "e": _iso(visit.end_time),
        "p": coverage.external_policy_id,
    }
    raw = json.dumps(payload, sort_keys=True)
    sig = hmac.new(
        settings.qr_secret.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()[:16]
    token = f"{raw}|{sig}"

    update_visit_status(visit_id, VisitStatus.access_issued, qr_token=token)
    return token

def verify_qr(qr_payload: str) -> QRVerifyOut:
    try:
        raw, sig = qr_payload.rsplit("|", 1)
        expected = hmac.new(
            settings.qr_secret.encode(), raw.encode(), hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return QRVerifyOut(valid=False, message="Invalid QR signature")

        payload = json.loads(raw)
        visit_id = payload.get("v")
        visit = get_visit(visit_id)
        if not visit:
            return QRVerifyOut(valid=False, message="Visit not found")

        # Ensure all gates pass before verifying
        payment = get_payment_by_visit(visit_id)
        coverage = get_coverage_by_visit(visit_id)
        risk = RiskDecision(
            visit_id=visit_id,
            approved=bool(getattr(visit, 'risk_approved', True)),
            reason=getattr(visit, 'risk_reason', None),
            risk_score=getattr(visit, 'risk_score', 0.0) or 0.0,
        )
        if not access_ready(visit, payment, coverage, risk):
            return QRVerifyOut(valid=False, message="Access not ready")

        return QRVerifyOut(
            valid=True,
            visit_id=visit.visit_id,
            asset_id=visit.asset_id,
            guest_id=visit.guest_id,
            status=visit.status.value,
            message="Access verified",
        )
    except Exception as e:
        return QRVerifyOut(valid=False, message=f"Verification failed: {e}")

def check_in(visit_id: str) -> CheckInOutResult:
    visit = get_visit(visit_id)
    if not visit:
        raise AccessDeniedError("Visit not found")
    if visit.status != VisitStatus.access_issued:
        raise AccessDeniedError(f"Cannot check in from status {visit.status}")
    update_visit_status(visit_id, VisitStatus.checked_in)
    return CheckInOutResult(visit_id=visit_id, status=VisitStatus.checked_in, timestamp=now_iso())

def check_out(visit_id: str) -> CheckInOutResult:
    visit = get_visit(visit_id)
    if not visit:
        raise AccessDeniedError("Visit not found")
    if visit.status != VisitStatus.checked_in:
        raise AccessDeniedError(f"Cannot check out from status {visit.status}")
    update_visit_status(visit_id, VisitStatus.checked_out)
    return CheckInOutResult(visit_id=visit_id, status=VisitStatus.checked_out, timestamp=now_iso())

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
