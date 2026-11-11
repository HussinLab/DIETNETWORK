# Worker image: CPU-only inference. torch==2.10.0 is pinned in
# dietnet_infer_python3115_requirements.txt; we install the CPU wheel
# explicitly (no CUDA, no GPU quota needed -- see deployPlan.md point 2).
FROM python:3.11.5-slim

ARG DEBIAN_FRONTEND=noninteractive
WORKDIR /opt

# --- OS deps + PLINK 1.9 / PLINK2 (static builds, no apt package exists) ---
# bc is required by Dietnet_inference/infer.sh (SNP-overlap scaling factor);
# without it, `scale=$(echo "... " | bc -l)` silently comes out empty, which
# makes the downstream `--scale $scale` argparse call fail with "expected
# one argument" -- and infer.sh doesn't check that exit code, so the script
# still prints "Inference ... completed" even though no predictions file
# (or even the intermediate .hdf5) was ever produced.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential unzip curl ca-certificates bc \
    && rm -rf /var/lib/apt/lists/*

# PLINK 1.9 (stable build). Override PLINK_URL at build time if the upstream
# link changes: `docker build --build-arg PLINK_URL=...`
ARG PLINK_URL=https://s3.amazonaws.com/plink1-assets/plink_linux_x86_64_20231211.zip
RUN mkdir -p /opt/plink && curl -fsSL "$PLINK_URL" -o /tmp/plink.zip \
    && unzip -o /tmp/plink.zip -d /opt/plink && rm /tmp/plink.zip \
    && chmod +x /opt/plink/plink

# PLINK2 (needed for bgen -> PLINK1.9-binary conversion)
ARG PLINK2_URL=https://s3.amazonaws.com/plink2-assets/alpha7/plink2_linux_x86_64_20260808.zip
RUN mkdir -p /opt/plink2 && curl -fsSL "$PLINK2_URL" -o /tmp/plink2.zip \
    && unzip -o /tmp/plink2.zip -d /opt/plink2 && rm /tmp/plink2.zip \
    && chmod +x /opt/plink2/plink2

# --- Diet Network inference code (from this repo) ---
COPY Dietnet_inference /opt/dietnet/Dietnet_inference
RUN chmod +x /opt/dietnet/Dietnet_inference/infer.sh

# --- Python deps: model-validated pins first, CPU-only torch, then worker extras ---
COPY Dietnet_inference/dietnet_infer_python3115_requirements.txt /opt/dietnet/requirements.txt
COPY worker/requirements.txt /opt/worker-requirements.txt
RUN pip install --no-cache-dir -r /opt/dietnet/requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /opt/worker-requirements.txt

# --- Pretrained weights + SNP files, downloaded ONCE at image build time (Zenodo 16943452) ---
# Never fetched at request/runtime. See ops/scripts/fetch_zenodo_models.sh.
COPY ops/scripts/fetch_zenodo_models.sh /opt/fetch_zenodo_models.sh
RUN chmod +x /opt/fetch_zenodo_models.sh && /opt/fetch_zenodo_models.sh /opt/dietnet/files

# --- Worker application code ---
WORKDIR /app
COPY worker/worker ./worker

ENV PLINK_PATH=/opt/plink/plink \
    PLINK2_PATH=/opt/plink2/plink2 \
    DIETNET_CODE_PATH=/opt/dietnet/Dietnet_inference \
    DIETNET_FILES_PATH=/opt/dietnet/files \
    PYTHONUNBUFFERED=1

RUN useradd -m -u 10001 worker && mkdir -p /data && chown -R worker /data /app
USER worker

# Two process types share this image: `celery worker` and `celery beat`
# (compose picks the command per-service via `command:`; see
# docker-compose.yml). Shell form (not exec-form array) so
# CELERY_WORKER_CONCURRENCY is read at container start, letting the
# processing-concurrency cap be tuned via env without an image rebuild.
# Defaults to 1 (safe/conservative) if the image is run standalone without
# it set -- docker-compose.yml's worker service sets it explicitly.
CMD celery -A worker.celery_app.celery_app worker --loglevel=INFO \
    --concurrency=${CELERY_WORKER_CONCURRENCY:-1} -Q inference,maintenance
