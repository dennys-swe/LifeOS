from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


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
