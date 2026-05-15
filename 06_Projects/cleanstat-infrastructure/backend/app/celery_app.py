"""
CleanStat Infrastructure - Celery Application
Background task processing configuration
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "cleanstat",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.observation_tasks", "app.tasks.verification_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
)
