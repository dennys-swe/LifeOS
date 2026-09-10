import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.database_url

url = make_url(DATABASE_URL)

# Sufixos de host de banco gerenciado que só devem ser tocados em produção.
# O `.env` local apontava para o Neon de produção, então rodar o backend na
# máquina (ou um teste que não sobrescreve `get_db`) escrevia nos dados
# financeiros reais. Ver issue #4.
_MANAGED_DB_HOST_SUFFIXES = (".neon.tech",)


def _guard_production_db(db_url: URL, *, environment: str, allow_prod_db: bool) -> None:
    if environment == "production":
        return

    host = (db_url.host or "").lower()
    if not host.endswith(_MANAGED_DB_HOST_SUFFIXES):
        return

    if allow_prod_db:
        logger.warning(
            "DATABASE_URL aponta para um banco gerenciado (%s) com ENVIRONMENT=%s — "
            "liberado por ALLOW_PROD_DB",
            host,
            environment,
        )
        return

    raise RuntimeError(
        f"DATABASE_URL aponta para um banco gerenciado ({host}) mas ENVIRONMENT={environment!r}. "
        "Isso quase certamente é o banco de produção. Suba um Postgres local "
        "(`docker compose up -d db`) ou, se realmente precisar ler produção, "
        "defina ALLOW_PROD_DB=1."
    )


_guard_production_db(url, environment=settings.environment, allow_prod_db=settings.allow_prod_db)

connect_args = {}

if url.get_backend_name() == "postgresql":
    if "sslmode" not in url.query:
        connect_args = {"sslmode": "require"}
    else:
        connect_args = {"sslmode": url.query["sslmode"]}

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
