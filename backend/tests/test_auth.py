from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app
from app.services.category_seed import DEFAULT_CATEGORIES


@pytest.fixture()
def raw_client(db_session):
    """Client sem override de current_active_user — exercita o fluxo real de auth."""

    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register(raw_client, email="dono@example.com", password="Sup3rSecreta!"):
    return raw_client.post("/auth/register", json={"email": email, "password": password})


def _login(raw_client, email="dono@example.com", password="Sup3rSecreta!"):
    return raw_client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
    )


def test_register_creates_user_and_seeds_categories(raw_client, db_session):
    response = _register(raw_client)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "dono@example.com"
    assert "hashed_password" not in data

    from app.models.category import Category

    categories = db_session.query(Category).all()
    names = {c.name for c in categories}
    assert names == {c["name"] for c in DEFAULT_CATEGORIES}
    assert all(str(c.user_id) == data["id"] for c in categories)


def test_register_duplicate_email_returns_400(raw_client):
    _register(raw_client)
    response = _register(raw_client)
    assert response.status_code == 400


def test_login_returns_jwt_and_users_me_works(raw_client):
    _register(raw_client)
    login_response = _login(raw_client)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert token

    me_response = raw_client.get(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "dono@example.com"


def test_login_wrong_password_returns_400(raw_client):
    _register(raw_client)
    response = _login(raw_client, password="senha-errada")
    assert response.status_code == 400


def test_unauthenticated_request_is_rejected(raw_client):
    response = raw_client.get("/payables")
    assert response.status_code == 401


def test_two_real_users_do_not_see_each_others_payables(raw_client):
    _register(raw_client, email="ana@example.com")
    token_ana = _login(raw_client, email="ana@example.com").json()["access_token"]

    _register(raw_client, email="bruno@example.com")
    token_bruno = _login(raw_client, email="bruno@example.com").json()["access_token"]

    headers_ana = {"Authorization": f"Bearer {token_ana}"}
    headers_bruno = {"Authorization": f"Bearer {token_bruno}"}

    create_resp = raw_client.post(
        "/payables",
        json={
            "title": "Conta da Ana",
            "amount": 100.0,
            "due_date": "2026-08-10",
            "status": "PENDING",
        },
        headers=headers_ana,
    )
    assert create_resp.status_code == 201
    payable_id = create_resp.json()["id"]

    ana_list = raw_client.get("/payables", headers=headers_ana).json()
    assert any(p["id"] == payable_id for p in ana_list)

    bruno_list = raw_client.get("/payables", headers=headers_bruno).json()
    assert not any(p["id"] == payable_id for p in bruno_list)

    bruno_delete = raw_client.delete(f"/payables/{payable_id}", headers=headers_bruno)
    assert bruno_delete.status_code == 404
