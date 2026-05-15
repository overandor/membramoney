from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.db.models import ProofEvent, ScanEvent, TapEvent, AcceptedPlacement, Payout, PayoutStatus, QRTag, NFCTag

router = APIRouter(tags=["proof"])

class ProofPhoto(BaseModel):
    placement_id: str
    photo_url: str
    latitude: float | None = None
    longitude: float | None = None

class ProofLocation(BaseModel):
    placement_id: str
    latitude: float
    longitude: float

class ProofQRScan(BaseModel):
    qr_id: str
    ip_address: str | None = None
    user_agent: str | None = None
    latitude: float | None = None
    longitude: float | None = None

class ProofNFCTap(BaseModel):
    nfc_id: str
    ip_address: str | None = None
    user_agent: str | None = None
    latitude: float | None = None
    longitude: float | None = None

class ProofReview(BaseModel):
    placement_id: str
    verified: bool
    reviewer_notes: str = ""

@router.post("/proof/photo")
def submit_photo(data: ProofPhoto, db: Session = Depends(get_db)):
    placement = db.query(AcceptedPlacement).filter(AcceptedPlacement.placement_id == data.placement_id).first()
    if not placement:
        raise HTTPException(404, "Placement not found")
    proof = ProofEvent(
        placement_id=data.placement_id,
        campaign_id=placement.campaign_id,
        owner_id=placement.owner_id,
        proof_type="photo",
        photo_url=data.photo_url,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(proof)
    db.commit()
    return {"proof_id": proof.proof_id, "status": "submitted"}

@router.post("/proof/location")
def submit_location(data: ProofLocation, db: Session = Depends(get_db)):
    placement = db.query(AcceptedPlacement).filter(AcceptedPlacement.placement_id == data.placement_id).first()
    if not placement:
        raise HTTPException(404, "Placement not found")
    proof = ProofEvent(
        placement_id=data.placement_id,
        campaign_id=placement.campaign_id,
        owner_id=placement.owner_id,
        proof_type="location",
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(proof)
    db.commit()
    return {"proof_id": proof.proof_id, "status": "submitted"}

@router.post("/proof/qr-scan")
def submit_qr_scan(data: ProofQRScan, db: Session = Depends(get_db)):
    qr = db.query(QRTag).filter(QRTag.qr_id == data.qr_id).first()
    if not qr or not qr.is_active:
        raise HTTPException(404, "QR code not found or inactive")
    scan = ScanEvent(
        qr_id=data.qr_id,
        campaign_id=qr.kit_id,
        ip_address=data.ip_address,
        user_agent=data.user_agent,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(scan)
    qr.scan_count = (qr.scan_count or 0) + 1
    db.commit()
    return {"scan_id": scan.scan_id, "qr_id": data.qr_id}

@router.post("/proof/nfc-tap")
def submit_nfc_tap(data: ProofNFCTap, db: Session = Depends(get_db)):
    nfc = db.query(NFCTag).filter(NFCTag.nfc_id == data.nfc_id).first()
    if not nfc or not nfc.is_active:
        raise HTTPException(404, "NFC tag not found or inactive")
    # Track tap as a scan event too
    tap = ScanEvent(
        nfc_id=data.nfc_id,
        campaign_id=nfc.kit_id,
        ip_address=data.ip_address,
        user_agent=data.user_agent,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(tap)
    nfc.tap_count = (nfc.tap_count or 0) + 1
    db.commit()
    return {"tap_id": tap.scan_id, "nfc_id": data.nfc_id}

@router.post("/proof/review")
def review_proof(data: ProofReview, db: Session = Depends(get_db)):
    proofs = db.query(ProofEvent).filter(
        ProofEvent.placement_id == data.placement_id,
        ProofEvent.verified == False
    ).all()
    for proof in proofs:
        proof.verified = data.verified
        proof.reviewer_notes = data.reviewer_notes

    placement = db.query(AcceptedPlacement).filter(AcceptedPlacement.placement_id == data.placement_id).first()
    if placement and data.verified:
        # Mark any pending payouts as eligible
        payouts = db.query(Payout).filter(
            Payout.placement_id == data.placement_id,
            Payout.status == PayoutStatus.pending.value
        ).all()
        for p in payouts:
            p.status = PayoutStatus.eligible.value
            p.proof_verified = True

    db.commit()
    return {"placement_id": data.placement_id, "verified": data.verified, "proofs_reviewed": len(proofs)}

@router.get("/proof-reports/{campaign_id}")
def proof_report(campaign_id: str, db: Session = Depends(get_db)):
    from sqlalchemy import func
    proofs = db.query(ProofEvent).filter(ProofEvent.campaign_id == campaign_id).all()
    scans = db.query(ScanEvent).filter(ScanEvent.campaign_id == campaign_id).count()
    verified_count = db.query(ProofEvent).filter(
        ProofEvent.campaign_id == campaign_id,
        ProofEvent.verified == True
    ).count()
    return {
        "campaign_id": campaign_id,
        "total_proofs": len(proofs),
        "verified_proofs": verified_count,
        "total_scans": scans,
        "proofs": [{"proof_id": p.proof_id, "type": p.proof_type, "verified": p.verified} for p in proofs]
    }
