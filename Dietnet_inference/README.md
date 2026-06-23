# Diet Network inference

Infer genetic ancestry from a query PLINK dataset using an ensemble of 15 pretrained Diet Network models (5 folds × 3 repeats, 24 population labels).

The pipeline:

1. Extracts training SNPs from your PLINK data
2. Fills missing SNPs and builds an HDF5 dataset
3. Runs inference with all 15 models
4. Writes combined predictions (and vote plots in Docker/Singularity)

## Input requirements

- PLINK binary format: `.bed`, `.bim`, `.fam` sharing a common prefix
- Genotypes harmonized to **GRCh38**
- Ideally QC-filtered (e.g. SNPs with >10% missingness removed)

At the end of each run the pipeline reports how many training SNPs were found in your data. **Do not trust predictions if overlap is less than 1,000 SNPs.**

## Model data

Pretrained weights and reference files are on [Zenodo](https://zenodo.org/records/18775363) (`Dietnet_inference.tar.gz`).

**Manual** `infer.sh` expects the Zenodo layout:

```
/path/to/Dietnet_inference/
├── DN_MODELS/     # weights (.pt), embeddings, normalization stats
└── DN_SNPS/       # dietnet_snps.txt, dummy PLINK files
```

**Docker / Singularity** use flattened host directories (see below). Docker can download and unpack these automatically on first run if the container has internet.

## Output files

All methods write to the working directory (`dietnet_results/` for containers):

| File | Description |
|------|-------------|
| `<prefix>.hdf5` | Processed input dataset |
| `<prefix>_dietnetsnps_extractedsnps.txt` | Training SNPs found in your data |
| `<prefix>_dietnetsnps_notextractedsnps.txt` | Training SNPs missing from your data |
| `<prefix>_dietnet_predictions.txt` | Per-sample predictions from all 15 models |
| `<prefix>_DIETNET_RESULTS_BY_MODEL/` | Per-model `.npz` outputs (labels, probabilities, embeddings) |
| `<prefix>_vote_plots/` | Vote plots (Docker/Singularity only) |

For containers, `<prefix>` is the basename of your PLINK prefix (e.g. `mydata` for `mydata.bed`).

---

## Manual inference

**Requirements:** Python 3.11, PLINK v1.9, Zenodo archive with `DN_MODELS/` and `DN_SNPS/`.

### Setup

```bash
python3 -m venv dietnet-env
source dietnet-env/bin/activate
pip install -r dietnet_infer_python3115_requirements.txt
```

Download `Dietnet_inference.tar.gz` from Zenodo and extract it. Use the extracted directory as `<dietnet_files_path>` below.

### Run

Outputs are written to the **current working directory**:

```bash
cd /path/to/results

bash /path/to/Dietnet_inference/infer.sh \
  <plink> \
  <dietnet_code_path> \
  <dietnet_files_path> \
  <plink_prefix> \
  <output_prefix>
```

| Argument | Description |
|----------|-------------|
| `plink` | Path to PLINK v1.9 executable |
| `dietnet_code_path` | This directory (`inference.py`, etc.) |
| `dietnet_files_path` | Zenodo directory with `DN_MODELS/` and `DN_SNPS/` |
| `plink_prefix` | Full path prefix of your `.bed/.bim/.fam` (no extension) |
| `output_prefix` | Prefix for output filenames |

**Example:**

```bash
bash ../Dietnet_inference/infer.sh \
  plink \
  ../Dietnet_inference \
  /data/Dietnet_inference \
  /data/my_cohort/mydata \
  mydata
```

---

## Docker

**Requirements:** [Docker](https://docs.docker.com/get-docker/), optional [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for GPU. **Internet on first run** — models are downloaded automatically.

The image bundles Python 3.11, PLINK, and all inference scripts.

### Directory layout

Create these folders next to the `Dockerfile`:

| Host folder | Mounted to | Purpose |
|-------------|------------|---------|
| `models/` | `/data/models` | Model weights (auto-filled on first run) |
| `additional-files/` | `/data/dietnet_files` | SNP list and dummy PLINK files (auto-filled) |
| `samples/` | `/data/plink` | Your query `.bed/.bim/.fam` (you provide these) |
| `dietnet_results/` | `/out` | All outputs |

### Build and run

```bash
cd Dietnet_inference
mkdir -p models additional-files samples dietnet_results
# Copy or link your PLINK trio into samples/

docker build -t dietnet-infer -f Dockerfile .

docker run --rm --gpus all \
  -v "$PWD/additional-files:/data/dietnet_files" \
  -v "$PWD/models:/data/models" \
  -v "$PWD/samples:/data/plink:ro" \
  -v "$PWD/dietnet_results:/out" \
  -w /out \
  dietnet-infer
```

On the **first run**, `docker-entrypoint.sh` downloads `Dietnet_inference.tar.gz` from Zenodo and unpacks it into `models/` and `additional-files/`. Later runs reuse those files.

**Notes:**

- Drop `--gpus all` for CPU-only inference.
- If `samples/` has exactly one PLINK trio, it is selected automatically.
- Multiple trios: pass the basename as an argument, e.g. `dietnet-infer mydata`, or set `PLINK_PREFIX=/data/plink/mydata`.

---

## Singularity / Apptainer

**Requirements:** Apptainer or Singularity. Build on a machine with internet (downloads base image, PLINK, and Python packages).

The `.sif` image does **not** include model weights. Bind-mount `models/` and `additional-files/` at run time (populate them beforehand — see [Compute nodes without internet](#compute-nodes-without-internet)).

### Build

```bash
cd Dietnet_inference
apptainer build dietnet_inference.sif dietnet_inference.def
```

Copy `dietnet_inference.sif` to your cluster if you build elsewhere.

### Run

```bash
mkdir -p models additional-files samples dietnet_results
# PLINK trio in samples/; models/ and additional-files/ pre-populated

apptainer run \
  --bind "$PWD/additional-files:/data/dietnet_files" \
  --bind "$PWD/models:/data/models" \
  --bind "$PWD/samples:/data/plink:ro" \
  --bind "$PWD/dietnet_results:/out" \
  --pwd /out \
  dietnet_inference.sif
```

Add `--nv` before `run` for NVIDIA GPU support, if available on your cluster.

PLINK trio selection follows the same rules as Docker.

---

## Compute nodes without internet

Many HPC clusters allow network access on **login nodes** but not on **compute nodes**. Prepare data on the login node, then run on compute.

### Docker or Singularity

On the login node:

```bash
cd Dietnet_inference
./download_files.sh ./models ./additional-files
# Add your PLINK files to samples/
```

This fills `models/` and `additional-files/` with the flat layout expected by containers. Copy `models/`, `additional-files/`, `samples/`, and (for Singularity) `dietnet_inference.sif` to scratch, then run with bind mounts pointing at those paths.

If `models/weights_model1_1.pt` already exists, Docker skips the runtime download.

### Manual inference

Download and extract `Dietnet_inference.tar.gz` on the login node. Keep the `DN_MODELS/` and `DN_SNPS/` subdirectories and pass that path as `<dietnet_files_path>` to `infer.sh`.
