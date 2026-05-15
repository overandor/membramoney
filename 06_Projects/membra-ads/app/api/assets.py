from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Literal
from app.db.database import get_db
from app.db.models import AdAsset, WindowAsset, VehicleAsset, WearableAsset

router = APIRouter(tags=["ad-assets"])

class AdAssetCreate(BaseModel):
    owner_id: str
    asset_type: Literal["window", "vehicle", "wearable"]
    title: str
    description: str = ""
    address: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    city: str = ""
    neighborhood: str = ""
    daily_rate_cents: int = 500
    photos: list[str] = []

class AdAssetOut(BaseModel):
    asset_id: str
    owner_id: str
    asset_type: str
    title: str
    description: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    city: str | None
    neighborhood: str | None
    daily_rate_cents: int
    photos: list[str]
    is_active: bool
    verified: bool
    class Config:
        from_attributes = True

class VerifyAsset(BaseModel):
    verified: bool = True

@router.post("/ad-assets", response_model=AdAssetOut)
def create_asset(data: AdAssetCreate, db: Session = Depends(get_db)):
    asset = AdAsset(**data.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

@router.get("/ad-assets", response_model=list[AdAssetOut])
def list_assets(city: str | None = None, asset_type: str | None = None, db: Session = Depends(get_db)):
    q = db.query(AdAsset).filter(AdAsset.is_active == True)
    if city:
        q = q.filter(AdAsset.city.ilike(f"%{city}%"))
    if asset_type:
        q = q.filter(AdAsset.asset_type == asset_type)
    return q.all()

@router.get("/ad-assets/{asset_id}", response_model=AdAssetOut)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(AdAsset).filter(AdAsset.asset_id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset

@router.patch("/ad-assets/{asset_id}", response_model=AdAssetOut)
def update_asset(asset_id: str, data: AdAssetCreate, db: Session = Depends(get_db)):
    asset = db.query(AdAsset).filter(AdAsset.asset_id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    for k, v in data.model_dump().items():
        setattr(asset, k, v)
    db.commit()
    db.refresh(asset)
    return asset

@router.post("/ad-assets/{asset_id}/verify", response_model=AdAssetOut)
def verify_asset(asset_id: str, data: VerifyAsset, db: Session = Depends(get_db)):
    asset = db.query(AdAsset).filter(AdAsset.asset_id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.verified = data.verified
    db.commit()
    db.refresh(asset)
    return asset

@router.post("/windows")
def create_window(data: dict, db: Session = Depends(get_db)):
    w = WindowAsset(**data)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w

@router.post("/vehicles")
def create_vehicle(data: dict, db: Session = Depends(get_db)):
    v = VehicleAsset(**data)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v

@router.post("/wearables")
def create_wearable(data: dict, db: Session = Depends(get_db)):
    w = WearableAsset(**data)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w
