import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every field can be set with an ASSAYR_<NAME> environment variable."""

    model_config = SettingsConfigDict(env_prefix="ASSAYR_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./assayr-dev.db"
    secure_cookies: bool = True
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    org_name: str = "My Organization"
    storage_dir: str = "./data/blobs"
    max_upload_mb: int = 100
    clamav_host: str | None = None
    clamav_port: int = 3310
    expiry_warning_days: int = 30
    evidence_grace_days: int = 14
    accept_threshold: float = 0.85
    reject_threshold: float = 0.60
    worker_poll_seconds: float = 2.0
    recompute_interval_minutes: int = 60

    @field_validator("clamav_host", mode="before")
    @classmethod
    def _blank_host_is_none(cls, value):
        return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=os.environ.get("ASSAYR_ENV_FILE", ".env"), _env_file_encoding="utf-8")
