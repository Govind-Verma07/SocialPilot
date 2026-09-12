"""
app/worker/celery_app.py
------------------------
Celery application instance configuration for SocialPilot background processing.
Configures broker, result backend, serialization, task discovery, and periodic beat schedule.
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "socialpilot_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Configure Celery Beat periodic schedule
    beat_schedule={
        "check-due-scheduled-posts-every-minute": {
            "task": "app.worker.tasks.check_and_publish_due_posts",
            "schedule": 60.0,  # Run every 60 seconds
        },
    },
)
