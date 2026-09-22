import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, TypeVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Antes de importar `app.*`: a suíte roda contra SQLite em memória (cada teste
# monta o seu). Fixar aqui garante que, mesmo que um `backend/.env` local
# aponte para o Postgres de produção, nenhum teste toque nele — e o guard de
# produção de `app/db/database.py` não dispara na coleta.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.users import current_active_user
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    # Jobs em background (ex: sync bancário) abrem sua própria sessão via
    # `app.services.bank_sync_service.SessionLocal` em vez da dependency
    # `get_db` — sem isso, um teste que dispara esse job em background
    # (o TestClient roda BackgroundTasks de forma síncrona) acabaria batendo
    # no Postgres real de produção em vez do SQLite isolado do teste.
    from app.services import bank_sync_service

    monkeypatch.setattr(bank_sync_service, "SessionLocal", SessionLocal)

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@contextmanager
def raw_test_client(db_session):
    """TestClient sem override de `current_active_user` — exercita o fluxo
    real de auth (register/login/JWT). Compartilhado entre `test_auth.py` e
    `test_rate_limit.py`."""

    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _make_user(db_session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="not-used-in-tests",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def user(db_session) -> User:
    return _make_user(db_session, "dono@example.com")


@pytest.fixture()
def other_user(db_session) -> User:
    return _make_user(db_session, "outro@example.com")


_T = TypeVar("_T")


def count_select_queries(db_session, fn: Callable[[], _T]) -> tuple[_T, list[str]]:
    """Roda `fn()` e devolve `(resultado, lista de SELECTs emitidos)` — usado
    pelas guardas de contagem de query contra regressão de N+1 (issue #134;
    ver também `test_sync_n_plus_one.py`, que filtra por um SELECT específico
    em vez de todos)."""
    engine = db_session.get_bind()
    statements: list[str] = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        if " ".join(statement.split()).upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _listener)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", _listener)
    return result, statements


@pytest.fixture()
def client(db_session, user):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[current_active_user] = lambda: user
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
