"""Application configuration loaded from environment variables.

All secrets are read from environment variables / .env files. No secrets
are ever hardcoded in source code.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = "RehabX AI"
    api_prefix: str = "/api/v1"
    debug: bool = False

    # Database
    database_url: str = f"sqlite:///{_REPO_ROOT / 'backend' / 'rehabx.db'}"

    # Security
    secret_key: str = "insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # Rate limiting (disable in tests or when a reverse proxy already throttles)
    rate_limit_enabled: bool = True

    # Storage
    storage_backend: str = "local"  # "local" | "s3"
    storage_dir: str = str(_REPO_ROOT / "backend" / "storage")
    storage_public_url: str = ""
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # Upload limits
    max_upload_bytes: int = 15 * 1024 * 1024
    allowed_upload_types: str = "image/png,image/jpeg,image/jpg"
    max_image_dimension: int = 4096

    # AI inference (backend shells out to the AI CLI)
    ai_inference_cli: str = "python"
    ai_model_root: str = str(_REPO_ROOT / "models")
    ai_classifier_checkpoint: str = str(_REPO_ROOT / "models" / "checkpoints" / "classifier" / "best.pt")
    ai_segmentation_checkpoint: str = str(_REPO_ROOT / "models" / "checkpoints" / "segmentation" / "best.pt")
    ai_inference_timeout_seconds: int = 600

    # Outbound email (SMTP). Empty smtp_host disables sending.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@rehabx.local"
    smtp_use_tls: bool = True
    frontend_base_url: str = "http://localhost:3000"

    # Audit log
    audit_log_path: str = str(_REPO_ROOT / "backend" / "logs" / "audit.log")

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def allowed_types(self) -> set[str]:
        return {t.strip().lower() for t in self.allowed_upload_types.split(",") if t.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_storage_dir(self) -> Path:
        return Path(self.storage_dir).resolve()

    @property
    def resolved_model_root(self) -> Path:
        return Path(self.ai_model_root).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
