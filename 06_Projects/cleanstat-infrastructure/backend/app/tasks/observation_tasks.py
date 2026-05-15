"""
CleanStat Infrastructure - Observation Tasks
Celery background tasks for observation processing
"""
from app.celery_app import celery_app
from app.services.ipfs import fetch_from_ipfs
from app.services.verification_engine import analyze_image
from app.db.session import SessionLocal
from app.models.observation import Observation
from app.models.audit_log import AuditLog

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_observation(self, observation_id: str):
    """Process observation with AI detection"""
    db = SessionLocal()
    try:
        obs = db.query(Observation).filter(Observation.id == observation_id).first()
        if not obs:
            return

        # Download image from IPFS
        image_data = fetch_from_ipfs(obs.image_cid)

        # Run AI model
        result = analyze_image(image_data)

        obs.status = "completed"
        obs.fill_level = result["fill_level"]
        obs.confidence = result["confidence"]
        db.commit()

        AuditLog(
            event_type="observation.processed",
            organization_id=obs.organization_id,
            details={"observation_id": obs.id, "result": result}
        )
        db.add(AuditLog)
        db.commit()
    except Exception as e:
        db.rollback()
        self.retry(exc=e)
    finally:
        db.close()
