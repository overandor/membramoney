from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Advertiser

router = APIRouter(tags=["advertisers"])

class AdvertiserCreate(BaseModel):
    email: str
    name: str
    company: str = ""

class AdvertiserOut(BaseModel):
    advertiser_id: str
    email: str
    name: str
    company: str
    stripe_customer_id: str | None
    class Config:
        from_attributes = True

@router.post("/advertisers", response_model=AdvertiserOut)
def create_advertiser(data: AdvertiserCreate, db: Session = Depends(get_db)):
    existing = db.query(Advertiser).filter(Advertiser.email == data.email).first()
    if existing:
        raise HTTPException(400, "Advertiser with this email already exists")
    adv = Advertiser(**data.model_dump())
    db.add(adv)
    db.commit()
    db.refresh(adv)
    return adv

@router.get("/advertisers/me")
def get_me():
    return {"message": "Use /advertisers/{advertiser_id}"}

@router.get("/advertisers/{advertiser_id}", response_model=AdvertiserOut)
def get_advertiser(advertiser_id: str, db: Session = Depends(get_db)):
    adv = db.query(Advertiser).filter(Advertiser.advertiser_id == advertiser_id).first()
    if not adv:
        raise HTTPException(404, "Advertiser not found")
    return adv
