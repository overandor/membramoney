from src.models.schemas import RiskDecision, ReservationOut
from src.models.enums import VisitStatus, IdentityLevel
from src.services.identity import get_user
from src.core.exceptions import RiskDeniedError

def evaluate_risk(visit: ReservationOut) -> RiskDecision:
    """Stub risk engine. Production uses external signals, history, fraud checks."""
    guest = get_user(visit.guest_id)
    if not guest:
        return RiskDecision(visit_id=visit.visit_id, approved=False, reason="Guest not found", risk_score=1.0)
    if guest.blocked:
        return RiskDecision(visit_id=visit.visit_id, approved=False, reason="Blocked user", risk_score=1.0)
    if guest.identity_level == IdentityLevel.unverified:
        return RiskDecision(visit_id=visit.visit_id, approved=False, reason="Identity not verified", risk_score=0.8)

    # Simulate risk scoring
    score = 0.1  # Base low risk
    if guest.identity_level == IdentityLevel.email_verified:
        score += 0.15
    if guest.identity_level == IdentityLevel.id_verified:
        score += 0.05
    if guest.trust_score < 0.6:
        score += 0.3

    approved = score < 0.5
    return RiskDecision(
        visit_id=visit.visit_id,
        approved=approved,
        reason="Risk check passed" if approved else "Risk threshold exceeded",
        risk_score=round(score, 2),
    )
