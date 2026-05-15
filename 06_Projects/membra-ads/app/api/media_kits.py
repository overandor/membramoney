from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import MediaKit, Campaign, AcceptedPlacement, QRTag, NFCTag, KitStatus
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(tags=["media-kits"])

class MediaKitCreate(BaseModel):
    campaign_id: str
    placement_id: str
    asset_type: str

class MediaKitOut(BaseModel):
    kit_id: str
    campaign_id: str
    placement_id: str
    asset_type: str
    status: str
    qr_tag_id: str | None
    nfc_tag_id: str | None
    tracking_url: str | None
    vendor: str | None
    vendor_order_id: str | None
    shipping_tracking: str | None
    class Config:
        from_attributes = True

class OrderKit(BaseModel):
    vendor: str  # printful, printify, gelato, manual
    shipping_address: dict

class ConfirmReceipt(BaseModel):
    received: bool = True

@router.post("/media-kits", response_model=MediaKitOut)
def create_media_kit(data: MediaKitCreate, db: Session = Depends(get_db)):
    kit = MediaKit(**data.model_dump())
    db.add(kit)
    db.commit()
    db.refresh(kit)
    return kit

@router.get("/media-kits/{kit_id}", response_model=MediaKitOut)
def get_media_kit(kit_id: str, db: Session = Depends(get_db)):
    kit = db.query(MediaKit).filter(MediaKit.kit_id == kit_id).first()
    if not kit:
        raise HTTPException(404, "Media kit not found")
    return kit

@router.post("/media-kits/{kit_id}/generate-qr")
def generate_qr(kit_id: str, db: Session = Depends(get_db)):
    kit = db.query(MediaKit).filter(MediaKit.kit_id == kit_id).first()
    if not kit:
        raise HTTPException(404, "Media kit not found")
    import uuid
    qr_id = f"qr_{uuid.uuid4().hex[:16]}"
    tracking_url = f"{settings.qr_base_url}/{qr_id}"
    qr = QRTag(
        qr_id=qr_id,
        kit_id=kit_id,
        tracking_url=tracking_url,
    )
    db.add(qr)
    kit.qr_tag_id = qr_id
    kit.tracking_url = tracking_url
    db.commit()
    return {"qr_id": qr_id, "tracking_url": tracking_url}

@router.post("/media-kits/{kit_id}/assign-nfc")
def assign_nfc(kit_id: str, uid: str | None = None, db: Session = Depends(get_db)):
    kit = db.query(MediaKit).filter(MediaKit.kit_id == kit_id).first()
    if not kit:
        raise HTTPException(404, "Media kit not found")
    import uuid
    nfc_id = f"nfc_{uuid.uuid4().hex[:16]}"
    nfc_uid = uid or f"UID_{uuid.uuid4().hex[:12].upper()}"
    nfc = NFCTag(
        nfc_id=nfc_id,
        kit_id=kit_id,
        uid=nfc_uid,
        tracking_url=f"{settings.qr_base_url}/nfc/{nfc_id}",
    )
    db.add(nfc)
    kit.nfc_tag_id = nfc_id
    db.commit()
    return {"nfc_id": nfc_id, "uid": nfc_uid}

@router.post("/media-kits/{kit_id}/order")
def order_kit(kit_id: str, data: OrderKit, db: Session = Depends(get_db)):
    kit = db.query(MediaKit).filter(MediaKit.kit_id == kit_id).first()
    if not kit:
        raise HTTPException(404, "Media kit not found")
    kit.status = KitStatus.ordered.value
    kit.vendor = data.vendor
    db.commit()
    return {
        "kit_id": kit_id,
        "status": kit.status,
        "vendor": data.vendor,
        "message": "Order placed with vendor. Track via webhooks or manual updates."
    }

@router.post("/media-kits/{kit_id}/confirm-receipt")
def confirm_receipt(kit_id: str, data: ConfirmReceipt, db: Session = Depends(get_db)):
    kit = db.query(MediaKit).filter(MediaKit.kit_id == kit_id).first()
    if not kit:
        raise HTTPException(404, "Media kit not found")
    if data.received:
        kit.status = KitStatus.received.value
    db.commit()
    return {"kit_id": kit_id, "status": kit.status}
