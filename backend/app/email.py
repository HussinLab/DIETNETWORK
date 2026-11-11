"""
Outbound email via an authenticated SMTP *submission* relay (port 587,
STARTTLS). Arbutus/Alliance cloud blocks outbound port 25, so this must be
a real relay (institutional ICM/UdeM relay, or a transactional provider
like Postmark/SES) -- host/credentials are config, never hardcoded.

Never attach raw genetic results to an email; only a link to the results
page (the user must be logged in to view it).
"""
import smtplib
from email.message import EmailMessage

from app.config import get_settings

settings = get_settings()


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


def send_verification_email(to_address: str, verify_url: str) -> None:
    subject = f"{settings.app_name}: verify your email"
    text = (
        f"Welcome to {settings.app_name}.\n\n"
        f"Please verify your email address by visiting:\n{verify_url}\n\n"
        f"This link expires in {settings.email_verification_ttl_hours} hours. "
        "If you did not create this account, ignore this email."
    )
    html = f"""
    <p>Welcome to {settings.app_name}.</p>
    <p>Please verify your email address to activate your account:</p>
    <p><a href="{verify_url}">{verify_url}</a></p>
    <p>This link expires in {settings.email_verification_ttl_hours} hours.
    If you did not create this account, you can ignore this email.</p>
    """
    _send(to_address, subject, text, html)


def send_job_completed_email(
    to_address: str,
    job_id: str,
    snp_overlap_count: int,
    snp_overlap_total: int,
    is_reliable: bool,
    results_url: str,
) -> None:
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
    <p style="color:#666;font-size:0.9em;">For your privacy, results are never attached to this email.</p>
    """
    _send(to_address, subject, text, html)


def send_job_failed_email(to_address: str, job_id: str, results_url: str) -> None:
    subject = f"{settings.app_name}: your ancestry job failed"
    text = (
        f"Your ancestry inference job ({job_id}) failed to complete.\n\n"
        "This is usually caused by malformed input data or an unsupported genome build. "
        f"See {results_url} for details, or contact support if the problem persists.\n\n"
        "No stack traces or internal details are included here for your security."
    )
    html = f"""
    <p>Your ancestry inference job <code>{job_id}</code> failed to complete.</p>
    <p>This is usually caused by malformed input data or an unsupported genome build.</p>
    <p><a href="{results_url}">View job details</a> or contact support if the problem persists.</p>
    """
    _send(to_address, subject, text, html)
