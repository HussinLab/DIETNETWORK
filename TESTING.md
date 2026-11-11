# Test plan: genotype pre-flight checks + queueing system

Covers the uncommitted changes on `webPlatform`: the four upload/inference
pre-flight checks (`worker/worker/tasks.py`) and the two concurrency caps
(processing queue, download semaphore). Uses the real 1000 Genomes trio in
`dataTest/` as source data, derived into fixtures per case below.

## 0. Setup

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
# frontend: http://localhost:5173, API: http://localhost:8000, mail: http://localhost:8025
```

Register + verify a test user (CAPTCHA is disabled in dev):

```bash
curl -s -X POST http://localhost:8000/auth/signup -H 'Content-Type: application/json' \
  -d '{"email":"test1@example.com","password":"..."}'
# grab the verify link from http://localhost:8025 (MailHog), then:
curl -s "http://localhost:8000/auth/verify?token=..."
curl -s -c cookies.txt -X POST http://localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"test1@example.com","password":"..."}'
```

All calls below assume `-b cookies.txt` for the session cookie.

## 1. Positive control

`dataTest/1000G...bed/.bim/.fam` — 2,504 samples, 229,986 SNPs, unmodified.
Well inside every limit (< 1GB, < 10k samples, full panel overlap, correctly
harmonized).

```bash
curl -b cookies.txt -F "genotype_file=@dataTest/...bed" \
  -F "bim_file=@dataTest/...bim" -F "fam_file=@dataTest/...fam" \
  -F "consent=true" http://localhost:8000/uploads
```

Expect: job created, status progresses to `done`, `is_reliable: true`,
results downloadable. This is the baseline every other case is checked
against — if this fails, fix it before trusting any rejection test below.

## 2. Pre-flight check fixtures

Generate each from the positive-control trio with `plink1.9` (or the
worker's own `settings.plink_path` inside the container). Panel file for
overlap/harmonization: `DN_SNPS/dietnet_snps.txt` and `DN_SNPS/dummy.bim`
under `settings.dietnet_files_path` in the worker image.

### 2a. SNP overlap < 1000 (`min_reliable_snp_overlap`)

```bash
shuf -n 500 <panel>/dietnet_snps.txt > /tmp/tiny_panel.txt
plink1.9 --bfile dataTest/1000G... --extract /tmp/tiny_panel.txt \
  --make-bed --out /tmp/fixtures/low_overlap
```
Expect: upload rejected before inference with the "Only N of M Diet
Network reference SNPs were found... consider imputing" message
(`worker/worker/tasks.py`, `check_snp_overlap`).

### 2b. Allele harmonization (swapped / strand-flipped)

Copy the `.bim`, swap the A1/A2 columns (5 and 6) for enough overlapping
SNPs to exceed `max_allele_mismatch_fraction` (default 5%):

```bash
awk 'BEGIN{OFS="\t"} {t=$5; $5=$6; $6=t; print}' dataTest/...bim > /tmp/fixtures/swapped.bim
cp dataTest/...bed /tmp/fixtures/swapped.bed
cp dataTest/...fam /tmp/fixtures/swapped.fam
```
Expect: rejection naming "swapped" (or "flipped"/"ambiguous" depending on
which alleles you pick — non-A/T,C/G pairs give an unambiguous "swapped"
classification) — see `check_allele_harmonization`.

### 2c. Sample count > `max_samples` (10,000)

2,504 samples is under the cap, so this needs synthetic inflation — e.g.
concatenate duplicated `.fam` rows (with unique IIDs) and the matching
`.bed` genotype blocks past 10,000, or just lower `MAX_SAMPLES` in the
test environment (e.g. to 2000) and reuse the unmodified fixture. The
latter is simpler and exercises the same code path.

### 2d. Combined upload size > `max_upload_mb` (1024 MB combined)

Easiest as a boundary/unit check rather than a real 1GB+ file: temporarily
lower `MAX_UPLOAD_MB` in the test environment and re-upload the unmodified
trio (~144 MB), or pad a copy of the `.bed` with junk bytes to cross a
lowered threshold.

For each of 2a-2d: assert the job lands in `failed` status, the
`JobDetailOut` / failure email contains the expected message text, and the
run stopped *before* `infer.sh` was invoked (check worker logs — no
`Dietnet_inference/infer.sh` line for that job).

## 3. Automating 1-2 as unit tests

`check_snp_overlap`, `check_allele_harmonization`, and `count_samples` in
`worker/worker/pipeline.py` are pure functions over `.bed/.bim/.fam` files
— wrap 2a-2c as pytest fixtures (small synthetic trios, not necessarily
the full 2,504-sample file) asserting exact return values/classifications.
Fast, no Docker, no real `plink` binary required if fixtures are
pre-generated. Reserve the full curl-through-the-API version above as an
integration smoke test, run less often.

## 4. Processing queue (FCFS)

Register N test users (script the signup/verify/login flow), then fire
uploads back-to-back and immediately poll `GET /jobs/{id}`:

```bash
for i in $(seq 1 5); do
  curl -b cookies_$i.txt -F ... http://localhost:8000/uploads &
done
wait
```
Expect: jobs process in creation order; `GET /jobs/{id}` on a still-queued
job returns `queue_position` counting only earlier-created queued jobs;
each user receives a "job started" email (MailHog) when their job leaves
the queue, in the same order. Temporarily set `CELERY_WORKER_CONCURRENCY=1`
in the test environment to make ordering easy to observe (default is 9).

## 5. Download concurrency cap (max 9)

Needs one already-`done` job. Fire >9 parallel downloads at it:

```bash
seq 1 15 | xargs -P 15 -I{} curl -s -o /dev/null -w '%{http_code}\n' \
  -b cookies.txt http://localhost:8000/jobs/<job_id>/download
```
Expect: exactly 9 requests return `200`, the rest return `429` with the
"Too many concurrent downloads" message. Re-run a few times — this is a
race condition test, a single pass proving 9/6 isn't sufficient
confidence; also verify the count via `MAX_CONCURRENT_DOWNLOADS=2` in the
test environment for a cheaper/faster repeat run.

## Out of scope here

Genome-build (hg19 vs GRCh38) mismatch detection and result encryption are
**not implemented** in the current codebase (confirmed by code read, not
inferred) — no test plan for them until the feature exists.

## Automating this: tests/

Everything above is now scripted under `tests/` (plus `worker/tests/` for
the pure unit tests):

| File | Covers |
| --- | --- |
| `tests/fixtures/generate_fixtures.py` | Generates 2a/2b fixtures from `dataTest/` (pure Python, no plink needed) |
| `worker/tests/test_pipeline.py` | Section 3 — unit tests for `count_samples`/`check_allele_harmonization`/`check_snp_overlap`, run via `tests/run_unit_tests.sh` |
| `tests/preflight_checks.py` | Sections 1–2 — positive control + 2a/2b/2c/2d, run against a live stack |
| `tests/fcfs_queue_check.py` | Section 4 |
| `tests/download_concurrency_check.py` | Section 5 |
| `tests/run_all.sh` | Runs everything above end to end against an isolated, throwaway compose stack (`--keep` to leave it up for debugging) |

## Results (last full run: 2026-09-18)

Run via `tests/run_all.sh` against an isolated stack (compose project
`dietnet-test`, ports 18000/18025) — see "How this was tested" below for
exactly what that does and doesn't prove.

| # | Check | Result | Detail |
| - | --- | --- | --- |
| 0 | Unit tests (`worker/tests/test_pipeline.py`) | ✅ PASS | 6/6 — `count_samples`, `check_allele_harmonization` (all 5 classifications), `check_snp_overlap` (both real plink runs) |
| 1 | Positive control | ✅ PASS | `229986/229986` SNP overlap, `is_reliable: true`, `status: done`. Full 15-model ensemble ran for real (~6.5 min), predictions looked sane (e.g. European 1000G samples called `CEUGBR`) |
| 2a | SNP overlap < 1000 | ✅ PASS | Rejected: *"Only 400 of 229986 Diet Network reference SNPs were found..."* |
| 2b | Swapped alleles | ✅ PASS | Rejected: *"229986 of 229986 overlapping SNPs (100%) have allele coding that doesn't match..."* — clean 100% once the pipeline bug below was fixed (was a noisy 76% before, polluted by that same bug) |
| 2c | Sample count > cap | ✅ PASS | `MAX_SAMPLES` temporarily lowered to 2000; rejected: *"Your data has 2504 samples, which exceeds the platform's limit of 2000..."* |
| 2d | Upload size > cap | ✅ PASS | `MAX_UPLOAD_MB` temporarily lowered to 5; upload returned `413`: *"Combined upload size exceeds the platform's 5 MB limit."* |
| 4 | FCFS processing queue | ✅ PASS | `CELERY_WORKER_CONCURRENCY` temporarily set to 1; 5 jobs' "job started" emails arrived in exact creation order; `queue_position` consistent with FCFS at every poll |
| 5 | Download concurrency cap | ✅ PASS | 15 parallel requests against one `done` job, 3 rounds: consistently 9×`200` / 6×`429` at the default `MAX_CONCURRENT_DOWNLOADS=9` |

### Bugs found and fixed while building this

None of these were artifacts of the test harness — all three would affect
a real deployment:

1. **Empty Alembic migration** (`backend/alembic/versions/38afb3b0bf90_baseline_schema.py`) — `upgrade()` was an unfilled `alembic revision` stub (`pass`), so a fresh database got zero tables and every request 500'd (`relation "users" does not exist`). Regenerated via `alembic revision --autogenerate` against the real models. The already-running deployment never hit this because its database predates the Alembic switchover.
2. **`SMTP_USE_STARTTLS` never wired into `docker-compose.yml`** — the base `x-backend-env`/`x-worker-env` anchors never referenced it, so there was no way to disable STARTTLS via `.env` in a real deployment (only the dev/local-test overlays hardcoded it). Added `SMTP_USE_STARTTLS: ${SMTP_USE_STARTTLS:-true}` to both (backward-compatible default).
3. **Missing `--real-ref-alleles` in `requalify_plink`/`convert_vcf_to_plink`** (`worker/worker/pipeline.py`) — without it, plink's `--make-bed` silently reassigns A1/A2 to whichever allele is major *in the uploaded sample*, discarding the original REF/ALT convention before `check_allele_harmonization` ever sees the data. This made even the untouched positive-control trio fail harmonization (24% spurious "swapped" rate) — a well-harmonized upload could be rejected purely as an artifact of the platform's own QC step, not a real problem with the user's data. Confirmed root cause by reproducing the exact flip count manually with plink before fixing.

## How this was tested, and what that does/doesn't prove

**What actually ran:** a full, separate copy of the stack (Postgres, Redis,
MailHog, backend, worker, beat — not frontend/Caddy) built from this
branch's own Dockerfiles and brought up under its own compose project
(`dietnet-test`), completely isolated from whatever's already deployed.
Every check drove it exactly the way a real user would: HTTP calls straight
against the FastAPI backend (signup → verify via a real link parsed out of
a real MailHog-captured email → login → multipart upload → poll `/jobs/{id}`
→ download), with the real Celery worker picking real jobs off the real
Redis-backed queue and running the real PLINK binaries and the real
15-model `infer.sh` ensemble against the real 1000G `dataTest/` data — no
mocking anywhere in that path.

**What it doesn't cover:**
- **The frontend was never touched.** Nothing here loaded the SvelteKit UI
  or a browser; every request bypassed it and hit the API directly. It
  validates backend/worker correctness, not the actual page flow.
- **Not the currently-deployed instance.** This ran against a freshly
  built image from the current working tree (including the three fixes
  above, and everything else already modified on this branch per
  `git status`) — not the image already running on the live server, which
  predates those fixes and hasn't been rebuilt/redeployed with them.
- **Infra differences.** No TLS/Caddy, no real SMTP relay (MailHog stood
  in), no real Turnstile CAPTCHA (disabled), same physical host as the
  live deployment but not necessarily the same instance size/resources as
  the actual `flavorName` DEPLOYMENT.md targets.
- **VCF/bgen paths unverified end-to-end.** Only the PLINK upload path was
  exercised with real data. The `--real-ref-alleles` fix to
  `convert_vcf_to_plink` follows directly from plink1.9's documented
  default behavior (verified via `plink --help`, same flag, same default),
  but wasn't re-run through a real VCF upload here. `convert_bgen_to_plink`
  was deliberately left unchanged — plink2's bgen import already respects
  the file's own REF/ALT encoding via `ref-first`, so it isn't subject to
  the same bug, but that reasoning wasn't validated against a real `.bgen`
  file either.
- **Concurrency defaults only partly stress-tested.** 2c/3/4 needed
  `MAX_SAMPLES`/`MAX_UPLOAD_MB`/`CELERY_WORKER_CONCURRENCY` temporarily
  lowered to make the checks fast/observable; the download-concurrency test
  is the only one that ran at its real production default (9).
- **Fixes are uncommitted.** All three bug fixes are local working-tree
  changes, not yet committed or deployed anywhere.

So: passing here is strong evidence the *backend + worker logic* is
correct — it's about as close to "real" as testing gets short of hitting
the actual deployment — but it isn't proof the live platform, as currently
running, behaves the same way, since that instance hasn't picked up these
fixes yet, and the frontend/infra layer wasn't exercised at all.
