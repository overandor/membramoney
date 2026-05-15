from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Literal
from datetime import datetime
from app.db.database import get_db
from app.db.models import Campaign, CampaignCreative, AcceptedPlacement, AdAsset, Owner, CampaignStatus

router = APIRouter(tags=["campaigns"])

class CampaignCreate(BaseModel):
    advertiser_id: str
    title: str
    description: str = ""
    target_city: str = ""
    target_neighborhoods: list[str] = []
    asset_types: list[str] = []
    budget_cents: int
    daily_budget_cents: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    destination_url: str = ""
    payout_rules: dict = {}

class CampaignOut(BaseModel):
    campaign_id: str
    advertiser_id: str
    title: str
    description: str | None
    target_city: str | None
    target_neighborhoods: list[str]
    asset_types: list[str]
    budget_cents: int
    daily_budget_cents: int | None
    start_date: datetime | None
    end_date: datetime | None
    status: str
    creative_url: str | None
    approved_creative_url: str | None
    destination_url: str | None
    payout_rules: dict
    class Config:
        from_attributes = True

class CreativeSubmit(BaseModel):
    asset_type: str
    mockup_url: str
    print_ready_url: str

class CreativeAction(BaseModel):
    approved: bool
    reviewer_notes: str = ""

class CampaignFund(BaseModel):
    stripe_payment_intent_id: str | None = None

class CampaignAccept(BaseModel):
    owner_id: str
    asset_id: str
    daily_rate_cents: int

@router.post("/campaigns", response_model=CampaignOut)
def create_campaign(data: CampaignCreate, db: Session = Depends(get_db)):
    payload = data.model_dump()
    if data.start_date:
        payload["start_date"] = datetime.fromisoformat(data.start_date)
    if data.end_date:
        payload["end_date"] = datetime.fromisoformat(data.end_date)
    campaign = Campaign(**payload)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign

@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Campaign)
    if status:
        q = q.filter(Campaign.status == status)
    return q.order_by(Campaign.created_at.desc()).all()

@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c

@router.post("/campaigns/{campaign_id}/submit-creative")
def submit_creative(campaign_id: str, data: CreativeSubmit, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campaign not found")
    creative = CampaignCreative(
        campaign_id=campaign_id,
        asset_type=data.asset_type,
        mockup_url=data.mockup_url,
        print_ready_url=data.print_ready_url,
    )
    db.add(creative)
    c.status = CampaignStatus.creative_submitted.value
    db.commit()
    return {"creative_id": creative.creative_id, "status": c.status}

@router.post("/campaigns/{campaign_id}/approve-creative")
def approve_creative(campaign_id: str, data: CreativeAction, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campaign not found")
    if data.approved:
        c.status = CampaignStatus.creative_approved.value
        c.approved_creative_url = c.creative_url
    else:
        c.status = CampaignStatus.draft.value
    db.commit()
    return {"campaign_id": campaign_id, "status": c.status, "approved": data.approved}

@router.post("/campaigns/{campaign_id}/fund")
def fund_campaign(campaign_id: str, data: CampaignFund, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campaign not found")
    c.status = CampaignStatus.funded.value
    db.commit()
    return {"campaign_id": campaign_id, "status": c.status}

@router.post("/campaigns/{campaign_id}/launch")
def launch_campaign(campaign_id: str, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campaign not found")
    if c.status not in (CampaignStatus.funded.value, CampaignStatus.creative_approved.value):
        raise HTTPException(400, "Campaign must be funded before launch")
    c.status = CampaignStatus.launched.value
    db.commit()
    return {"campaign_id": campaign_id, "status": c.status}

@router.get("/campaigns/available")
def available_campaigns(city: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Campaign).filter(Campaign.status == CampaignStatus.funded.value)
    if city:
        q = q.filter(Campaign.target_city.ilike(f"%{city}%"))
    return q.all()

@router.post("/campaigns/{campaign_id}/accept")
def accept_campaign(campaign_id: str, data: CampaignAccept, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campaign not found")
    placement = AcceptedPlacement(
        campaign_id=campaign_id,
        asset_id=data.asset_id,
        owner_id=data.owner_id,
        daily_rate_cents=data.daily_rate_cents,
    )
    db.add(placement)
    db.commit()
    return {"placement_id": placement.placement_id, "status": placement.status}

@router.post("/campaigns/{campaign_id}/decline")
def decline_campaign(campaign_id: str, owner_id: str, db: Session = Depends(get_db)):
    return {"message": "Campaign declined", "campaign_id": campaign_id, "owner_id": owner_id}
