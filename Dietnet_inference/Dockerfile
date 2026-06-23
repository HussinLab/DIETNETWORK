FROM python:3.11-slim-bookworm

ARG ZENODO_FILE_URL=https://zenodo.org/records/18775363/files/Dietnet_inference.tar.gz?download=1
ARG ZENODO_MD5=f0439ccc546d170f1aec38271cfd7442
ENV ZENODO_FILE_URL=${ZENODO_FILE_URL}
ENV ZENODO_MD5=${ZENODO_MD5}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bc \
    ca-certificates \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/plink.zip \
      https://s3.amazonaws.com/plink1-assets/plink_linux_x86_64_20241022.zip \
    && unzip -p /tmp/plink.zip plink > /usr/local/bin/plink \
    && chmod +x /usr/local/bin/plink \
    && rm /tmp/plink.zip

WORKDIR /app

COPY dietnet_infer_python3115_requirements.txt .
RUN pip install --no-cache-dir -r dietnet_infer_python3115_requirements.txt

COPY infer_docker.sh inference.py inference_dataset.py inference_combine_results.py plot_results.py ./
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD []