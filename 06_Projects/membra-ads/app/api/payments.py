from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Payment, Payout, Campaign, Owner, AcceptedPlacement, PaymentStatus, PayoutStatus
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(tags=["payments"])

class PaymentAuthorize(BaseModel):
    campaign_id: str
    amount_cents: int
    stripe_payment_intent_id: str | None = None

class PaymentCapture(BaseModel):
    payment_id: str
    stripe_payment_intent_id: str | None = None

class PayoutRelease(BaseModel):
    payout_id: str
    stripe_transfer_id: str | None = None

@router.post("/payments/authorize")
def authorize_payment(data: PaymentAuthorize, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.campaign_id == data.campaign_id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    payment = Payment(
        campaign_id=data.campaign_id,
        advertiser_id=campaign.advertiser_id,
        amount_cents=data.amount_cents,
        stripe_payment_intent_id=data.stripe_payment_intent_id,
        status=PaymentStatus.authorized.value,
    )
    db.add(payment)
    db.commit()
    return {"payment_id": payment.payment_id, "status": payment.status, "amount_cents": data.amount_cents}

@router.post("/payments/capture")
def capture_payment(data: PaymentCapture, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.payment_id == data.payment_id).first()
    if not payment:
        raise HTTPException(404, "Payment not found")
    payment.status = PaymentStatus.captured.value
    if data.stripe_payment_intent_id:
        payment.stripe_payment_intent_id = data.stripe_payment_intent_id
    db.commit()
    return {"payment_id": payment.payment_id, "status": payment.status}

@router.post("/payouts/release")
def release_payout(data: PayoutRelease, db: Session = Depends(get_db)):
    payout = db.query(Payout).filter(Payout.payout_id == data.payout_id).first()
    if not payout:
        raise HTTPException(404, "Payout not found")
    if not payout.proof_verified:
        raise HTTPException(400, "Proof must be verified before payout release")
    payout.status = PayoutStatus.released.value
    if data.stripe_transfer_id:
        payout.stripe_transfer_id = data.stripe_transfer_id
    from datetime import datetime
    payout.released_at = datetime.utcnow()
    db.commit()
    return {"payout_id": payout.payout_id, "status": payout.status, "amount_cents": payout.amount_cents}

@router.post("/payouts/create-transfer")
def create_transfer(placement_id: str, amount_cents: int, db: Session = Depends(get_db)):
    placement = db.query(AcceptedPlacement).filter(AcceptedPlacement.placement_id == placement_id).first()
    if not placement:
        raise HTTPException(404, "Placement not found")
    payout = Payout(
        owner_id=placement.owner_id,
        placement_id=placement_id,
        campaign_id=placement.campaign_id,
        amount_cents=amount_cents,
        status=PayoutStatus.pending.value,
    )
    db.add(payout)
    db.commit()
    return {"payout_id": payout.payout_id, "status": payout.status, "amount_cents": amount_cents}

@router.get("/payouts/{payout_id}")
def get_payout(payout_id: str, db: Session = Depends(get_db)):
    payout = db.query(Payout).filter(Payout.payout_id == payout_id).first()
    if not payout:
        raise HTTPException(404, "Payout not found")
    return payout
