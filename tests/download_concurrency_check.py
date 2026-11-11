#!/usr/bin/env python3
"""TESTING.md section 5: download concurrency cap.

Needs one already-"done" job -- pass --job-id/--access-token from
preflight_checks.py's --case positive --json-out output (see run_all.sh).
Fires more parallel GET /jobs/{id}/download requests than
MAX_CONCURRENT_DOWNLOADS allows and checks exactly that many succeed.

This is a race-condition test (app/concurrency.py's whole point is
correctness under concurrent acquire attempts) -- run with --rounds > 1 to
build confidence beyond a single pass.

Usage: download_concurrency_check.py --base-url URL --job-id ID --access-token TOKEN
       --limit N [--requests M] [--rounds R]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import session_from_access_token  # noqa: E402


def one_download(base_url: str, job_id: str, token: str) -> int:
    # A fresh session/cookie per request -- mirrors independent concurrent
    # users, and avoids requests.Session's connection pooling serializing
    # what's supposed to be a genuinely concurrent burst.
    session = session_from_access_token(base_url, token)
    resp = session.get(f"{base_url}/jobs/{job_id}/download", timeout=60)
    resp.close()
    return resp.status_code


def run_round(base_url: str, job_id: str, token: str, n_requests: int) -> list[int]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_requests) as pool:
        futures = [pool.submit(one_download, base_url, job_id, token) for _ in range(n_requests)]
        return [f.result() for f in futures]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--access-token", required=True)
    parser.add_argument("--limit", type=int, default=9, help="MAX_CONCURRENT_DOWNLOADS the stack is running with")
    parser.add_argument("--requests", type=int, default=15, help="parallel download requests to fire per round")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    if args.requests <= args.limit:
        print(f"[FAIL] download_concurrency: --requests ({args.requests}) must be > --limit ({args.limit})")
        sys.exit(1)

    all_ok = True
    for round_num in range(1, args.rounds + 1):
        codes = run_round(args.base_url, args.job_id, args.access_token, args.requests)
        ok_count = codes.count(200)
        rejected_count = codes.count(429)
        other = [c for c in codes if c not in (200, 429)]
        round_ok = ok_count == args.limit and rejected_count == args.requests - args.limit and not other
        all_ok = all_ok and round_ok
        status = "PASS" if round_ok else "FAIL"
        print(
            f"[{status}] download_concurrency round {round_num}/{args.rounds}: "
            f"{ok_count} x 200, {rejected_count} x 429"
            + (f", unexpected codes: {other}" if other else "")
        )

    print(f"[{'PASS' if all_ok else 'FAIL'}] download_concurrency: {args.rounds} round(s), limit={args.limit}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
