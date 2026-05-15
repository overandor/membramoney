from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.zone import Zone
from app.schemas.zone import ZoneCreate, ZoneResponse
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/zones", tags=["zones"])


@router.post("/", response_model=ZoneResponse)
def create_zone(zone: ZoneCreate, db: Session = Depends(get_db)):
    """Create a new zone"""
    new_zone = Zone(
        name=zone.name,
        zone_code=zone.zone_code,
        boundary_polygon=zone.boundary_polygon,
        center_latitude=zone.center_latitude,
        center_longitude=zone.center_longitude,
        description=zone.description,
        area_sq_km=zone.area_sq_km,
        population=zone.population,
        priority_level=zone.priority_level
    )
    
    db.add(new_zone)
    db.commit()
    db.refresh(new_zone)
    
    logger.info("Zone created", zone_id=new_zone.id, zone_code=zone.zone_code)
    
    return new_zone


@router.get("/{zone_id}", response_model=ZoneResponse)
def get_zone(zone_id: int, db: Session = Depends(get_db)):
    """Get a zone by ID"""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    
    return zone


@router.get("/", response_model=list[ZoneResponse])
def list_zones(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all zones with pagination"""
    zones = db.query(Zone).offset(skip).limit(limit).all()
    return zones


@router.get("/code/{zone_code}", response_model=ZoneResponse)
def get_zone_by_code(zone_code: str, db: Session = Depends(get_db)):
    """Get a zone by zone code"""
    zone = db.query(Zone).filter(Zone.zone_code == zone_code).first()
    
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    
    return zone
