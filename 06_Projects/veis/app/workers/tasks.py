from celery import Celery
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.models.observation import Observation, ObservationStatus
from app.services.detection_service import DetectionService
import json

settings = get_settings()
logger = get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "veis",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)

detection_service = DetectionService()


@celery_app.task(bind=True, max_retries=3)
def process_observation_task(self, observation_id: int):
    """
    Process an observation asynchronously using AI detection
    """
    import asyncio
    db = SessionLocal()
    
    try:
        logger.info("Processing observation", observation_id=observation_id)
        
        # Get observation
        observation = db.query(Observation).filter(
            Observation.id == observation_id
        ).first()
        
        if not observation:
            logger.error("Observation not found", observation_id=observation_id)
            return {"error": "Observation not found"}
        
        # Update status to processing
        observation.status = ObservationStatus.PROCESSING
        db.commit()
        
        # Run AI detection (run async function in sync context)
        detection_result = asyncio.run(detection_service.detect_waste(observation.image_url))
        
        # Update observation with results
        observation.waste_type = detection_result["waste_type"]
        observation.estimated_mass_g = detection_result["estimated_mass_g"]
        observation.confidence_score = detection_result["confidence_score"]
        observation.detection_result = json.dumps(detection_result)
        observation.status = ObservationStatus.COMPLETED
        
        db.commit()
        
        logger.info(
            "Observation processed successfully",
            observation_id=observation_id,
            waste_type=detection_result["waste_type"]
        )
        
        return {
            "observation_id": observation_id,
            "status": "completed",
            "waste_type": detection_result["waste_type"],
            "estimated_mass_g": detection_result["estimated_mass_g"],
            "confidence_score": detection_result["confidence_score"]
        }
        
    except Exception as e:
        logger.error(
            "Error processing observation",
            observation_id=observation_id,
            error=str(e)
        )
        
        # Update status to failed
        if observation:
            observation.status = ObservationStatus.FAILED
            observation.error_message = str(e)
            db.commit()
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
    finally:
        db.close()


@celery_app.task
def cleanup_old_observations(days: int = 30):
    """
    Cleanup old observations (background maintenance task)
    """
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        deleted = db.query(Observation).filter(
            Observation.created_at < cutoff_date,
            Observation.status == ObservationStatus.COMPLETED
        ).delete()
        
        db.commit()
        
        logger.info(
            "Old observations cleaned up",
            deleted_count=deleted,
            days=days
        )
        
        return {"deleted_count": deleted}
        
    finally:
        db.close()
