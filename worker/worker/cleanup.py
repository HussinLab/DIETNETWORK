"""
Scheduled 30-day retention sweep (Celery beat task; see celery_app.py for
the daily schedule). A systemd-timer equivalent that calls this same task
via `celery call` is provided in ops/scripts/cleanup_timer/ for operators
who prefer not to run Celery beat.

The DB `created_at` timestamp is the source of truth for age, never
filesystem mtime (mtimes can be reset by copies/backups).
"""
import logging
import os
import shutil
from datetime import timedelta

from worker.celery_app import celery_app
from worker.config import settings
from worker.db import Job, get_session, utcnow

logger = logging.getLogger("worker.cleanup")


def _delete_path(path: str | None) -> None:
    if not path or not os.path.exists(path):
        return
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    else:
        os.remove(path)


@celery_app.task(name="worker.cleanup.cleanup_expired_jobs")
def cleanup_expired_jobs() -> int:
    cutoff = utcnow() - timedelta(days=settings.retention_days)
    purged = 0

    session = get_session()
    try:
        expired = (
            session.query(Job)
            .filter(Job.created_at < cutoff, Job.purged_at.is_(None))
            .all()
        )
        for job in expired:
            logger.info("Purging job %s (created_at=%s, cutoff=%s)", job.id, job.created_at, cutoff)
            _delete_path(job.raw_path)
            _delete_path(job.results_path and os.path.dirname(job.results_path))

            job.raw_path = None
            job.results_path = None
            job.predictions = None  # derived results also purged at 30 days, not just raw genotypes
            job.purged_at = utcnow()
            purged += 1

        session.commit()
    finally:
        session.close()

    logger.info("Retention sweep complete: purged %d job(s)", purged)
    return purged
