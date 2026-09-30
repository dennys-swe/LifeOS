"""Idade real do dado por conexão (#214): regras puras de `connection_freshness`."""

from datetime import datetime, timedelta

from app.services.connection_freshness import (
    assess_connection_freshness,
    parse_pluggy_datetime,
)

NOW = datetime(2026, 9, 30, 18, 0, 0)


def _assess(**overrides):
    base = dict(
        item_checked_at=NOW,
        item_status="UPDATED",
        item_user_action=None,
        item_last_updated_at=NOW - timedelta(hours=10),
        item_next_auto_sync_at=NOW + timedelta(hours=14),
        consent_expires_at=NOW + timedelta(days=300),
        now=NOW,
    )
    base.update(overrides)
    return assess_connection_freshness(**base)


def test_recent_update_with_scheduled_sync_is_fresh():
    result = _assess()
    assert (result.state, result.reason) == ("fresh", "ok")
    assert result.data_age_hours == 10.0
    assert result.auto_sync_scheduled is True


def test_old_data_without_auto_sync_is_stale():
    """O caso real do Inter: 13 dias, `nextAutoSyncAt` nulo, sem erro."""
    result = _assess(
        item_last_updated_at=NOW - timedelta(days=13),
        item_next_auto_sync_at=None,
    )
    assert (result.state, result.reason) == ("stale", "no_auto_sync")
    assert result.data_age_hours == 13 * 24.0
    assert result.auto_sync_scheduled is False


def test_old_data_with_overdue_auto_sync_is_stale():
    result = _assess(
        item_last_updated_at=NOW - timedelta(days=3),
        item_next_auto_sync_at=NOW - timedelta(hours=5),
    )
    assert (result.state, result.reason) == ("stale", "auto_sync_overdue")


def test_old_data_with_future_auto_sync_is_not_stale():
    result = _assess(
        item_last_updated_at=NOW - timedelta(days=3),
        item_next_auto_sync_at=NOW + timedelta(hours=2),
    )
    assert result.state == "fresh"


def test_recent_data_without_auto_sync_is_not_stale_yet():
    """Até 48h sem agendamento ainda não é alarme."""
    result = _assess(item_last_updated_at=NOW - timedelta(hours=30), item_next_auto_sync_at=None)
    assert result.state == "fresh"


def test_boundary_exactly_48h_is_not_stale():
    result = _assess(item_last_updated_at=NOW - timedelta(hours=48), item_next_auto_sync_at=None)
    assert result.state == "fresh"


def test_login_error_needs_attention_even_if_data_is_recent():
    result = _assess(item_status="LOGIN_ERROR")
    assert (result.state, result.reason) == ("attention", "needs_attention")


def test_pending_user_action_needs_attention():
    result = _assess(item_user_action="AUTHORIZE")
    assert result.state == "attention"


def test_never_checked_is_unknown():
    result = _assess(item_checked_at=None, item_last_updated_at=None, item_status=None)
    assert (result.state, result.reason) == ("unknown", "not_checked")
    assert result.data_age_hours is None


def test_checked_but_without_last_update_is_unknown():
    result = _assess(item_last_updated_at=None)
    assert result.state == "unknown"


def test_consent_expiring_soon_is_flagged_without_changing_state():
    result = _assess(consent_expires_at=NOW + timedelta(days=12))
    assert result.state == "fresh"
    assert result.consent_expiring is True
    assert result.consent_days_left == 12


def test_consent_far_away_is_not_flagged():
    assert _assess().consent_expiring is False


def test_consent_already_expired_is_flagged():
    result = _assess(consent_expires_at=NOW - timedelta(days=2))
    assert result.consent_expiring is True
    assert result.consent_days_left < 0


def test_missing_consent_date_is_not_flagged():
    result = _assess(consent_expires_at=None)
    assert result.consent_expiring is False and result.consent_days_left is None


def test_parse_pluggy_datetime_handles_z_suffix_and_garbage():
    assert parse_pluggy_datetime("2026-09-17T12:32:52.971Z") == datetime(
        2026, 9, 17, 12, 32, 52, 971000
    )
    assert parse_pluggy_datetime(None) is None
    assert parse_pluggy_datetime("") is None
    assert parse_pluggy_datetime("não é data") is None
    assert parse_pluggy_datetime(12345) is None
