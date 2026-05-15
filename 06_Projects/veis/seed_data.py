"""
Seed data script for VEIS database
Run this script to populate the database with initial data
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import Session
from app.db.base import SessionLocal, engine, Base
from app.models import Zone
from app.core.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)


def seed_zones(db: Session):
    """Seed initial zones"""
    zones_data = [
        {
            "name": "Manhattan Downtown",
            "zone_code": "MDT",
            "center_latitude": 40.7128,
            "center_longitude": -74.0060,
            "description": "Downtown Manhattan area",
            "area_sq_km": 15.0,
            "population": 500000,
            "priority_level": "high"
        },
        {
            "name": "Brooklyn Heights",
            "zone_code": "BRK",
            "center_latitude": 40.7011,
            "center_longitude": -73.9867,
            "description": "Brooklyn Heights area",
            "area_sq_km": 12.0,
            "population": 300000,
            "priority_level": "medium"
        },
        {
            "name": "Queens Central",
            "zone_code": "QNS",
            "center_latitude": 40.7282,
            "center_longitude": -73.7949,
            "description": "Central Queens area",
            "area_sq_km": 20.0,
            "population": 400000,
            "priority_level": "medium"
        },
        {
            "name": "Bronx North",
            "zone_code": "BRX",
            "center_latitude": 40.8448,
            "center_longitude": -73.8648,
            "description": "North Bronx area",
            "area_sq_km": 18.0,
            "population": 250000,
            "priority_level": "low"
        },
        {
            "name": "Staten Island",
            "zone_code": "SIL",
            "center_latitude": 40.5795,
            "center_longitude": -74.1502,
            "description": "Staten Island area",
            "area_sq_km": 25.0,
            "population": 200000,
            "priority_level": "low"
        }
    ]
    
    for zone_data in zones_data:
        # Check if zone already exists
        existing_zone = db.query(Zone).filter(
            Zone.zone_code == zone_data["zone_code"]
        ).first()
        
        if not existing_zone:
            zone = Zone(**zone_data)
            db.add(zone)
            logger.info(f"Created zone: {zone.name} ({zone.zone_code})")
        else:
            logger.info(f"Zone already exists: {existing_zone.name} ({existing_zone.zone_code})")
    
    db.commit()


def main():
    """Main seed function"""
    logger.info("Starting seed data script")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    # Create session
    db = SessionLocal()
    
    try:
        # Seed zones
        seed_zones(db)
        
        logger.info("Seed data completed successfully")
        
    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
