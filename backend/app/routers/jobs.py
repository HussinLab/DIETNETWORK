import os
import tempfile
import zipfile

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.concurrency import acquire_download_slot, release_download_slot
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_verified_user
from app.models import Job, JobStatus, User
from app.schemas import JobDetailOut, JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])
settings = get_settings()


async def _get_owned_job(job_id: str, user: User, db: AsyncSession) -> Job:
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if not job or job.user_id != user.id:
        # 404, not 403: don't confirm existence of other users' jobs.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.get("", response_model=list[JobOut])
async def list_jobs(user: User = Depends(get_current_verified_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()))
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobDetailOut)
async def get_job(job_id: str, user: User = Depends(get_current_verified_user), db: AsyncSession = Depends(get_db)):
    job = await _get_owned_job(job_id, user, db)
    out = JobDetailOut.model_validate(job)
    if job.status == JobStatus.queued:
        # 1-based position in the (already FCFS) processing queue -- how
        # many still-queued jobs were created before this one, across all
        # users. Only computed for the single-job fetch the job detail page
        # polls, not the dashboard list, to avoid an N+1 count query there.
        ahead = await db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status == JobStatus.queued, Job.created_at < job.created_at)
        )
        out.queue_position = ahead.scalar_one() + 1
    return out


def _build_results_zip(results_dir: str, dest_path: str) -> None:
    """Zips every file under results_dir (predictions, SNP overlap lists,
    the hdf5 dataset, and the per-model .npz outputs -- see README's "Output
    files" section) preserving the DIETNET_RESULTS_BY_MODEL/ subdirectory
    structure. Runs in a thread pool -- it's blocking file I/O and can be a
    few hundred MB, so it must not run on the async event loop."""
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(results_dir):
            for name in files:
                full_path = os.path.join(root, name)
                zf.write(full_path, arcname=os.path.relpath(full_path, results_dir))


@router.get("/{job_id}/download")
async def download_results(
    job_id: str, user: User = Depends(get_current_verified_user), db: AsyncSession = Depends(get_db)
):
    job = await _get_owned_job(job_id, user, db)
    results_dir = job.results_path and os.path.dirname(job.results_path)
    if not results_dir or not os.path.isdir(results_dir):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Results are not available for this job")

    # Held from here until the temp zip is removed below -- that's the
    # window the extra disk usage actually exists for, not just the build
    # step. See app/concurrency.py.
    slot = await acquire_download_slot()
    if slot is None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many concurrent downloads right now (limit {settings.max_concurrent_downloads}). "
            "Please try again in a moment.",
        )

    fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        await run_in_threadpool(_build_results_zip, results_dir, tmp_path)
    except Exception:
        os.remove(tmp_path)
        await release_download_slot(slot)
        raise

    async def _cleanup() -> None:
        os.remove(tmp_path)
        await release_download_slot(slot)

    return FileResponse(
        tmp_path,
        media_type="application/zip",
        filename=f"{job_id}_dietnet_results.zip",
        background=BackgroundTask(_cleanup),
    )
