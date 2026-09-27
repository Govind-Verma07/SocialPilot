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
    broker_connection_retry_on_startup=True,
    # Configure Celery Beat periodic schedule
    beat_schedule={
        "check-due-scheduled-posts-periodically": {
            "task": "app.worker.tasks.check_and_publish_due_posts",
            "schedule": 15.0,  # Scan for due scheduled posts every 15 seconds
        },
        "process-queued-and-retry-jobs": {
            "task": "app.worker.tasks.process_queued_and_retry_jobs",
            "schedule": 30.0,  # Scan for retrying jobs with elapsed backoff every 30 seconds
        },
        "check-and-send-scheduled-reminders": {
            "task": "app.worker.tasks.check_and_send_scheduled_reminders",
            "schedule": 60.0,  # Scan for upcoming scheduled post reminders every minute
        },
        "sync-social-analytics-periodically": {
            "task": "app.worker.tasks.sync_social_analytics_task",
            "schedule": 300.0,  # Sync real platform analytics every 5 minutes
        },
    },
)

import sys
if sys.platform == "win32":
    celery_app.conf.worker_pool = "solo"
