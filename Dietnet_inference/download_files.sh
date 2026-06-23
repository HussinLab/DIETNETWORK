#!/usr/bin/env bash
set -euo pipefail

ZENODO_URL='https://zenodo.org/records/18775363/files/Dietnet_inference.tar.gz?download=1'
ZENODO_MD5='f0439ccc546d170f1aec38271cfd7442'

MODELS_DIR="${1:-/path/to/models}"
FILES_DIR="${2:-/path/to/additional-files}"

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

curl -fsSL -o "$tmp" "$ZENODO_URL"
echo "${ZENODO_MD5}  $tmp" | md5sum -c -

mkdir -p "$MODELS_DIR" "$FILES_DIR"
tar --warning=no-unknown-keyword -xzf "$tmp" -C "$(dirname "$MODELS_DIR")"
# After extract, move leaf dirs (same logic as old entrypoint)
mv "$(dirname "$MODELS_DIR")/Dietnet_inference/DN_MODELS/"* "$MODELS_DIR/"
mv "$(dirname "$MODELS_DIR")/Dietnet_inference/DN_SNPS/"* "$FILES_DIR/"
rm -rf "$(dirname "$MODELS_DIR")/Dietnet_inference"