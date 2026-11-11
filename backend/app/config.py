"""
Central configuration for the FastAPI backend.

Everything sensitive (DB password, JWT secret, SMTP credentials, CAPTCHA
secret key) is read from environment variables only. In production those
env vars are injected into the container by docker-compose from values set
with `pulumi config set --secret` (see infra/__main__.py) -- nothing
sensitive is ever committed to the repo.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "Diet Network Ancestry Platform"
    environment: str = "development"  # development | production
    base_url: str = "http://localhost:8000"          # backend, used in emails
    frontend_url: str = "http://localhost:5173"       # used to build result links
    cors_origins: str = "http://localhost:5173"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://dietnet:dietnet@localhost:5432/dietnet"
    database_url_sync: str = "postgresql+psycopg2://dietnet:dietnet@localhost:5432/dietnet"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14
    email_verification_ttl_hours: int = 48
    cookie_secure: bool = True  # set False only for plain-HTTP local dev
    cookie_domain: str | None = None

    # --- Rate limiting ---
    login_max_attempts: int = 5
    login_window_seconds: int = 300  # 5 minutes
    login_lockout_seconds: int = 900  # 15 minutes

    # --- CAPTCHA (Cloudflare Turnstile) ---
    turnstile_secret_key: str = ""
    turnstile_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    captcha_enabled: bool = True

    # --- SMTP (submission relay, port 587 -- Arbutus blocks outbound 25) ---
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "no-reply@example.org"
    smtp_use_starttls: bool = True

    # --- Storage ---
    data_root: str = "/data"  # per-user uploads/results live under {data_root}/{user_id}/{job_id}
    max_upload_mb: int = 1024  # combined total across all files in one upload, not per-file
    retention_days: int = 30
    delete_raw_after_success: bool = True

    # Shown alongside every user-facing rejection/error message.
    github_issues_url: str = "https://github.com/HussinLab/DIETNETWORK/issues"

    # --- Concurrency (disk headroom on the single-VM deploy) ---
    # Caps simultaneous result-zip builds/downloads -- separate from the
    # worker's processing concurrency (CELERY_WORKER_CONCURRENCY), which
    # bounds how many jobs run at once, not how many results get downloaded
    # at once. See app/concurrency.py.
    max_concurrent_downloads: int = 9
    download_slot_ttl_seconds: int = 600  # self-heals a slot leaked by a crashed request

    # --- Uploads accepted ---
    allowed_genotype_extensions: tuple[str, ...] = (".vcf", ".vcf.gz", ".bgen")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
