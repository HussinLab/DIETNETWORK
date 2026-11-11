"""
Celery client used by the API process to *enqueue* jobs. The actual task
implementation (VCF/bgen -> PLINK -> infer.sh -> parse) lives in the
worker/ service so the API image stays free of the (large) DietNetwork /
PyTorch dependency stack -- it only needs to know the task name and be
able to talk to Redis.
"""
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("dietnet_api", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = "inference"
