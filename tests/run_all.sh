#!/usr/bin/env bash
# Orchestrates TESTING.md end to end against an isolated, throwaway stack:
# generates fixtures, brings the stack up under its own compose project
# (never touches whatever's already running under the default
# "dietnetwork" project on this host), runs every check, prints a
# diagnostics summary, and tears the stack down.
#
# Usage: tests/run_all.sh [--keep] [--skip-fixtures]
#   --keep           leave the isolated stack running afterward (for
#                     debugging a failure) instead of tearing it down
#   --skip-fixtures  don't regenerate dataTest/fixtures/ (they're
#                     deterministic -- only useful to skip if you know
#                     they're already current)
set -uo pipefail
cd "$(dirname "$0")/.."

PROJECT=dietnet-test
ENV_FILE=tests/.env.test
BASE_URL=http://localhost:18000
MAILHOG_URL=http://localhost:18025

KEEP=0
SKIP_FIXTURES=0
for arg in "$@"; do
    case "$arg" in
        --keep) KEEP=1 ;;
        --skip-fixtures) SKIP_FIXTURES=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

dc() {
    docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f docker-compose.yml -f tests/docker-compose.test.yml "$@"
}

RESULTS=() # "NAME:PASS" or "NAME:FAIL", printed as the final summary

record() {
    local name="$1" code="$2"
    if [ "$code" -eq 0 ]; then
        RESULTS+=("$name:PASS")
    else
        RESULTS+=("$name:FAIL")
    fi
}

cleanup() {
    if [ "$KEEP" -eq 1 ]; then
        echo
        echo "--keep set: leaving stack up (project '$PROJECT', backend at $BASE_URL, mailhog at $MAILHOG_URL)"
        echo "Tear down later with: docker compose -p $PROJECT --env-file $ENV_FILE -f docker-compose.yml -f tests/docker-compose.test.yml down"
    else
        echo
        echo "Tearing down isolated stack..."
        dc down --volumes
    fi
}
trap cleanup EXIT

wait_for_backend() {
    for _ in $(seq 1 60); do
        if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    echo "backend did not become healthy within 120s" >&2
    return 1
}

echo "=== Generating pre-flight fixtures ==="
if [ "$SKIP_FIXTURES" -eq 0 ]; then
    python3 tests/fixtures/generate_fixtures.py
else
    echo "(skipped, --skip-fixtures)"
fi

echo
echo "=== Preparing data volume ==="
# Docker auto-creates DATA_HOST_PATH/uploads as root on first bind-mount if
# it doesn't already exist, but backend/worker both run as uid 10001 (see
# their Dockerfiles' `useradd -u 10001`) and never run as root -- so an
# unprepared volume 500s on the very first upload (PermissionError on
# /data/<job_id>). Pre-create and chown it ourselves rather than relying on
# either container to fix its own mount.
mkdir -p tests/.volumes-test/uploads
docker run --rm -v "$(pwd)/tests/.volumes-test/uploads:/v" alpine chown -R 10001:10001 /v

echo
echo "=== Bringing up isolated stack (project: $PROJECT) ==="
dc up -d --build postgres redis mailhog backend worker beat
wait_for_backend || { record "stack-startup" 1; echo "Cannot continue without a healthy backend."; exit 1; }
record "stack-startup" 0

echo
echo "=== Unit tests (worker/tests/test_pipeline.py) ==="
./tests/run_unit_tests.sh "${PROJECT}-worker"
record "unit-tests" $?

echo
echo "=== Pre-flight: positive control (section 1) ==="
python3 tests/preflight_checks.py --case positive --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL" \
    --json-out /tmp/dietnet_test_positive.json
record "preflight-positive" $?

echo
echo "=== Pre-flight: 2a SNP overlap < 1000 ==="
python3 tests/preflight_checks.py --case 2a --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2a-snp-overlap" $?

echo
echo "=== Pre-flight: 2b swapped alleles ==="
python3 tests/preflight_checks.py --case 2b --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2b-harmonization" $?

echo
echo "=== Pre-flight: 2c sample count cap (MAX_SAMPLES temporarily lowered to 2000) ==="
MAX_SAMPLES=2000 dc up -d --no-deps worker
sleep 5
python3 tests/preflight_checks.py --case 2c --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2c-sample-cap" $?
dc up -d --no-deps worker # restore default (10000)
sleep 5

echo
echo "=== Pre-flight: 2d upload size cap (MAX_UPLOAD_MB temporarily lowered to 5) ==="
MAX_UPLOAD_MB=5 dc up -d --no-deps backend
wait_for_backend
python3 tests/preflight_checks.py --case 2d --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2d-upload-size" $?
dc up -d --no-deps backend # restore default (1024)
wait_for_backend

echo
echo "=== FCFS processing queue (section 4; CELERY_WORKER_CONCURRENCY temporarily set to 1) ==="
CELERY_WORKER_CONCURRENCY=1 dc up -d --no-deps worker
sleep 5
python3 tests/fcfs_queue_check.py --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL" --n 5
record "fcfs-queue" $?
dc up -d --no-deps worker # restore default (9)
sleep 5

echo
echo "=== Download concurrency cap (section 5) ==="
if [ -f /tmp/dietnet_test_positive.json ] && command -v jq >/dev/null 2>&1; then
    JOB_ID=$(jq -r .job_id /tmp/dietnet_test_positive.json)
    ACCESS_TOKEN=$(jq -r .access_token /tmp/dietnet_test_positive.json)
    python3 tests/download_concurrency_check.py --base-url "$BASE_URL" \
        --job-id "$JOB_ID" --access-token "$ACCESS_TOKEN" --limit 9 --requests 15 --rounds 3
    record "download-concurrency" $?
else
    echo "Skipped: no completed job from the positive-control step (or jq missing) to download." >&2
    record "download-concurrency" 1
fi

echo
echo "================= SUMMARY ================="
overall=0
for r in "${RESULTS[@]}"; do
    name="${r%%:*}"
    status="${r##*:}"
    printf '%-32s %s\n' "$name" "$status"
    [ "$status" = "FAIL" ] && overall=1
done
echo "============================================="
exit $overall
