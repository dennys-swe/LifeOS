from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, case_sensitive=False, extra="ignore")

    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/finance_db"
    secret_key: str = "insecure-dev-secret-change-me"
    cors_origins: str = "http://localhost:5173"
    cron_secret: str | None = None

    pluggy_client_id: str | None = None
    pluggy_client_secret: str | None = None

    vapid_private_key: str | None = None
    vapid_public_key: str | None = None
    vapid_claims_email: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
