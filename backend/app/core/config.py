from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, case_sensitive=False, extra="ignore")

    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/finance_db"

    # Ambiente lógico: "development" | "staging" | "production". Dirige o guard
    # de banco de produção (ver app/db/database.py) e o environment reportado ao
    # Sentry. Produção seta ENVIRONMENT=production explicitamente.
    environment: str = "development"
    # Escape hatch consciente: permite o backend subir contra um banco gerenciado
    # (Neon) mesmo fora de production. Para leitura pontual de produção.
    allow_prod_db: bool = False

    secret_key: str = "insecure-dev-secret-change-me"
    cors_origins: str = "http://localhost:5173"
    cron_secret: str | None = None

    # Observabilidade. Sem SENTRY_DSN o Sentry fica desligado (dev e testes).
    # O environment reportado ao Sentry é `self.environment`.
    sentry_dsn: str | None = None
    log_level: str = "INFO"

    pluggy_client_id: str | None = None
    pluggy_client_secret: str | None = None
    # Segredo no path da webhook: POST /webhooks/pluggy/<secret>. Quando setado,
    # o path sem segredo passa a ser no-op. Ver app/api/endpoints/webhooks.py.
    pluggy_webhook_secret: str | None = None

    vapid_private_key: str | None = None
    vapid_public_key: str | None = None
    vapid_claims_email: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
