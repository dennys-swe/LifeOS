from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from app.models.bank_account import BankAccount, BankAccountSyncStatus


def _make_account(db, user, *, external_id: str | None = None) -> BankAccount:
    acc = BankAccount(
        user_id=user.id,
        name="Conta Corrente",
        bank_name="Nubank",
        account_type="checking",
        external_id=external_id,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@patch("app.api.endpoints.webhooks.bank_sync_service.sync_account")
def test_pluggy_webhook_triggers_sync_for_known_item(mock_sync, client, db_session, user):
    item_id = str(uuid4())
    acc = _make_account(db_session, user, external_id=item_id)
    mock_sync.return_value = {
        "imported": 0, "skipped": 0, "bills_synced": 0, "auto_reconciled": 0, "suggestions": [],
    }

    r = client.post("/webhooks/pluggy", json={"event": "transactions/created", "itemId": item_id})

    assert r.status_code == 200
    db_session.refresh(acc)
    assert acc.sync_status == BankAccountSyncStatus.IDLE
    mock_sync.assert_called_once()


def test_pluggy_webhook_ignores_unknown_item(client):
    r = client.post("/webhooks/pluggy", json={"event": "transactions/created", "itemId": str(uuid4())})
    assert r.status_code == 200


def test_pluggy_webhook_ignores_irrelevant_event(client, db_session, user):
    item_id = str(uuid4())
    acc = _make_account(db_session, user, external_id=item_id)

    r = client.post("/webhooks/pluggy", json={"event": "item/deleted", "itemId": item_id})

    assert r.status_code == 200
    db_session.refresh(acc)
    assert acc.sync_status == BankAccountSyncStatus.IDLE


@patch("app.api.endpoints.webhooks.bank_sync_service.sync_account")
def test_pluggy_webhook_skips_account_already_syncing(mock_sync, client, db_session, user):
    item_id = str(uuid4())
    acc = _make_account(db_session, user, external_id=item_id)
    acc.sync_status = BankAccountSyncStatus.SYNCING
    db_session.add(acc)
    db_session.commit()

    r = client.post("/webhooks/pluggy", json={"event": "transactions/created", "itemId": item_id})

    assert r.status_code == 200
    mock_sync.assert_not_called()
