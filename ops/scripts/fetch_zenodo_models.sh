#!/bin/bash
# Downloads the pretrained Diet Network weights + SNP files from Zenodo
# record 16943452 (DN_MODELS/ and DN_SNPS/) ONCE, at worker image build
# time. Never call this at request/runtime -- see deployPlan.md point 5.
#
# Usage: fetch_zenodo_models.sh <dest_dir>
set -euo pipefail

DEST="${1:?Usage: fetch_zenodo_models.sh <dest_dir>}"
ZENODO_RECORD="16943452"
ZENODO_API="https://zenodo.org/api/records/${ZENODO_RECORD}"
# Only the inference file is needed at runtime -- Dietnet_training.tar.gz
# (1KGP training data / repro material, ~260MB) is not used by infer.sh and
# is deliberately skipped here.
WANTED_FILE="Dietnet_inference.tar.gz"

mkdir -p "$DEST"
cd "$DEST"

echo "Fetching file list for Zenodo record ${ZENODO_RECORD}..."
curl -fsSL "$ZENODO_API" -o record.json

# Each Zenodo record file has a direct download link at .files[].links.self
python3 - "$DEST" "$WANTED_FILE" <<'PYEOF'
import json
import os
import sys
import urllib.request

dest, wanted = sys.argv[1], sys.argv[2]
with open(os.path.join(dest, "record.json")) as f:
    record = json.load(f)

for entry in record.get("files", []):
    name = entry["key"]
    if name != wanted:
        continue
    url = entry["links"]["self"]
    out_path = os.path.join(dest, name)
    print(f"Downloading {name} ...")
    urllib.request.urlretrieve(url, out_path)
    break
else:
    sys.exit(f"'{wanted}' not found in Zenodo record {sys.argv[1]!r} file list")
PYEOF

rm -f record.json

# Dietnet_inference.tar.gz unpacks to Dietnet_inference/{DN_MODELS,DN_SNPS}/
# (one level nested, matching this repo's own Dietnet_inference/ layout) --
# not DN_MODELS/DN_SNPS directly at the archive root. Unpack then flatten so
# the final layout is: $DEST/DN_MODELS/*.pt|*.npz and $DEST/DN_SNPS/*.txt
echo "Unpacking $WANTED_FILE ..."
tar -xzf "$WANTED_FILE" -C "$DEST"
rm -f "$WANTED_FILE"

if [ -d "$DEST/Dietnet_inference/DN_MODELS" ] && [ -d "$DEST/Dietnet_inference/DN_SNPS" ]; then
    mv "$DEST/Dietnet_inference/DN_MODELS" "$DEST/DN_MODELS"
    mv "$DEST/Dietnet_inference/DN_SNPS" "$DEST/DN_SNPS"
    rmdir "$DEST/Dietnet_inference" 2>/dev/null || true
fi

if [ ! -d "$DEST/DN_MODELS" ] || [ ! -d "$DEST/DN_SNPS" ]; then
    echo "WARNING: expected $DEST/DN_MODELS and $DEST/DN_SNPS after unpacking." >&2
    echo "Inspect the Zenodo record layout (it may have changed) and adjust this script." >&2
    ls -la "$DEST" >&2
    exit 1
fi

# Zenodo tarball entries carry the uploader's original uid/gid/mode, which
# means nothing inside this image and can leave files unreadable to the
# unprivileged `worker` user infer.sh actually runs as. Normalize so the
# runtime user can read (but not modify) its own model files.
chmod -R a+rX,go-w "$DEST"

echo "Diet Network model files ready at $DEST"
