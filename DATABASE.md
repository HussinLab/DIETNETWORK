# Database architecture

This document explains how the backend, worker, and Postgres relate to each
other through SQLAlchemy and Alembic, and describes the current schema.
Read alongside [DEPLOYMENT.md](../DEPLOYMENT.md) for how the containers
that run this fit together.

## The three pieces, and how they connect

```
backend/app/models.py (SQLAlchemy, async)  ──┐
                                              ├──describes──▶ desired schema
worker/worker/db.py (SQLAlchemy, sync)     ──┘

        │  alembic revision --autogenerate  (diffs desired vs actual)
        ▼
backend/alembic/versions/*.py   ── migration scripts, committed to git,
                                    each pointing at the previous one ──
        │
        │  alembic upgrade head  (runs in docker-entrypoint.sh, every boot)
        ▼
Postgres  ── actual schema, tracked via its own alembic_version table ──
```

**Postgres** just stores rows; it has no notion of Python or of the app.

**SQLAlchemy** is the Python-side ORM. `backend/app/models.py` defines
classes like `Job` and maps them to columns/types. It lets the app read and
write rows as Python objects, and it's the *source of truth* for what the
schema is supposed to look like — but on its own it does **not** keep
Postgres in sync with that description over time. (An earlier version of
this app called `Base.metadata.create_all()` on boot, which only creates
*missing* tables; it can never alter something that already exists — see
"Past incident" below.)

**Alembic** closes that gap. It:

1. Diffs `models.py` against the live Postgres schema
   (`alembic revision --autogenerate -m "..."`, run manually when you
   change a model).
2. Writes the diff as a versioned Python script under
   `backend/alembic/versions/`, each one naming the previous revision it
   builds on — a linear, ordered chain.
3. Tracks which revisions a given database has already applied, in a table
   it owns (`alembic_version` — currently holds one row, the current head).
4. Applies whatever hasn't been applied yet (`alembic upgrade head`). This
   is safe to run on every container start (it's a no-op if nothing's
   pending), which is exactly what
   [`backend/docker-entrypoint.sh`](docker-entrypoint.sh) does before
   `uvicorn` starts, in every environment.

### Why this is the standard approach

The problem it solves: a schema change and the code change that depends on
it need to travel together, in the same commit, applied in the same order
everywhere — not as a manual step someone might forget on a given server.

- **Reproducible**: replaying every migration from empty always produces
  the same schema, in dev, staging, and prod alike.
- **Ordered**: each migration's `down_revision` fixes exactly one valid
  application order.
- **Reviewable**: a schema change shows up as a diff in the PR, not as a
  side effect discovered later by a failing request.
- **Safe to run unconditionally**: `alembic upgrade head` on every boot
  means there's no "did someone run the migration on prod?" step to miss.

### Where to look when changing the schema

1. Edit `backend/app/models.py`.
2. `cd backend && alembic revision --autogenerate -m "describe the change"`
   (needs a reachable Postgres — run it inside the backend container, or
   against a local DB via `DATABASE_URL_SYNC`).
3. Read the generated file in `alembic/versions/` — autogenerate is a
   starting point, not always correct (it won't detect a column rename, for
   instance; it'll see that as a drop + add).
4. Commit the migration file alongside the model change. It applies
   automatically on next deploy.

### Known gotcha: the worker keeps its own mirror of the schema

Celery tasks run outside FastAPI's async event loop, so
`worker/worker/db.py` talks to Postgres with a separate, synchronous
SQLAlchemy setup (`psycopg2` instead of `asyncpg`) — it is **not** the same
`Base`/models as `backend/app/models.py`, just a hand-written mirror of the
same tables. **Alembic and the backend's models are the only source of
truth for the actual schema**; the worker's copy has to be kept in sync by
hand whenever a table it touches (`users`, `jobs`) changes shape. This is
exactly what caused the second incident below — the mirror declared a
column as generic `String` when the real column is Postgres `uuid`, and the
two SQLAlchemy setups silently disagreed about what Python type a value
should come back as.

## Past incidents (why the above matters in practice)

**1. Missing enum value never reached the DB.** `plink` was added to the
`InputType` enum in `models.py`, but the app only ran
`Base.metadata.create_all()` on boot, which never alters an existing type.
The live DB's `inputtype` enum stayed `{vcf, bgen}`, so every PLINK upload
failed at insert time with `invalid input value for enum inputtype:
"plink"` — a 500 after the full file had already uploaded. Fixed by
patching the enum directly, then adopting Alembic (this doc) so a model
change like this ships a migration instead of silently not applying.

**2. Worker's schema mirror disagreed on a column type.** `worker/db.py`
declared `Job.id` and `Job.user_id` as plain `String`, but the real Postgres
columns are `uuid`. `psycopg2` auto-converts `uuid` columns to Python
`uuid.UUID` objects unless SQLAlchemy is explicitly told the real column
type (via `sqlalchemy.dialects.postgresql.UUID`) — a generic `String`
mapping doesn't override that. So `job.id`/`job.user_id` came back as
`UUID` objects, and `os.path.join(settings.data_root, job.user_id, job.id,
"results")` crashed with `TypeError: join() argument must be str, bytes,
or os.PathLike object, not 'UUID'`. Fixed by mapping those columns with
`UUID(as_uuid=False)` in `worker/db.py`, matching `backend/app/models.py`.

## Schema

Five tables, all defined in `backend/app/models.py` (worker's
`worker/db.py` mirrors `users` and `jobs` only — see gotcha above).

### `users`

| column | type | notes |
|---|---|---|
| `id` | `uuid` | PK |
| `email` | `varchar(320)` | unique, indexed |
| `password_hash` | `varchar(255)` | |
| `is_verified` | `bool` | email verification gate |
| `is_active` | `bool` | |
| `consented_at` | `timestamptz`, nullable | data-processing consent |
| `created_at` | `timestamptz` | |

### `email_verification_tokens`

| column | type | notes |
|---|---|---|
| `id` | `uuid` | PK |
| `user_id` | `uuid` | FK → `users.id`, `ON DELETE CASCADE` |
| `token_hash` | `varchar(255)` | unique |
| `expires_at` | `timestamptz` | |
| `used_at` | `timestamptz`, nullable | |
| `created_at` | `timestamptz` | |

### `refresh_tokens`

| column | type | notes |
|---|---|---|
| `id` | `uuid` | PK |
| `user_id` | `uuid` | FK → `users.id`, `ON DELETE CASCADE` |
| `token_hash` | `varchar(255)` | unique |
| `expires_at` | `timestamptz` | |
| `revoked_at` | `timestamptz`, nullable | |
| `created_at` | `timestamptz` | |

### `jobs`

The core table — one row per inference run.

| column | type | notes |
|---|---|---|
| `id` | `uuid` | PK |
| `user_id` | `uuid` | FK → `users.id`, `ON DELETE CASCADE` |
| `status` | enum `jobstatus` | `queued` \| `running` \| `done` \| `failed` |
| `input_type` | enum `inputtype` | `vcf` \| `bgen` \| `plink` |
| `raw_path` | `varchar(1024)`, nullable | filesystem path to the uploaded genotype file(s); set null after cleanup |
| `results_path` | `varchar(1024)`, nullable | path to the parsed predictions file |
| `raw_deleted_at` | `timestamptz`, nullable | when the raw upload was purged (see `delete_raw_after_success` / retention) |
| `snp_overlap_count` | `int`, nullable | SNPs in the upload that overlap the model's reference panel |
| `snp_overlap_total` | `int`, nullable | reference panel size |
| `is_reliable` | `bool`, nullable | `snp_overlap_count >= min_reliable_snp_overlap` — surfaced to the user whenever predictions are shown |
| `predictions` | `json`, nullable | `{"rows": [...]}`, per-sample ancestry predictions |
| `error_message` | `text`, nullable | sanitized, user-facing only — never a raw traceback (see `worker/tasks.py`) |
| `created_at` / `started_at` / `completed_at` / `purged_at` | `timestamptz`, nullable except `created_at` | job lifecycle timestamps |

Filesystem layout for a job's files: `{data_root}/{user_id}/{job_id}/raw/...`
and `.../results/...` (`data_root` defaults to `/data`, mounted from the
host/cloud volume — see `docker-compose.yml`).

### `audit_log`

Minimal audit trail for auth/data-access events (PIPEDA / Law 25).

| column | type | notes |
|---|---|---|
| `id` | `uuid` | PK |
| `user_id` | `varchar(64)`, nullable | not a FK — events can predate/outlive a user record |
| `event` | `varchar(64)` | e.g. `login_success`, `login_failed`, `job_created` |
| `ip_address` | `varchar(64)`, nullable | |
| `detail` | `text`, nullable | |
| `created_at` | `timestamptz` | |

## Connection setup

- **Backend** (`backend/app/database.py`): async engine via `asyncpg`,
  `DATABASE_URL` (`postgresql+asyncpg://...`). Used for all FastAPI request
  handling.
- **Worker** (`worker/worker/db.py`): sync engine via `psycopg2`,
  `DATABASE_URL_SYNC` (`postgresql+psycopg2://...`). Used because Celery
  tasks run outside the asyncio event loop.
- **Alembic** (`backend/alembic/env.py`): also sync, via `psycopg2`, reusing
  the same `DATABASE_URL_SYNC` setting — one source of truth for DB
  credentials across all three.

Both URLs point at the same Postgres database; only the driver differs.
