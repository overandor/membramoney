from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.db.models import Campaign, ScanEvent, ProofEvent, AcceptedPlacement, Payout

router = APIRouter(tags=["analytics"])

@router.get("/analytics/campaign/{campaign_id}")
def campaign_analytics(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    total_scans = db.query(ScanEvent).filter(ScanEvent.campaign_id == campaign_id).count()
    unique_qr_scans = db.query(ScanEvent.qr_id).filter(
        ScanEvent.campaign_id == campaign_id,
        ScanEvent.qr_id != None
    ).distinct().count()
    unique_nfc_taps = db.query(ScanEvent.nfc_id).filter(
        ScanEvent.campaign_id == campaign_id,
        ScanEvent.nfc_id != None
    ).distinct().count()
    verified_proofs = db.query(ProofEvent).filter(
        ProofEvent.campaign_id == campaign_id,
        ProofEvent.verified == True
    ).count()
    total_payouts = db.query(Payout).filter(Payout.campaign_id == campaign_id).count()
    total_payout_cents = db.query(func.sum(Payout.amount_cents)).filter(
        Payout.campaign_id == campaign_id,
        Payout.status == "released"
    ).scalar() or 0
    placements = db.query(AcceptedPlacement).filter(AcceptedPlacement.campaign_id == campaign_id).count()

    return {
        "campaign_id": campaign_id,
        "title": campaign.title,
        "status": campaign.status,
        "total_scans": total_scans,
        "unique_qr_scans": unique_qr_scans,
        "unique_nfc_taps": unique_nfc_taps,
        "verified_proofs": verified_proofs,
        "total_payouts": total_payouts,
        "total_payout_cents": total_payout_cents,
        "active_placements": placements,
        "budget_cents": campaign.budget_cents,
        "daily_budget_cents": campaign.daily_budget_cents,
    }

@router.get("/analytics/owner/{owner_id}")
def owner_analytics(owner_id: str, db: Session = Depends(get_db)):
    placements = db.query(AcceptedPlacement).filter(AcceptedPlacement.owner_id == owner_id).all()
    total_earnings = db.query(func.sum(Payout.amount_cents)).filter(
        Payout.owner_id == owner_id,
        Payout.status == "released"
    ).scalar() or 0
    pending_earnings = db.query(func.sum(Payout.amount_cents)).filter(
        Payout.owner_id == owner_id,
        Payout.status == "eligible"
    ).scalar() or 0
    active_campaigns = len([p for p in placements if p.status == "active"])

    return {
        "owner_id": owner_id,
        "total_earnings_cents": total_earnings,
        "pending_earnings_cents": pending_earnings,
        "active_placements": active_campaigns,
        "total_placements": len(placements),
    }
