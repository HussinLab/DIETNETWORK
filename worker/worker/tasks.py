import glob
import logging
import os
import traceback

from worker.celery_app import celery_app
from worker.config import settings
from worker.db import Job, User, get_session, utcnow
from worker.email import send_job_completed_email, send_job_failed_email, send_job_started_email
from worker.pipeline import (
    PipelineError,
    check_allele_harmonization,
    check_snp_overlap,
    convert_bgen_to_plink,
    convert_vcf_to_plink,
    count_samples,
    parse_predictions,
    requalify_plink,
    run_infer,
)

logger = logging.getLogger("worker.tasks")


def _find_genotype_file(raw_dir: str, input_type: str) -> str:
    if input_type == "vcf":
        for pattern in ("*.vcf.gz", "*.vcf"):
            hits = glob.glob(os.path.join(raw_dir, pattern))
            if hits:
                return hits[0]
        raise PipelineError("No VCF file found in upload directory.")
    elif input_type == "bgen":
        hits = glob.glob(os.path.join(raw_dir, "*.bgen"))
        if not hits:
            raise PipelineError("No bgen file found in upload directory.")
        return hits[0]
    else:
        # uploads.py always saves an already-PLINK upload as query.bed
        # alongside query.bim/query.fam (see create_upload).
        hits = glob.glob(os.path.join(raw_dir, "*.bed"))
        if not hits:
            raise PipelineError("No .bed file found in upload directory.")
        return hits[0]


def _find_sample_file(raw_dir: str) -> str:
    hits = glob.glob(os.path.join(raw_dir, "*.sample"))
    if not hits:
        raise PipelineError("No .sample file found alongside the bgen upload.")
    return hits[0]


@celery_app.task(name="worker.tasks.run_inference_job", bind=True, max_retries=0)
def run_inference_job(self, job_id: str) -> None:
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if job is None:
            logger.error("Job %s not found; nothing to do.", job_id)
            return

        user = session.get(User, job.user_id)
        job.status = "running"
        job.started_at = utcnow()
        session.commit()

        # Counterpart to the completion/failure emails: tells a user who was
        # behind the concurrency cap (see DEPLOYMENT.md) that their job made
        # it off the queue, without them needing to keep the page open.
        # Guarded separately from the rest of the task: this fires before
        # any real processing happens, so a transient SMTP hiccup here must
        # not fail an otherwise-healthy job the way it would further down.
        if user:
            try:
                send_job_started_email(user.email, job.id)
            except Exception:
                logger.warning("Failed to send job-started email for job %s", job.id, exc_info=True)

        raw_dir = job.raw_path
        results_dir = os.path.join(settings.data_root, job.user_id, job.id, "results")
        convert_dir = os.path.join(raw_dir, "converted")
        os.makedirs(results_dir, exist_ok=True)
        os.makedirs(convert_dir, exist_ok=True)

        plink_prefix = os.path.join(convert_dir, "query")

        if job.input_type == "vcf":
            genotype_file = _find_genotype_file(raw_dir, "vcf")
            convert_vcf_to_plink(genotype_file, plink_prefix)
        elif job.input_type == "bgen":
            genotype_file = _find_genotype_file(raw_dir, "bgen")
            sample_file = _find_sample_file(raw_dir)
            convert_bgen_to_plink(genotype_file, sample_file, plink_prefix)
        else:
            genotype_file = _find_genotype_file(raw_dir, "plink")
            in_prefix = genotype_file[: -len(".bed")]
            requalify_plink(in_prefix, plink_prefix)

        # Sample-count cap: only knowable once the upload is in PLINK form
        # (a .fam line per sample). Rejects before any further processing.
        sample_count = count_samples(plink_prefix)
        if sample_count > settings.max_samples:
            raise PipelineError(
                f"Your data has {sample_count} samples, which exceeds the platform's limit of "
                f"{settings.max_samples}. Please split your data into smaller batches and re-upload."
            )

        # Pre-flight SNP-overlap check: reject before spending several
        # minutes running the 15-model ensemble on data we already know is
        # unreliable (see pipeline.check_snp_overlap).
        preflight_prefix = os.path.join(convert_dir, "preflight_overlap")
        overlap_count, overlap_total = check_snp_overlap(plink_prefix, preflight_prefix)
        if overlap_count < settings.min_reliable_snp_overlap:
            raise PipelineError(
                f"Only {overlap_count} of {overlap_total} Diet Network reference SNPs were found "
                f"in your data (minimum {settings.min_reliable_snp_overlap} required for reliable "
                "predictions). This is often caused by a sparse genotyping array or a genome build "
                "other than GRCh38 -- consider imputing your data to increase SNP coverage, then re-upload."
            )

        # Allele-harmonization check: same extracted .bim the overlap check
        # just produced, compared against the training panel's reference
        # alleles. Catches a systematically swapped or strand-flipped
        # upload, which --real-ref-alleles would otherwise let through with
        # silently inverted dosage rather than an error (see
        # pipeline.check_allele_harmonization).
        dummy_bim_path = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dummy.bim")
        harmonization = check_allele_harmonization(preflight_prefix + ".bim", dummy_bim_path)
        compared = harmonization["compared"]
        mismatched = harmonization["swapped"] + harmonization["flipped"] + harmonization["ambiguous"]
        if compared and mismatched / compared > settings.max_allele_mismatch_fraction:
            dominant = max(("swapped", "flipped", "ambiguous"), key=harmonization.get)
            explanation = {
                "swapped": "your A1/A2 allele columns appear to be swapped relative to the reference panel",
                "flipped": "your data appears to be reported on the opposite DNA strand (a strand flip) "
                "relative to GRCh38",
                "ambiguous": "many of the mismatched SNPs are A/T or C/G pairs, where a strand flip and an "
                "allele swap look identical, so the exact cause can't be determined automatically",
            }[dominant]
            raise PipelineError(
                f"{mismatched} of {compared} overlapping SNPs ({mismatched / compared:.0%}) have allele "
                f"coding that doesn't match the Diet Network reference panel -- {explanation}. Please "
                "re-harmonize your alleles to match the reference panel (GRCh38, matching strand) and re-upload."
            )

        output_prefix = os.path.join(results_dir, "result")
        predictions_file = run_infer(plink_prefix, output_prefix)

        is_reliable = overlap_count >= settings.min_reliable_snp_overlap
        predictions = parse_predictions(predictions_file)

        job.status = "done"
        job.results_path = predictions_file
        job.snp_overlap_count = overlap_count
        job.snp_overlap_total = overlap_total
        job.is_reliable = is_reliable
        job.predictions = {"rows": predictions}
        job.completed_at = utcnow()
        session.commit()

        if settings.delete_raw_after_success:
            _delete_raw(job, session)

        if user:
            send_job_completed_email(user.email, job.id, overlap_count, overlap_total, is_reliable)

    except Exception as exc:  # noqa: BLE001 -- top-level task boundary, must not raise
        logger.error("Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())
        session.rollback()
        job = session.get(Job, job_id)
        if job is not None:
            job.status = "failed"
            # User-facing message only -- never a raw stack trace.
            job.error_message = (
                str(exc)
                if isinstance(exc, PipelineError)
                else "An unexpected error occurred while processing your file. Support has been notified."
            )
            job.completed_at = utcnow()
            session.commit()
            user = session.get(User, job.user_id)
            if user:
                send_job_failed_email(user.email, job.id)
    finally:
        session.close()


def _delete_raw(job: Job, session) -> None:
    import shutil

    if job.raw_path and os.path.exists(job.raw_path):
        shutil.rmtree(job.raw_path, ignore_errors=True)
        job.raw_path = None
        job.raw_deleted_at = utcnow()
        session.commit()
