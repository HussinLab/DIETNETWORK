#!/usr/bin/env bash
# Runs worker/tests/test_pipeline.py inside an ephemeral container from the
# worker image -- needed for two reasons, not just plink/DN_SNPS access:
# worker/worker/pipeline.py uses `str | None` syntax (Python 3.10+), and the
# host's system python3 here is 3.9. Fully decoupled from any running
# compose stack: just `docker run --rm` off an already-built image, no
# network/DB/queue involved.
#
# Usage: tests/run_unit_tests.sh [image]  (default image: dietnetwork-worker)
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${1:-dietnetwork-worker}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Image '$IMAGE' not found locally -- building from worker/Dockerfile..."
    docker build -f worker/Dockerfile -t "$IMAGE" .
fi

docker run --rm \
    -v "$(pwd)/worker/tests:/app/tests:ro" \
    -v "$(pwd)/dataTest:/app/dataTest:ro" \
    -e FIXTURES_DIR=/app/dataTest/fixtures \
    --entrypoint bash \
    "$IMAGE" -c "pip install --quiet --no-cache-dir pytest && cd /app && python -m pytest tests -v"
