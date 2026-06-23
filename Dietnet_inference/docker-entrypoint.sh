#!/bin/bash
set -euo pipefail

mkdir -p /data/models /data/dietnet_files

if [[ ! -f /data/models/weights_model1_1.pt ]]; then
  tmp=$(mktemp)
  curl -fsSL -o "$tmp" "${ZENODO_FILE_URL}"
  echo "${ZENODO_MD5}  $tmp" | md5sum -c -
  tar --warning=no-unknown-keyword -xzf "$tmp" -C /data/models ${TAR_STRIP:+--strip-components="${TAR_STRIP}"}
  mv /data/models/Dietnet_inference/DN_MODELS/* /data/models/
  mv /data/models/Dietnet_inference/DN_SNPS/* /data/dietnet_files/
  rm -rf /data/models/Dietnet_inference "/data/models/._Dietnet_inference"
  rm -f "$tmp"
fi

exec /bin/bash /app/infer_docker.sh "$@"
