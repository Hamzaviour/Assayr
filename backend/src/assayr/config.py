from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
