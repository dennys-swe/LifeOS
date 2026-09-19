from __future__ import annotations

import asyncio
import logging

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app, request_timing


def test_request_timing_logs_duration(caplog):
    with caplog.at_level(logging.INFO, logger="app.timing"):
        with TestClient(app) as client:
            response = client.get("/")

    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == "app.timing"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert records[0].getMessage().startswith("GET / -> 200 ")


def test_request_timing_logs_warning_when_slow(caplog, monkeypatch):
    monkeypatch.setattr(settings, "slow_request_threshold_ms", 0)
    with caplog.at_level(logging.INFO, logger="app.timing"):
        with TestClient(app) as client:
            response = client.get("/")

    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == "app.timing"]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING


def test_request_timing_logs_even_when_call_next_raises(caplog):
    """Um request que estoura exceção (timeout, crash) não pode sumir do log
    de timing — é justamente o pior caso que o perfil de latência precisa
    capturar."""
    request = Request({"type": "http", "method": "GET", "path": "/boom", "headers": []})

    async def boom(_request):
        raise RuntimeError("simulated crash")

    with caplog.at_level(logging.INFO, logger="app.timing"), pytest.raises(RuntimeError):
        asyncio.run(request_timing(request, boom))

    records = [r for r in caplog.records if r.name == "app.timing"]
    assert len(records) == 1
    assert records[0].getMessage().startswith("GET /boom -> ERR ")
