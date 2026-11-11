from celery import Celery
from celery.schedules import crontab

from worker.config import settings

celery_app = Celery("dietnet_worker", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = "inference"
celery_app.conf.task_routes = {
    "worker.tasks.run_inference_job": {"queue": "inference"},
    "worker.cleanup.cleanup_expired_jobs": {"queue": "maintenance"},
}

# Celery Beat schedule: daily retention sweep (30-day auto-deletion).
# DB `created_at` is the source of truth, not filesystem mtime (see cleanup.py).
celery_app.conf.beat_schedule = {
    "daily-retention-cleanup": {
        "task": "worker.cleanup.cleanup_expired_jobs",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC daily, low-traffic window
        "options": {"queue": "maintenance"},
    },
}
celery_app.conf.timezone = "UTC"

# Ensure task modules are registered when the worker starts.
celery_app.autodiscover_tasks(["worker"], related_name="tasks")
celery_app.autodiscover_tasks(["worker"], related_name="cleanup")
