# Diet Network Ancestry Inference Web Platform

## Role and objective

You are building and deploying a production web platform that lets registered users upload their own genotype data and receive **genetic ancestry predictions** from the pretrained **Diet Network** ensemble (HussinLab). The platform runs **inference only** — it never retrains or fine-tunes the model. Deployment target is the **Arbutus cloud** (Digital Research Alliance of Canada / former Compute Canada OpenStack), provisioned entirely as code with **Pulumi**. The frontend is a **SvelteKit** app with polished, modern UI.

Repository to deploy: `https://github.com/HussinLab/DIETNETWORK` (use the `Dietnet_inference/` directory only).

---

## Critical facts about the model (read before designing anything)

These come from inspecting the actual repo and will save you from wrong assumptions:

1. **The model does NOT accept VCF or bgen directly.** It requires **PLINK 1.9 binary format** (`.bed/.bim/.fam`), with genotypes **harmonized to GRCh38** and ideally filtered for missingness (drop SNPs with >10% missing). Your platform accepts VCF/bgen from users and must **convert to PLINK first** (see Inference Pipeline). This conversion step is the single most important piece of glue you are writing.

2. **Inference is CPU-only and lightweight.** The model is a small MLP ensemble; `requirements.txt` pins `torch==2.10.0` but there is **no need for a GPU flavor**. Install the CPU build of PyTorch. This keeps the Arbutus footprint and cost low. Do not request GPU quota.

3. **It is an ensemble of 15 models** (5 folds x 3 repeats). `infer.sh` loops over them sequentially, each a separate `python inference.py` call. A single job therefore takes minutes, not seconds — this is why the platform needs an **async job queue**, not synchronous request handling.

4. **The real `infer.sh` argument order differs from the README.** Trust the script, not the README. The actual signature is:
   ```
   bash infer.sh <plink_path> <dietnet_code_path> <dietnet_files_path> <plink_test_prefix> <output_name>
   ```
   - `plink_path` — path to the PLINK 1.9 executable
   - `dietnet_code_path` — path to `Dietnet_inference/` (the Python scripts)
   - `dietnet_files_path` — path to the downloaded model files (containing `DN_SNPS/` and `DN_MODELS/`)
   - `plink_test_prefix` — prefix of the user's converted PLINK dataset
   - `output_name` — output prefix

5. **Pretrained weights and SNP files come from Zenodo**, record `16943452` (`DN_MODELS/` and `DN_SNPS/`). These are downloaded **once at image/volume build time**, never per request. Do not fetch them at runtime.

6. **Primary output** is `<output_name>_dietnet_predictions.txt` (tab-delimited: each sample with predicted ancestry across the 15 models; 24 possible populations, trained on 1000 Genomes). Per-model `.npz` files with softmax scores and embeddings are also produced.

7. **Surface the reliability caveat.** The tool warns that predictions should be discarded when the SNP overlap with the Diet Network SNP set is **under 1000 SNPs**. The final results screen and the completion email must show the overlap count and flag low-overlap results as unreliable.

8. **Python 3.11.5** with the exact pins in `Dietnet_inference/dietnet_infer_python3115_requirements.txt`. **PLINK v1.9** required; add **PLINK2** as well, since bgen conversion needs it.

---

## Target architecture

Keep the web tier and the compute tier separate so long-running inference never blocks HTTP requests.

```
            Internet
               |
         [ Floating IP ]
               |
        +--------------+        Arbutus project (OpenStack)
        |  Caddy (TLS) |  <- Let's Encrypt, reverse proxy
        +--------------+
          |          |
   +-------------+  +------------------+
   | SvelteKit   |  |  FastAPI backend |  <- auth, uploads, job submit, results
   | (frontend)  |  +------------------+
   +-------------+        |        |
                          |        +---> [ PostgreSQL ]  (users, jobs, file metadata + timestamps)
                          |
                    [ Redis broker ]
                          |
              +------------------------+
              |  Inference worker(s)   |  <- Celery/RQ; PLINK convert + infer.sh + parse
              |  DietNetwork + models  |     (models baked in, read-only)
              +------------------------+
                          |
              [ Encrypted Cinder volume ]  <- per-user uploads + results, 30-day lifecycle
```

Recommended packaging: **Docker Compose** on the VM(s), brought up by cloud-init that Pulumi injects. For a first deployment a **single well-sized VM** running all containers is acceptable; structure the compose file so the worker can later move to its own instance without code changes.

---

## Tech stack

- **Frontend:** SvelteKit + TypeScript. Use a component library / design system for a clean look (e.g. shadcn-svelte or Skeleton), sensible empty/loading/error states, drag-and-drop upload with client-side file-type and size checks, a job dashboard showing status (queued / running / done / failed) and a results view.
- **Backend/API:** FastAPI (Python). Chosen so the API and the inference environment share one ecosystem. Handles auth, upload intake, job creation, status, results, and email dispatch.
- **Worker/queue:** Celery (or RQ) with Redis as broker/result backend. One queue for inference jobs.
- **Database:** PostgreSQL.
- **Reverse proxy / TLS:** Caddy (automatic Let's Encrypt) — simplest path to HTTPS. Nginx + certbot is an acceptable alternative.
- **CAPTCHA:** Cloudflare Turnstile (free, privacy-preserving) or hCaptcha.
- **IaC:** Pulumi with the `pulumi_openstack` provider (Python program, to match the rest of the stack).

---

## Feature requirements

### 1. User accounts with validation
- Email + password registration. Hash passwords with **argon2id** (never store plaintext, never use fast/unsalted hashes).
- **Email verification**: on signup, create a single-use, time-limited token, email a verification link, and block login/upload until verified.
- Session management via secure, httpOnly, SameSite cookies (or short-lived JWT + refresh). Enforce password strength and per-account rate limiting on login attempts.
- Do not roll your own crypto; use vetted libraries for hashing and token generation.

### 2. Email notification on completion
- When a job finishes (success or failure), email the user with the outcome, the SNP-overlap count, the low-overlap warning if applicable, and a link to the results page (do not attach raw genetic results to the email).
- **Arbutus caveat:** outbound port 25 is typically blocked on Alliance cloud. Send through an **authenticated SMTP submission relay (port 587)** — your institution's relay (ICM/UdeM) or a transactional email provider. Make SMTP host/credentials a config value, not hardcoded.

### 3. User data storage with 30-day auto-deletion
- Store each user's uploads and results under a per-user path on an **encrypted Cinder volume**, with a DB row recording `user_id`, `job_id`, file paths, and `created_at`.
- Enforce deletion with a **scheduled cleanup job** (systemd timer or a Celery beat task) that runs daily, finds records older than 30 days, deletes the files, and marks the DB row purged. Rely on the DB timestamp as the source of truth, not filesystem mtime.
- **Strongly recommended:** delete the raw uploaded genotype file immediately after inference succeeds, keeping only the derived results for the 30-day window. Raw genotypes are the most sensitive artifact and are not needed once predictions exist. Make this a config toggle if you want, defaulting to on.
- If the project has Swift/S3 object storage available, an object lifecycle rule is an alternative to the cron approach; default to the volume + scheduled job since it is guaranteed available.

### 4. CAPTCHA on login and account creation
- Add a Turnstile/hCaptcha challenge to both the **signup** and **login** forms. Verify the token **server-side** in FastAPI before doing any auth work. Combine with server-side rate limiting so CAPTCHA is defense-in-depth, not the only bot control.

### Input handling (VCF / bgen)
- Accept `.vcf`/`.vcf.gz` and `.bgen` (with optional accompanying `.sample`) uploads. Validate type and size client- and server-side; reject anything else.
- **VCF -> PLINK:** `plink --vcf <file> --make-bed --out <prefix>` (PLINK 1.9).
- **bgen -> PLINK:** `plink2 --bgen <file> ref-first --sample <file.sample> --make-bed --out <prefix>` (PLINK2). Prompt the user for the `.sample` file when a bgen is uploaded.
- **QC:** apply a missingness filter (`--geno 0.1`) and require GRCh38. The platform cannot reliably re-map genome builds, so state the **GRCh38 requirement** explicitly in the UI and validate/warn where possible.

---

## Inference pipeline (per job, on the worker)

1. Receive the converted or raw upload; if VCF/bgen, convert to PLINK `.bed/.bim/.fam` as above.
2. Run QC (missingness filter). Record how many SNPs remain.
3. Run the ensemble:
   ```
   bash Dietnet_inference/infer.sh <plink_exe> <code_path> <models_path> <user_plink_prefix> <output_prefix>
   ```
   using the **actual argument order** noted above.
4. Parse `<output_prefix>_dietnet_predictions.txt` into structured results for the DB / UI.
5. Extract the **SNP overlap count** (the script prints it and writes `<prefix>_dietnetsnps_extractedsnps.txt`); store it and flag results with overlap < 1000 as unreliable.
6. Mark the job complete, trigger the notification email, and (if configured) delete the raw upload.
7. On any failure, capture logs, mark the job failed, and email a failure notice. Never surface raw stack traces to users.

Consider parallelizing the 15 model runs across worker CPUs to cut latency, but validate outputs match the sequential run first.

---

## Pulumi IaC specification (Arbutus)

Write a Pulumi **Python** program that provisions:

- **Auth:** configure the `openstack` provider from an **application credential** (Horizon -> Identity -> Application Credentials) placed in a `clouds.yaml`; reference it via `openstack:cloud`. Do not embed your personal password or commit credentials.
- **Networking:** reuse the project's existing network/subnet/router if present, otherwise create them. Allocate **one floating IP** for the proxy (default quota is small, often ~2).
- **Security groups (least privilege):**
  - 443 and 80 open to the world (80 only for ACME/redirect).
  - 22 restricted to your admin IP/CIDR only.
  - PostgreSQL and Redis: **no ingress from outside**; container-network only.
- **Compute:** an Ubuntu LTS instance with a **CPU flavor** sized for the ensemble (start around 8 vCPU / 16-32 GB RAM; tune down after measuring). Attach the SSH keypair.
- **Storage:** an **encrypted Cinder volume** for user data and the database; mount it for the worker/DB containers. A separate small volume or baked image layer holds the read-only DietNetwork model files.
- **Bootstrap:** cloud-init `user_data` that installs Docker + Compose, mounts the volume, downloads the Zenodo model files (or pulls a prebuilt image that already contains them), writes the compose env from Pulumi config, and brings the stack up.
- **Persistence:** if this is an always-on service, ensure the project uses a **persistent cloud** allocation rather than a reclaimable compute-cloud one.

Manage all secrets (DB password, JWT secret, SMTP credentials, CAPTCHA secret key) via **Pulumi encrypted config** (`pulumi config set --secret`), injected into containers as env vars. Nothing sensitive in the repo.

---

## Security & data governance (do not skip — this is identifiable genetic data)

Uploaded genotypes are **sensitive personal information**. Under Canadian PIPEDA and Quebec's Law 25 (relevant given an ICM/Montreal context), this raises real obligations. Build these in from the start:

- **Consent + privacy policy:** an explicit consent checkbox at upload and a clear policy stating what is collected, why, where it is stored, and the 30-day retention/deletion guarantee.
- **Data residency:** Arbutus is Canadian-hosted — good. Keep all data and backups on Canadian infrastructure.
- **Encryption:** TLS in transit everywhere (Caddy/Let's Encrypt); encryption at rest via encrypted Cinder volumes (or LUKS).
- **Data minimization:** delete raw genotype files as soon as inference completes; retain only derived results within the 30-day window; users can only ever access their own data.
- **Hardening:** argon2id password hashing, server-side CAPTCHA verification, login rate limiting, no public DB/Redis, admin SSH locked to a known IP, audit logging of auth and data-access events, regular OS patching.
- **Process:** confirm whether this platform needs **Research Ethics Board (REB)** review and consult the institution's privacy/security officer before going live. Flag this to the PI rather than assuming it is covered.

---

## Deliverables

1. Pulumi program (Python) that stands up the full Arbutus stack reproducibly from a clean project.
2. Dockerfiles / Compose file for frontend, API, worker, Redis, Postgres, Caddy — with the DietNetwork models baked into the worker image.
3. SvelteKit frontend (auth flows, upload with .sample handling, job dashboard, results view with overlap warning).
4. FastAPI backend (auth + email verification, CAPTCHA verification, upload intake, job API, SMTP notifications).
5. Worker implementing the full VCF/bgen -> PLINK -> `infer.sh` -> parse pipeline.
6. Scheduled 30-day cleanup job.
7. README covering local dev, `pulumi up` deploy, config/secrets, and how to point at a different Arbutus project.

## Confirm before building
- Which Arbutus **project/quota** and whether a **domain name** is available for TLS.
- The **SMTP relay** to use for outbound email (institutional vs external).
- Whether users may upload **bgen without a `.sample`** file (affects conversion UX).
- Whether **REB / privacy** sign-off is required before launch.