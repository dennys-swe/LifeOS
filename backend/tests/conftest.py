import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.users import current_active_user
from app.db.database import Base
from app.db.database import get_db
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
