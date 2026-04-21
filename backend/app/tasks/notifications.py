"""Celery tasks: push notifications and expiry checks."""
from app.worker import celery_app


@celery_app.task(name="app.tasks.notifications.check_expiring_containers")
def check_expiring_containers() -> dict:
    """Hourly job: find containers expiring in ≤ 2 days and create prep tasks."""
    # TODO: call StorageService.get_expiring_all(); create PrepTask per container
    return {"status": "ok"}
