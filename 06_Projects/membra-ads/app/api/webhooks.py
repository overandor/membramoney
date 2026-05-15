from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import MediaKit, KitStatus, Payment, PaymentStatus
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(tags=["webhooks"])

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    # In production: verify signature with stripe_webhook_secret
    import json
    try:
        event = json.loads(payload)
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "payment_intent.succeeded":
        intent_id = data.get("id")
        payment = db.query(Payment).filter(Payment.stripe_payment_intent_id == intent_id).first()
        if payment:
            payment.status = PaymentStatus.captured.value
            db.commit()
    elif event_type == "transfer.paid":
        transfer_id = data.get("id")
        from app.db.models import Payout, PayoutStatus
        payout = db.query(Payout).filter(Payout.stripe_transfer_id == transfer_id).first()
        if payout:
            payout.status = PayoutStatus.released.value
            from datetime import datetime
            payout.released_at = datetime.utcnow()
            db.commit()

    return {"status": "ok"}

@router.post("/webhooks/printful")
async def printful_webhook(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    order_id = data.get("order", {}).get("id")
    status = data.get("type", "")
    kit = db.query(MediaKit).filter(MediaKit.vendor_order_id == str(order_id)).first()
    if kit:
        if "shipment" in status.lower():
            kit.status = KitStatus.shipped.value
            kit.shipping_tracking = data.get("shipment", {}).get("tracking_number")
        elif "fulfilled" in status.lower() or "completed" in status.lower():
            kit.status = KitStatus.shipped.value
        db.commit()
    return {"status": "ok"}

@router.post("/webhooks/printify")
async def printify_webhook(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    order_id = data.get("order_id")
    status = data.get("status")
    kit = db.query(MediaKit).filter(MediaKit.vendor_order_id == str(order_id)).first()
    if kit:
        if status in ("shipped", "in_transit"):
            kit.status = KitStatus.shipped.value
            kit.shipping_tracking = data.get("tracking_number")
        db.commit()
    return {"status": "ok"}

@router.post("/webhooks/gelato")
async def gelato_webhook(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    order_id = data.get("orderId")
    status = data.get("status")
    kit = db.query(MediaKit).filter(MediaKit.vendor_order_id == str(order_id)).first()
    if kit:
        if status in ("shipped", "fulfilled"):
            kit.status = KitStatus.shipped.value
        db.commit()
    return {"status": "ok"}

@router.post("/webhooks/nfc-vendor")
async def nfc_vendor_webhook(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    # Generic NFC vendor webhook for batch completion
    batch_id = data.get("batch_id")
    return {"status": "ok", "batch_id": batch_id}
