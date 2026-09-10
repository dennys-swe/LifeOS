from __future__ import annotations

import logging

import app.core.observability as observability
from app.core.observability import configure_logging, init_sentry


def test_configure_logging_is_idempotent(monkeypatch):
    monkeypatch.setattr(observability, "_logging_configured", False)
    configure_logging()
    configure_logging()  # segunda chamada não pode duplicar handler nem levantar


def test_configure_logging_respects_log_level(monkeypatch):
    original_level = logging.getLogger().level
    monkeypatch.setattr(observability, "_logging_configured", False)
    monkeypatch.setattr(observability.settings, "log_level", "WARNING")
    try:
        configure_logging()
        assert logging.getLogger().level == logging.WARNING
    finally:
        logging.getLogger().setLevel(original_level)


def test_init_sentry_is_noop_without_dsn(monkeypatch):
    monkeypatch.setattr(observability, "_sentry_configured", False)
    monkeypatch.setattr(observability.settings, "sentry_dsn", None)
    init_sentry()  # sem DSN: não importa o SDK, não levanta
    assert observability._sentry_configured is False


def test_init_sentry_initializes_when_dsn_present(monkeypatch):
    calls = {}

    def fake_init(**kwargs):
        calls.update(kwargs)

    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    monkeypatch.setattr(observability, "_sentry_configured", False)
    monkeypatch.setattr(observability.settings, "sentry_dsn", "https://k@o0.ingest.sentry.io/1")
    monkeypatch.setattr(observability.settings, "environment", "staging")

    init_sentry()

    assert calls["dsn"] == "https://k@o0.ingest.sentry.io/1"
    assert calls["environment"] == "staging"
    assert calls["send_default_pii"] is False
    assert observability._sentry_configured is True
