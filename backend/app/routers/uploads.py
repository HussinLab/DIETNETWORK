import os
import re
import shutil
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.config import get_settings
from app.database import get_db
from app.deps import client_ip, get_current_verified_user
from app.models import AuditLog, InputType, Job, JobStatus, User
from app.schemas import JobOut

router = APIRouter(prefix="/uploads", tags=["uploads"])
settings = get_settings()

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(name or "upload")
    return _SAFE_NAME.sub("_", name)[:200] or "upload"


def _classify(filename: str) -> InputType:
    lower = filename.lower()
    if lower.endswith(".vcf") or lower.endswith(".vcf.gz"):
        return InputType.vcf
    if lower.endswith(".bgen"):
        return InputType.bgen
    if lower.endswith(".bed"):
        return InputType.plink
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST, "Unsupported file type. Upload .vcf, .vcf.gz, .bgen, or .bed"
    )


class _UploadTooLarge(Exception):
    """Raised mid-stream so the caller can clean up every file written so far
    for this job, not just the one that tipped the job over the limit."""


async def _save_upload(upload: UploadFile, dest_path: str, max_bytes: int, running_total: list[int]) -> int:
    """Writes `upload` to `dest_path`, counting its bytes against
    `running_total[0]` -- a job-wide combined-size budget shared across every
    file in the request (genotype + sample/bim/fam), not a per-file cap. A
    PLINK trio each individually under the cap could otherwise add up to well
    over it."""
    size = 0
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            running_total[0] += len(chunk)
            if running_total[0] > max_bytes:
                out.close()
                os.remove(dest_path)
                raise _UploadTooLarge()
            out.write(chunk)
    return size


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_upload(
    genotype_file: UploadFile,
    consent: bool = Form(...),
    sample_file: UploadFile | None = None,
    bim_file: UploadFile | None = None,
    fam_file: UploadFile | None = None,
    user: User = Depends(get_current_verified_user),
    request_ip: str = Depends(client_ip),
    db: AsyncSession = Depends(get_db),
):
    if not consent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Consent is required to process genetic data")

    filename = _sanitize_filename(genotype_file.filename or "")
    input_type = _classify(filename)

    if input_type == InputType.bgen and sample_file is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A .sample file is required alongside .bgen uploads for genotype conversion",
        )
    if input_type == InputType.plink and (bim_file is None or fam_file is None):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A .bim and a .fam file are required alongside a .bed upload",
        )

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(settings.data_root, user.id, job_id, "raw")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    # Shared across every file below -- see _UploadTooLarge / _save_upload:
    # the cap is on the job's combined size, not any single file.
    running_total = [0]

    if input_type == InputType.plink:
        # PLINK requires .bed/.bim/.fam to share an exact basename -- force
        # one regardless of what the three files were originally named, so
        # the worker can find them as a matched set (see _find_genotype_file).
        genotype_path = os.path.join(job_dir, "query.bed")
    else:
        genotype_path = os.path.join(job_dir, filename)

    try:
        await _save_upload(genotype_file, genotype_path, max_bytes, running_total)

        sample_path = None
        if sample_file is not None:
            sample_filename = _sanitize_filename(sample_file.filename or "genotype.sample")
            sample_path = os.path.join(job_dir, sample_filename)
            await _save_upload(sample_file, sample_path, max_bytes, running_total)

        if bim_file is not None:
            await _save_upload(bim_file, os.path.join(job_dir, "query.bim"), max_bytes, running_total)
        if fam_file is not None:
            await _save_upload(fam_file, os.path.join(job_dir, "query.fam"), max_bytes, running_total)
    except _UploadTooLarge:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Combined upload size exceeds the platform's {settings.max_upload_mb} MB limit.",
        )

    job = Job(
        id=job_id,
        user_id=user.id,
        status=JobStatus.queued,
        input_type=input_type,
        raw_path=job_dir,
    )
    db.add(job)
    db.add(AuditLog(user_id=user.id, event="job_created", ip_address=request_ip, detail=job_id))
    await db.commit()
    await db.refresh(job)

    celery_app.send_task(
        "worker.tasks.run_inference_job",
        args=[job.id],
        queue="inference",
    )

    return job
