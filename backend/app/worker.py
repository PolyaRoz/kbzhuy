"""Celery worker entry point."""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "kbzhuy",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.plan",
        "app.tasks.cooking",
        "app.tasks.notifications",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-expiring-containers": {
            "task": "app.tasks.notifications.check_expiring_containers",
            "schedule": 3600.0,  # every hour
        },
        "generate-prep-tasks": {
            "task": "app.tasks.plan.generate_prep_tasks_for_today",
            "schedule": 86400.0,  # daily
        },
    },
)
