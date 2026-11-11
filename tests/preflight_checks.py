#!/usr/bin/env python3
"""TESTING.md section 1 (positive control) + section 2 (pre-flight rejection
checks 2a-2d), run against an already-running isolated stack.

2a/2b use the generated dataTest/fixtures/{low_overlap,swapped} fileset
(see tests/fixtures/generate_fixtures.py). 2c/2d reuse the unmodified
positive-control trio -- they only trigger a rejection because
tests/run_all.sh recreates the worker/backend service with
MAX_SAMPLES/MAX_UPLOAD_MB temporarily lowered before invoking this script
with --case 2c / --case 2d (see run_all.sh; TESTING.md itself recommends
this over fabricating an oversized fixture -- "simpler... exercises the
same code path").

Usage: preflight_checks.py --case {positive,2a,2b,2c,2d} --base-url URL --mailhog-url URL [--json-out PATH]
Exit code 0 = expectation met, 1 = not met (see stdout for the diagnostic).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import TestFailure, get_job, signup_verify_login, unique_email, upload_plink, wait_for_status  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSITIVE_CONTROL = os.path.join(
    REPO_ROOT,
    "dataTest",
    "1000G.2504_WGS30x.GSA17k_MHI.intersectGSA.miss10perc.maf0.05.pruned.autosomes.noHLA.phased_imputed",
)
FIXTURES_DIR = os.path.join(REPO_ROOT, "dataTest", "fixtures")

CASES = {
    "positive": {"fixture": POSITIVE_CONTROL, "expect_upload_status": 201},
    "2a": {"fixture": os.path.join(FIXTURES_DIR, "low_overlap"), "expect_upload_status": 201},
    "2b": {"fixture": os.path.join(FIXTURES_DIR, "swapped"), "expect_upload_status": 201},
    "2c": {"fixture": POSITIVE_CONTROL, "expect_upload_status": 201},  # rejected once running, not at upload time
    "2d": {"fixture": POSITIVE_CONTROL, "expect_upload_status": 413},  # rejected synchronously, in create_upload
}


def _upload_raw(session: requests.Session, base_url: str, prefix: str) -> requests.Response:
    with open(prefix + ".bed", "rb") as bed, open(prefix + ".bim", "rb") as bim, open(prefix + ".fam", "rb") as fam:
        files = {
            "genotype_file": ("query.bed", bed, "application/octet-stream"),
            "bim_file": ("query.bim", bim, "application/octet-stream"),
            "fam_file": ("query.fam", fam, "application/octet-stream"),
        }
        return session.post(f"{base_url}/uploads", files=files, data={"consent": "true"}, timeout=120)


def run_case(case: str, base_url: str, mailhog_url: str, job_timeout: float) -> dict:
    spec = CASES[case]
    email = unique_email(f"preflight-{case}")
    session = signup_verify_login(base_url, mailhog_url, email)

    if spec["expect_upload_status"] == 413:
        resp = _upload_raw(session, base_url, spec["fixture"])
        ok = resp.status_code == 413 and "exceeds the platform's" in resp.text
        return {
            "case": case,
            "passed": ok,
            "detail": f"upload returned {resp.status_code}: {resp.text[:300]}",
        }

    job = upload_plink(session, base_url, spec["fixture"])
    job = wait_for_status(session, base_url, job["id"], {"done", "failed"}, timeout=job_timeout)

    if case == "positive":
        ok = job["status"] == "done" and job.get("is_reliable") is True
        return {
            "case": case,
            "passed": ok,
            "job_id": job["id"],
            # Handed to download_concurrency_check.py so it can reuse this
            # already-"done" job without re-running the full ensemble.
            "access_token": session.cookies.get("access_token"),
            "detail": json.dumps(job),
        }

    expected_substrings = {
        "2a": "Diet Network reference SNPs were found",
        "2b": "allele coding that doesn't match",
        "2c": "exceeds the platform's limit",
    }[case]
    error = job.get("error_message") or ""
    ok = job["status"] == "failed" and expected_substrings in error
    return {"case": case, "passed": ok, "job_id": job["id"], "detail": error or json.dumps(job)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=sorted(CASES))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mailhog-url", required=True)
    parser.add_argument("--job-timeout", type=float, default=900, help="seconds to wait for job completion")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    try:
        result = run_case(args.case, args.base_url, args.mailhog_url, args.job_timeout)
    except TestFailure as exc:
        result = {"case": args.case, "passed": False, "detail": str(exc)}

    status = "PASS" if result["passed"] else "FAIL"
    print(f"[{status}] preflight/{args.case}: {result.get('detail', '')}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(result, f)

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
