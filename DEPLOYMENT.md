# Diet Network Ancestry Platform — Deployment Guide

This repo now contains, in addition to the original Diet Network model code
(`Dietnet_inference/`, `Dietnet_train_and_evaluate/`), a full web platform
that lets registered users upload genotype data and get ancestry
predictions from the pretrained inference ensemble. It implements
[deployPlan.md](deployPlan.md). Layout:

```
backend/    FastAPI: auth, email verification, CAPTCHA, upload intake, job API, SMTP
worker/     Celery worker: VCF/bgen -> PLINK -> infer.sh -> parse, + 30-day cleanup task
frontend/   SvelteKit: signup/login, drag-and-drop upload, job dashboard, results view
infra/      Pulumi (Python) program that provisions the stack on Arbutus (OpenStack)
ops/        Zenodo model-file fetch script, systemd-timer alternative to Celery beat
docker-compose.yml, Caddyfile          the runtime stack (Caddy/TLS, frontend, backend,
                                        worker, beat, Postgres, Redis) -- used as-is,
                                        with no overlay, for the Arbutus deploy below
docker-compose.dev.yml                 overlay for a laptop: drops Caddy/TLS, adds MailHog
docker-compose.local-test.yml,
localDeployICM                         overlay + launcher for smoke-testing the real
                                        Caddy/TLS topology on a shared non-Arbutus server
```

Three different things run this compose file, and only one of them is "the same as Compute Canada": the base `docker-compose.yml` alone *is* the Arbutus/production topology, so a laptop or shared-server run either has to drop pieces of it (dev) or can layer on top of it unchanged (local-test) to approximate prod. See "Where this differs from Compute Canada" under each section below.

## Architecture

```
Internet -> Floating IP -> Caddy (TLS) -> SvelteKit (frontend)
                                        -> FastAPI (backend) -> Postgres
                                                              -> Redis -> Celery worker(s)
                                                                          (PLINK convert + infer.sh + parse)
                                                                          -> Encrypted Cinder volume (uploads/results)
```

Postgres and Redis publish no host ports; they're reachable only from
other containers on the compose `internal` network. The worker is
structured so it can move to its own instance later (Redis/Postgres URLs
are already environment-driven) without any code changes — only the
`internal` OpenStack security group and those two env vars would change.

## Critical facts about the model this platform builds on

See `deployPlan.md` for the full list; the two that shape the code the
most:

- The real `infer.sh` argument order is `<plink_path> <dietnet_code_path>
  <dietnet_files_path> <plink_test_prefix> <output_name>` — the README's
  order is wrong. `worker/worker/pipeline.py::run_infer` uses the verified
  order.
- Predictions with SNP overlap under 1000 are unreliable. Rather than just
  flagging this after the fact, `worker/worker/tasks.py` runs a fast
  pre-flight pass (`pipeline.check_snp_overlap`) right after PLINK
  conversion and rejects the job *before* the 15-model ensemble runs,
  reusing the same `--extract dietnet_snps.txt` step `infer.sh` performs
  internally. A completed job's overlap is still stored on the job row
  (`is_reliable`) and surfaced on the job detail page and completion email,
  but it's now guaranteed to already be above the threshold.
- Same pre-flight pass also checks allele harmonization
  (`pipeline.check_allele_harmonization`) against `DN_SNPS/dummy.bim` (the
  reference-allele PLINK set `infer.sh` merges against) and the sample
  count against `MAX_SAMPLES`, rejecting before inference if either the
  alleles look systematically swapped/strand-flipped or the file is over
  10k samples. See the pre-flight checks in `worker/worker/tasks.py` for
  all four (upload-size, sample-count, SNP-overlap, allele-harmonization).

## Local development

```bash
cp .env.example .env          # edit POSTGRES_PASSWORD/JWT_SECRET at minimum
cp frontend/.env.example frontend/.env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This starts everything over plain HTTP without Caddy/TLS, with CAPTCHA
disabled (Cloudflare's public always-pass Turnstile test key is wired in)
and a local MailHog instance so you can view "sent" emails at
http://localhost:8025 instead of configuring a real SMTP relay. The
frontend dev server is at http://localhost:5173, the API at
http://localhost:8000.

Building the `worker` image downloads the ~GB-scale pretrained model
files from Zenodo on first build (`ops/scripts/fetch_zenodo_models.sh`) —
expect the first `docker compose build worker` to take a while; it is not
repeated on every job.

Note: the frontend, worker, and infra pieces were authored but not
`npm install`/`pulumi up`-verified in this environment (no network access
during generation) — run `npm install` in `frontend/` and `pip install -r
requirements.txt` in `infra/` as your first step, and treat first-run
build errors as the normal "wire up a fresh scaffold" pass, not a sign of
a deeper design problem.

**Where this differs from Compute Canada:** the `caddy` container doesn't
run at all here (`profiles: ["disabled-in-dev"]`), so there's no TLS
reverse proxy and no single origin — frontend and backend are two
separate plain-HTTP ports. That's fine for UI/API development but it
doesn't exercise the Caddy config, cookie/CORS behavior across an
origin, or MailHog's absence (a real SMTP relay). Use the local-test
setup below when you need to validate closer to what actually runs on
Arbutus.

## Local test deploy on a shared server (e.g. ICM)

```bash
cp .env.example .env   # edit POSTGRES_PASSWORD/JWT_SECRET/SMTP_HOST at minimum
./localDeployICM
```

This is the middle ground between the dev overlay above and a real
Arbutus deploy: it runs `docker-compose.yml` with the
`docker-compose.local-test.yml` overlay
(`docker compose -f docker-compose.yml -f docker-compose.local-test.yml up --build -d`,
which is what [localDeployICM](localDeployICM) wraps), keeping the **real
production topology** — Caddy terminating TLS in front of
frontend+backend, Postgres/Redis reachable only on the internal network —
instead of dropping it like the dev overlay does. It exists for testing
on a shared, non-Arbutus box that already runs other projects' containers
on the default ports: Caddy's host ports move to 8080/8443 (set directly
in `docker-compose.yml`, since Compose appends rather than replaces
list-type keys like `ports` across `-f` files — remapping them from an
overlay wouldn't work), and MailHog + a CAPTCHA test key stand in for a
real SMTP relay and Turnstile keys, the same as in dev.

**Where this differs from Compute Canada:** only the port numbers (8080/8443
vs 80/443), the self-signed Caddy-internal cert (vs a real Let's Encrypt
cert — see the Caddyfile's ACME email/domain handling), MailHog instead of
a real SMTP relay, and CAPTCHA disabled. The container topology itself —
which services exist and how they talk to each other — is identical to
Arbutus. Tear down with `./localDeployICM down`.

## Deploying to Arbutus with Pulumi

```bash
cd infra
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp clouds.yaml.example clouds.yaml        # fill in an Application Credential
export OS_CLIENT_CONFIG_FILE=$(pwd)/clouds.yaml

pulumi stack init arbutus
cp Pulumi.arbutus.yaml.example Pulumi.arbutus.yaml   # edit non-secret values

pulumi config set --secret dbPassword "$(openssl rand -base64 32)"
pulumi config set --secret jwtSecret "$(openssl rand -base64 48)"
pulumi config set --secret smtpHost smtp.your-relay.example.org
pulumi config set --secret smtpUsername your-smtp-user
pulumi config set --secret smtpPassword your-smtp-password
pulumi config set --secret turnstileSecretKey your-turnstile-secret
pulumi config set --secret turnstileSiteKey your-turnstile-site-key

pulumi up
```

`pulumi up` provisions (or reuses) the network, two least-privilege
security groups, an encrypted Cinder volume, a keypair, a floating IP, and
one CPU VM whose cloud-init (`infra/cloud-init/user_data.sh.tmpl`) installs
Docker, mounts the volume at `/mnt/data`, clones this repo, writes `.env`
from your Pulumi config, and runs `docker compose up -d --build`. First
boot takes a while (Docker install + image builds + Zenodo model
download); watch progress with:

```bash
ssh -i <key> ubuntu@$(pulumi stack output floating_ip) 'tail -f /var/log/dietnet-bootstrap.log'
```

### Pointing at a different Arbutus project

Create a new stack (`pulumi stack init <name>`), point `clouds.yaml` /
`OS_CLIENT_CONFIG_FILE` at that project's Application Credential, and set
that stack's config independently — `externalNetworkName`, `imageName`,
`flavorName`, and `volumeType` are all project-specific (check with
`openstack network list --external`, `openstack image list`, `openstack
flavor list`, `openstack volume type list` against that project).

### Config & secrets reference

| Key | Secret? | Notes |
|---|---|---|
| `adminCidr` | no | Your IP/CIDR for SSH — never `0.0.0.0/0` |
| `externalNetworkName` | no | Arbutus provider network name for the floating IP pool |
| `keypairPublicKey` | no | Your SSH public key |
| `imageName` / `flavorName` | no | Verify against your project's catalog; start ~8 vCPU/16-32GB, tune down after measuring |
| `volumeSizeGb` / `volumeType` | no | `volumeType` must be an *encrypted* type |
| `gitRepoUrl` / `gitRef` | no | What cloud-init clones/deploys |
| `domain` / `acmeEmail` | no | Leave `domain` blank to get a self-signed cert on the floating IP |
| `dbPassword`, `jwtSecret`, `smtpHost`, `smtpUsername`, `smtpPassword`, `turnstileSecretKey`, `turnstileSiteKey` | **yes** | `pulumi config set --secret ...` only |

Nothing sensitive is ever committed — `.env`, `clouds.yaml`, and
`Pulumi.<stack>.yaml` are all gitignored; only the `.example` templates
are tracked.

## Concurrency caps (single-VM disk headroom)

The base volume is provisioned at a fixed size (`volumeSizeGb`, default
150GB above but tunable, and the original design point was a 10GB
instance) shared by uploads, in-flight processing, and downloaded results,
so two independent caps keep concurrent activity from overrunning it:

- **Processing** — `CELERY_WORKER_CONCURRENCY` (default 9) caps how many
  `run_inference_job` tasks run at once; the rest sit in the already-FCFS
  Redis/Celery queue (`worker/Dockerfile`'s CMD reads it at container
  start). The queue-position shown on the job detail page and the
  job-started email (`worker/worker/email.py`) are the user-facing side of
  this. The Diet Network ensemble is CPU-only (`deployPlan.md`), so this is
  as much a CPU-contention knob as a disk one — tune it against measured
  load on your `flavorName`, not just the disk math.
- **Downloads** — `MAX_CONCURRENT_DOWNLOADS` (default 9) caps simultaneous
  result-zip builds/streams (`backend/app/concurrency.py`, a Redis-backed
  sliding-window semaphore). A completed job's results sit on disk
  regardless of the processing cap above, so this is a separate limit, not
  the same 9 jobs. The 10th+ concurrent downloader gets a 429 asking them
  to retry shortly, rather than an email — a zip build/stream is seconds,
  not the multi-minute wait the processing queue can involve.

## Scaling the worker off the web VM

Provision a second instance attached to the same OpenStack network,
expose Postgres/Redis on that network (bind the ports and add the
consuming instance to `internal_sg` — see `infra/security_groups.py`),
and point the worker's `REDIS_URL`/`DATABASE_URL_SYNC` env vars at the new
hosts. No application code changes are required.

## Open items flagged for the PI / project owner

These were called out in `deployPlan.md`'s "Confirm before building"
section. The build above uses documented defaults so nothing is blocked,
but these should be confirmed before going live:

1. **Arbutus project/quota + domain name.** Defaults assume a fresh
   project and a self-signed cert on the floating IP if no `domain` is
   set. Supply the real project's `externalNetworkName`/`imageName`/
   `flavorName` and a domain for a trusted Let's Encrypt cert.
2. **`volumeType` must actually be an encrypted type — verify this
   yourself, nothing in the deploy checks it.** `infra/storage.py`
   requires a `volumeType` name but the Pulumi OpenStack provider has no
   way to look up an existing volume type's properties, so a
   non-encrypted type would deploy without error or warning — this is the
   platform's entire "encrypted at rest" guarantee for uploaded genotype
   data, and it rests on this one manual step. Before `pulumi up`, run
   `openstack volume type show <name>` against your project and confirm
   it carries an encryption association (ask your Alliance support
   contact if the output isn't self-explanatory); don't infer it from the
   type's name alone.
3. **SMTP relay.** Defaults to whatever `smtpHost`/port 587 you configure
   — pick the ICM/UdeM institutional relay or a transactional provider
   and set it via secret config.
4. **bgen without a `.sample` file.** Currently **required** — both
   `backend/app/routers/uploads.py` and the upload UI reject a bgen
   upload with no accompanying `.sample`. Relax this only if you can
   source sample IDs another way.
5. **REB / privacy sign-off.** Not a code question — confirm with your
   institution's Research Ethics Board and privacy/security officer
   before accepting real user genotype data. This platform implements
   the technical controls (consent capture, encryption, 30-day deletion,
   audit logging, data residency) but does not substitute for that
   review.
