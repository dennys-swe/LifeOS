"""Estado do item da Pluggy guardado pelo sync e exposto na API (#214)."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.bank_account import BankAccount
from app.services import bank_sync_service

INTER_ITEM = {
    "status": "UPDATED",
    "executionStatus": "SUCCESS",
    "lastUpdatedAt": "2026-09-17T12:32:52.971Z",
    "nextAutoSyncAt": None,
    "consentExpiresAt": "2027-07-25T23:47:38.552Z",
    "userAction": None,
}


def _account(db, user, **extra) -> BankAccount:
    acc = BankAccount(
        user_id=user.id,
        name="Conexão",
        bank_name="MeuPluggy",
        account_type="checking",
        external_id=str(uuid4()),
        **extra,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def _ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _sync(db, acc, item_response):
    """`item_response`: dict (vira JSON cru) ou Exception (a chamada levanta)."""
    empty_page = SimpleNamespace(data=json.dumps({"results": [], "totalPages": 1}).encode())
    with (
        patch("app.services.bank_sync_service.get_api_client", return_value=_ctx()),
        patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
    ):
        items = mock_sdk.ItemsApi.return_value.items_retrieve_without_preload_content
        if isinstance(item_response, Exception):
            items.side_effect = item_response
        else:
            items.return_value = SimpleNamespace(data=json.dumps(item_response).encode())
        mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[])
        mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = empty_page
        return bank_sync_service.sync_account(db, acc)


def test_sync_stores_item_state(db_session, user):
    acc = _account(db_session, user)

    _sync(db_session, acc, INTER_ITEM)
    db_session.refresh(acc)

    assert acc.item_status == "UPDATED"
    assert acc.item_execution_status == "SUCCESS"
    assert acc.item_last_updated_at == datetime(2026, 9, 17, 12, 32, 52, 971000)
    assert acc.item_next_auto_sync_at is None
    assert acc.consent_expires_at == datetime(2027, 7, 25, 23, 47, 38, 552000)
    assert acc.item_checked_at is not None


def test_sync_keeps_previous_item_state_when_item_read_fails(db_session, user):
    """Item ilegível não derruba o sync nem apaga o último estado conhecido."""
    checked = datetime(2026, 9, 29, 10, 0, 0)
    acc = _account(
        db_session,
        user,
        item_status="UPDATED",
        item_last_updated_at=datetime(2026, 9, 29, 9, 0, 0),
        item_checked_at=checked,
    )

    result = _sync(db_session, acc, TimeoutError("lento"))
    db_session.refresh(acc)

    assert result is not None
    assert acc.item_status == "UPDATED"
    assert acc.item_checked_at == checked


def test_sync_ignores_non_object_item_response(db_session, user):
    acc = _account(db_session, user)

    _sync(db_session, acc, ["não", "é", "objeto"])
    db_session.refresh(acc)

    assert acc.item_checked_at is None


def test_sync_clears_pending_user_action_when_it_goes_away(db_session, user):
    acc = _account(
        db_session, user, item_status="WAITING_USER_ACTION", item_user_action="AUTHORIZE"
    )

    _sync(db_session, acc, INTER_ITEM)
    db_session.refresh(acc)

    assert acc.item_status == "UPDATED"
    assert acc.item_user_action is None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_list_exposes_stale_freshness_for_connection_without_auto_sync(client, db_session, user):
    _account(
        db_session,
        user,
        item_status="UPDATED",
        item_last_updated_at=datetime(2020, 1, 1),
        item_next_auto_sync_at=None,
        item_checked_at=datetime(2026, 9, 30),
    )

    body = client.get("/bank-accounts").json()

    assert body[0]["freshness"]["state"] == "stale"
    assert body[0]["freshness"]["reason"] == "no_auto_sync"
    assert body[0]["freshness"]["auto_sync_scheduled"] is False


def test_list_exposes_unknown_freshness_before_first_check(client, db_session, user):
    _account(db_session, user)

    body = client.get("/bank-accounts").json()

    assert body[0]["freshness"]["state"] == "unknown"
    assert body[0]["freshness"]["data_age_hours"] is None


def test_list_does_not_leak_other_users_connections(client, db_session, user, other_user):
    _account(
        db_session, other_user, item_status="LOGIN_ERROR", item_checked_at=datetime(2026, 9, 30)
    )

    assert client.get("/bank-accounts").json() == []
