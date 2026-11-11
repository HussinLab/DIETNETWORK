"""Same SMTP submission-relay approach as the API (see backend/app/email.py);
duplicated here in sync form since Celery tasks aren't async."""
import smtplib
from email.message import EmailMessage

from worker.config import settings


def _send(to_address: str, subject: str, text_body: str, html_body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = to_address
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)


def send_job_completed_email(
    to_address: str, job_id: str, snp_overlap_count: int, snp_overlap_total: int, is_reliable: bool
) -> None:
    results_url = f"{settings.frontend_url}/jobs/{job_id}"
    subject = f"{settings.app_name}: your ancestry results are ready"
    reliability_note = (
        "Your SNP overlap with the Diet Network reference set is healthy."
        if is_reliable
        else (
            "WARNING: your SNP overlap is below 1000 SNPs, the threshold below which "
            "predictions are considered unreliable. Please review the caveat on the results page."
        )
    )
    text = (
        f"Your ancestry inference job ({job_id}) has completed.\n\n"
        f"SNP overlap with Diet Network reference set: {snp_overlap_count} / {snp_overlap_total}\n"
        f"{reliability_note}\n\n"
        f"View your results (login required): {results_url}\n\n"
        "For your privacy, results are not attached to this email."
    )
    html = f"""
    <p>Your ancestry inference job <code>{job_id}</code> has completed.</p>
    <p>SNP overlap with Diet Network reference set: <b>{snp_overlap_count} / {snp_overlap_total}</b></p>
    <p style="{'color:#b91c1c;font-weight:bold;' if not is_reliable else ''}">{reliability_note}</p>
    <p><a href="{results_url}">View your results</a> (login required).</p>
    """
    _send(to_address, subject, text, html)


def send_job_started_email(to_address: str, job_id: str) -> None:
    """Fired once when a job leaves the queue and actually starts
    processing (see the queued -> running transition in worker/tasks.py) --
    the FCFS-queue counterpart to the completion/failure emails, so a user
    waiting behind the concurrency cap (see DEPLOYMENT.md) doesn't have to
    keep the job page open to know their upload made it off the queue."""
    results_url = f"{settings.frontend_url}/jobs/{job_id}"
    subject = f"{settings.app_name}: your ancestry job has started"
    text = (
        f"Your ancestry inference job ({job_id}) has left the queue and started processing.\n\n"
        f"Track progress: {results_url}\n\n"
        "We'll email you again once it completes."
    )
    html = f"""
    <p>Your ancestry inference job <code>{job_id}</code> has left the queue and started processing.</p>
    <p><a href="{results_url}">Track progress</a>.</p>
    <p>We'll email you again once it completes.</p>
    """
    _send(to_address, subject, text, html)


def send_job_failed_email(to_address: str, job_id: str) -> None:
    results_url = f"{settings.frontend_url}/jobs/{job_id}"
    subject = f"{settings.app_name}: your ancestry job failed"
    text = (
        f"Your ancestry inference job ({job_id}) failed to complete.\n\n"
        "This is usually caused by malformed input data or an unsupported genome build. "
        f"See {results_url} for details.\n\n"
        f"If this looks wrong, please open an issue: {settings.github_issues_url}"
    )
    html = f"""
    <p>Your ancestry inference job <code>{job_id}</code> failed to complete.</p>
    <p>This is usually caused by malformed input data or an unsupported genome build.</p>
    <p><a href="{results_url}">View job details</a>.</p>
    <p>If this looks wrong, please <a href="{settings.github_issues_url}">open an issue on GitHub</a>.</p>
    """
    _send(to_address, subject, text, html)
