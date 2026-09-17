"""Hardening da issue #7: headers de segurança, CORS restrito e readiness
check que realmente testa o banco (não só o processo)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def _client():
    return TestClient(app)


def test_security_headers_present():
    with _client() as client:
        resp = client.get("/")

    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "max-age=" in resp.headers["strict-transport-security"]
    assert resp.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_csp_is_skipped_on_docs_to_not_break_swagger_ui():
    with _client() as client:
        resp = client.get("/docs")

    assert "content-security-policy" not in resp.headers


def test_root_is_ok_when_db_reachable():
    with _client() as client:
        resp = client.get("/")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_returns_503_when_db_unreachable():
    broken_session = MagicMock()
    broken_session.execute.side_effect = Exception("connection refused")
    broken_session.__enter__.return_value = broken_session
    broken_session.__exit__.return_value = False

    with patch("app.main.SessionLocal", return_value=broken_session):
        with _client() as client:
            resp = client.get("/")

    assert resp.status_code == 503


def test_cors_preflight_only_allows_methods_frontend_uses():
    with _client() as client:
        resp = client.options(
            "/payables",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    allowed = resp.headers.get("access-control-allow-methods", "")
    assert "TRACE" not in allowed
    assert "GET" in allowed
