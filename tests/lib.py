"""Shared helpers for the tests/*_check.py scripts: signup/verify/login
against the backend API, uploads, job polling, and reading verification/
notification emails out of MailHog (both services run in the isolated
stack brought up by tests/run_all.sh -- see tests/docker-compose.test.yml).
"""
from __future__ import annotations

import base64
import quopri
import re
import time
import uuid

import requests


class TestFailure(Exception):
    """A pre-flight/queue/download expectation wasn't met -- distinct from a
    network/HTTP error, so callers can tell "the platform behaved wrong"
    apart from "the harness couldn't reach it"."""


def unique_email(tag: str) -> str:
    return f"test-{tag}-{uuid.uuid4().hex[:10]}@example.org"


# --- MailHog (http://<mailhog>:8025/api/v2) ---


def _decode_part(part: dict) -> str:
    body = part.get("Body", "")
    headers = part.get("Headers", {})
    cte = (headers.get("Content-Transfer-Encoding", [""])[0] or "").lower()
    if cte == "quoted-printable":
        return quopri.decodestring(body.encode()).decode(errors="replace")
    if cte == "base64":
        return base64.b64decode(body).decode(errors="replace")
    return body


def wait_for_email(mailhog_url: str, to_address: str, subject_contains: str, timeout: float = 30) -> dict:
    deadline = time.time() + timeout
    last_subjects: list[str] = []
    while time.time() < deadline:
        resp = requests.get(f"{mailhog_url}/api/v2/search", params={"kind": "to", "query": to_address}, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        last_subjects = [i["Content"]["Headers"].get("Subject", [""])[0] for i in items]
        for item in items:
            subject = item["Content"]["Headers"].get("Subject", [""])[0]
            if subject_contains in subject:
                return item
        time.sleep(0.5)
    raise TestFailure(
        f"No email to {to_address} with subject containing {subject_contains!r} within {timeout}s "
        f"(saw subjects: {last_subjects})"
    )


def extract_url(item: dict, path_hint: str) -> str:
    parts = (item.get("MIME") or {}).get("Parts") or [item["Content"]]
    for part in parts:
        text = _decode_part(part)
        # Quoted-printable soft line breaks ("=\r\n") can split a long URL --
        # undo those before searching, not just decode the transfer encoding.
        text = text.replace("=\r\n", "").replace("=\n", "")
        m = re.search(rf"https?://\S*{re.escape(path_hint)}\S*", text)
        if m:
            return m.group(0).rstrip(".,)>\"'")
    raise TestFailure(f"No URL containing {path_hint!r} found in email {item.get('ID')}")


# --- Auth flow ---

PASSWORD = "TestPassw0rd1234"  # meets SignupRequest.password_strength (upper/lower/digit, >=12 chars)


def signup_verify_login(base_url: str, mailhog_url: str, email: str, timeout: float = 30) -> requests.Session:
    r = requests.post(
        f"{base_url}/auth/signup",
        json={"email": email, "password": PASSWORD, "captcha_token": "", "consent": True},
        timeout=10,
    )
    if r.status_code != 201:
        raise TestFailure(f"signup failed for {email}: {r.status_code} {r.text}")

    item = wait_for_email(mailhog_url, email, "verify your email", timeout=timeout)
    verify_url = extract_url(item, "/verify?token=")
    token = verify_url.split("token=", 1)[1]

    r = requests.get(f"{base_url}/auth/verify", params={"token": token}, timeout=10)
    if r.status_code != 200:
        raise TestFailure(f"verify failed for {email}: {r.status_code} {r.text}")

    session = requests.Session()
    r = session.post(
        f"{base_url}/auth/login",
        json={"email": email, "password": PASSWORD, "captcha_token": ""},
        timeout=10,
    )
    if r.status_code != 200:
        raise TestFailure(f"login failed for {email}: {r.status_code} {r.text}")
    return session


# --- Uploads / jobs ---


def upload_plink(session: requests.Session, base_url: str, prefix: str, consent: bool = True) -> dict:
    """prefix: path without extension: opens prefix.bed/.bim/.fam."""
    with open(prefix + ".bed", "rb") as bed, open(prefix + ".bim", "rb") as bim, open(prefix + ".fam", "rb") as fam:
        files = {
            "genotype_file": ("query.bed", bed, "application/octet-stream"),
            "bim_file": ("query.bim", bim, "application/octet-stream"),
            "fam_file": ("query.fam", fam, "application/octet-stream"),
        }
        data = {"consent": "true" if consent else "false"}
        r = session.post(f"{base_url}/uploads", files=files, data=data, timeout=60)
    if r.status_code != 201:
        raise TestFailure(f"upload failed: {r.status_code} {r.text}")
    return r.json()


def session_from_access_token(base_url: str, token: str) -> requests.Session:
    """Rebuilds an authenticated session from a saved access_token cookie
    value (see preflight_checks.py's --json-out for the "positive" case) --
    lets download_concurrency_check.py reuse an already-"done" job without
    re-running signup/verify/login or the full inference ensemble.

    Sets the Cookie header directly rather than going through
    session.cookies.set(domain=...): http.cookiejar's domain-matching
    silently drops cookies for bare hostnames like "localhost" once a
    domain is explicitly attached, so the cookie jar approach sends no
    Cookie header at all against a local test stack."""
    session = requests.Session()
    session.headers["Cookie"] = f"access_token={token}"
    return session


def get_job(session: requests.Session, base_url: str, job_id: str) -> dict:
    r = session.get(f"{base_url}/jobs/{job_id}", timeout=10)
    r.raise_for_status()
    return r.json()


def wait_for_status(
    session: requests.Session, base_url: str, job_id: str, target_statuses: set[str], timeout: float = 600
) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = get_job(session, base_url, job_id)
        if last["status"] in target_statuses:
            return last
        time.sleep(2)
    raise TestFailure(f"job {job_id} did not reach {target_statuses} within {timeout}s (last: {last})")
