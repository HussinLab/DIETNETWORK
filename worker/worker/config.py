import os


def _bool(name: str, default: str) -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes", "on")


class Settings:
    # --- Celery / Redis ---
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # --- Database (sync driver -- Celery tasks run in worker threads/processes) ---
    database_url_sync: str = os.environ.get(
        "DATABASE_URL_SYNC", "postgresql+psycopg2://dietnet:dietnet@localhost:5432/dietnet"
    )

    # --- Storage ---
    data_root: str = os.environ.get("DATA_ROOT", "/data")
    retention_days: int = int(os.environ.get("RETENTION_DAYS", "30"))
    delete_raw_after_success: bool = _bool("DELETE_RAW_AFTER_SUCCESS", "true")

    # --- Tools baked into the worker image ---
    plink_path: str = os.environ.get("PLINK_PATH", "/opt/plink/plink")
    plink2_path: str = os.environ.get("PLINK2_PATH", "/opt/plink2/plink2")

    # --- Diet Network code + downloaded model/SNP files (baked into image, read-only) ---
    dietnet_code_path: str = os.environ.get("DIETNET_CODE_PATH", "/opt/dietnet/Dietnet_inference")
    dietnet_files_path: str = os.environ.get("DIETNET_FILES_PATH", "/opt/dietnet/files")

    # SNP overlap below this threshold => job is rejected before the ensemble
    # runs (checked in a fast pre-flight pass -- see pipeline.check_snp_overlap).
    min_reliable_snp_overlap: int = int(os.environ.get("MIN_RELIABLE_SNP_OVERLAP", "1000"))

    # Fraction of overlapping SNPs allowed to disagree in allele coding
    # (swapped/strand-flipped vs the reference panel) before the job is
    # rejected as systematically mis-harmonized -- see
    # pipeline.check_allele_harmonization. A few genuinely discordant SNPs
    # are normal; a large fraction indicates the whole file needs re-harmonizing.
    max_allele_mismatch_fraction: float = float(os.environ.get("MAX_ALLELE_MISMATCH_FRACTION", "0.05"))

    # --- QC ---
    geno_missingness_threshold: str = os.environ.get("GENO_MISSINGNESS_THRESHOLD", "0.1")

    # Sample-count cap (checked from the converted .fam, right after PLINK
    # conversion -- sample count isn't known for VCF/bgen before that point).
    max_samples: int = int(os.environ.get("MAX_SAMPLES", "10000"))

    # Shown alongside every user-facing rejection/error message.
    github_issues_url: str = os.environ.get(
        "GITHUB_ISSUES_URL", "https://github.com/HussinLab/DIETNETWORK/issues"
    )

    # --- Notification links ---
    frontend_url: str = os.environ.get("FRONTEND_URL", "http://localhost:5173")

    # --- SMTP (same relay config as the API, used for completion/failure emails) ---
    smtp_host: str = os.environ.get("SMTP_HOST", "localhost")
    smtp_port: int = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username: str = os.environ.get("SMTP_USERNAME", "")
    smtp_password: str = os.environ.get("SMTP_PASSWORD", "")
    smtp_from_address: str = os.environ.get("SMTP_FROM_ADDRESS", "no-reply@example.org")
    smtp_use_starttls: bool = _bool("SMTP_USE_STARTTLS", "true")
    app_name: str = os.environ.get("APP_NAME", "Diet Network Ancestry Platform")

    # --- Parallelism for the 15-model ensemble ---
    ensemble_workers: int = int(os.environ.get("ENSEMBLE_WORKERS", "1"))


settings = Settings()
