from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Owner

router = APIRouter(tags=["owners"])

class OwnerCreate(BaseModel):
    email: str
    name: str
    phone: str = ""
    city: str = ""
    neighborhood: str = ""

class OwnerOut(BaseModel):
    owner_id: str
    email: str
    name: str
    phone: str
    identity_verified: bool
    city: str
    neighborhood: str
    stripe_connect_account_id: str | None
    class Config:
        from_attributes = True

@router.post("/owners", response_model=OwnerOut)
def create_owner(data: OwnerCreate, db: Session = Depends(get_db)):
    existing = db.query(Owner).filter(Owner.email == data.email).first()
    if existing:
        raise HTTPException(400, "Owner with this email already exists")
    owner = Owner(**data.model_dump())
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner

@router.get("/owners/me")
def get_me():
    # In production: decode JWT, return current owner
    return {"message": "Use /owners/{owner_id}"}

@router.get("/owners/{owner_id}", response_model=OwnerOut)
def get_owner(owner_id: str, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.owner_id == owner_id).first()
    if not owner:
        raise HTTPException(404, "Owner not found")
    return owner
