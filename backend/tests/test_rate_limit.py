from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.rate_limit import storage
from tests.conftest import raw_test_client


@pytest.fixture()
def raw_client(db_session, monkeypatch):
    """Client sem override de current_active_user, com o rate limit religado.

    `tests/conftest.py` fixa `ENVIRONMENT=test` pra desligar o middleware no
    resto da suíte (mesma IP sintética do TestClient em centenas de
    requests) — aqui religamos só pra este módulo, e limpamos o storage
    entre testes pra um não vazar contagem pro outro.
    """
    monkeypatch.setattr(settings, "environment", "development")
    storage.reset()
    with raw_test_client(db_session) as test_client:
        yield test_client


def _login_attempt(client, headers=None):
    return client.post(
        "/auth/jwt/login",
        data={"username": "nobody@example.com", "password": "errada"},
        headers=headers,
    )


def test_sixth_login_attempt_in_a_minute_is_rate_limited(raw_client):
    for _ in range(5):
        response = _login_attempt(raw_client)
        assert response.status_code == 400  # LOGIN_BAD_CREDENTIALS, não limitado ainda

    response = _login_attempt(raw_client)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_register_is_rate_limited_separately_from_login(raw_client):
    for i in range(5):
        response = raw_client.post(
            "/auth/register",
            json={"email": f"user{i}@example.com", "password": "SenhaForte123!"},
        )
        assert response.status_code == 201

    response = raw_client.post(
        "/auth/register",
        json={"email": "user5@example.com", "password": "SenhaForte123!"},
    )
    assert response.status_code == 429


def test_data_endpoints_are_not_caught_by_the_strict_auth_limit(raw_client):
    for _ in range(5):
        _login_attempt(raw_client)

    # a chave de rate limit de dados ("default:<ip>") é separada da de auth
    # ("auth:<path>:<ip>") — 6 tentativas erradas de login não devem afetar
    # outra rota. "/categories" exige auth (401 sem token), mas isso já basta
    # pra provar que não caiu no bucket de auth (que devolveria 429).
    response = raw_client.get("/categories")
    assert response.status_code == 401


def test_health_check_is_exempt_from_rate_limiting(raw_client):
    for _ in range(120):
        response = raw_client.get("/")
        assert response.status_code == 200


def test_client_supplied_x_forwarded_for_cannot_be_used_to_bypass_the_limit(raw_client):
    # O Render (único proxy no caminho) anexa o IP real como o ÚLTIMO hop do
    # header; qualquer coisa antes é o que o cliente mandou. Se o código
    # confiasse no primeiro valor, bastaria variar esse prefixo a cada
    # request pra nunca bater no mesmo bucket e escapar do rate limit.
    for i in range(5):
        _login_attempt(raw_client, headers={"X-Forwarded-For": f"1.2.3.{i}, 9.9.9.9"})

    response = _login_attempt(raw_client, headers={"X-Forwarded-For": "1.2.3.99, 9.9.9.9"})
    assert response.status_code == 429
