"""O sync preenche o selo de cartão de transações antigas que ficaram sem ele (#184)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.bank_account import BankAccount
from app.models.transaction import Transaction, TransactionType
from app.services import bank_sync_service


def _conn(db, user) -> BankAccount:
    acc = BankAccount(
        user_id=user.id,
        name="Conexão",
        bank_name="MeuPluggy",
        account_type="checking",
        external_id=str(uuid4()),
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def _old_tx(db, user, tx_id, *, label=None, pluggy_account_id=None, description="COMPRA"):
    tx = Transaction(
        user_id=user.id,
        date=date(2026, 9, 1),
        description=description,
        amount=Decimal("10.00"),
        type=TransactionType.EXPENSE,
        source=f"pluggy:{tx_id}",
        card_label=label,
        pluggy_account_id=pluggy_account_id,
    )
    db.add(tx)
    db.commit()
    return tx


def _ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _sync(db, acc, feed_txs, *, account_name="Itaú Click", account_type="CREDIT"):
    pluggy_acct = SimpleNamespace(id="pl-acc-1", type=account_type, name=account_name)
    page = SimpleNamespace(data=json.dumps({"results": feed_txs, "totalPages": 1}).encode())
    with (
        patch("app.services.bank_sync_service.get_api_client", return_value=_ctx()),
        patch("app.services.bank_sync_service.pluggy_sdk") as sdk,
    ):
        sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
            results=[pluggy_acct]
        )
        sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = (
            page
        )
        sdk.BillApi.return_value.bills_list_without_preload_content.return_value = SimpleNamespace(
            data=json.dumps({"results": []}).encode()
        )
        return bank_sync_service.sync_account(db, acc)


def _feed(tx_id, card_number=None):
    tx = {"id": tx_id, "amount": 10.0, "description": "COMPRA", "date": "2026-09-01T00:00:00Z"}
    tx["type"] = "DEBIT"
    if card_number:
        tx["creditCardMetadata"] = {"cardNumber": card_number}
    return tx


def test_existing_transaction_without_label_gets_card_and_account(db_session, user):
    acc = _conn(db_session, user)
    tx = _old_tx(db_session, user, "t1")

    result = _sync(db_session, acc, [_feed("t1", "4174")])
    db_session.refresh(tx)

    assert tx.card_label == "Itaú Click ••4174"
    assert tx.pluggy_account_id == "pl-acc-1"
    assert result["relabeled"] == 1
    assert result["imported"] == 0


def test_label_without_card_number_uses_just_the_account_name(db_session, user):
    """Inter não manda `cardNumber`: o selo é só o nome."""
    acc = _conn(db_session, user)
    tx = _old_tx(db_session, user, "t1")

    _sync(db_session, acc, [_feed("t1")], account_name="Titular")
    db_session.refresh(tx)

    assert tx.card_label == "Titular"


def test_already_labeled_transaction_is_left_alone(db_session, user):
    acc = _conn(db_session, user)
    tx = _old_tx(db_session, user, "t1", label="Apelido antigo", pluggy_account_id="pl-acc-1")

    result = _sync(db_session, acc, [_feed("t1", "4174")])
    db_session.refresh(tx)

    assert tx.card_label == "Apelido antigo"
    assert result["relabeled"] == 0


def test_existing_pluggy_account_id_is_not_overwritten(db_session, user):
    acc = _conn(db_session, user)
    tx = _old_tx(db_session, user, "t1", pluggy_account_id="outra-conta")

    _sync(db_session, acc, [_feed("t1", "4174")])
    db_session.refresh(tx)

    assert tx.card_label == "Itaú Click ••4174"
    assert tx.pluggy_account_id == "outra-conta"


def test_transaction_missing_from_the_feed_stays_unlabeled(db_session, user):
    acc = _conn(db_session, user)
    gone = _old_tx(db_session, user, "gone")

    _sync(db_session, acc, [_feed("other", "4174")])
    db_session.refresh(gone)

    assert gone.card_label is None


def test_manual_transactions_and_other_users_are_untouched(db_session, user, other_user):
    acc = _conn(db_session, user)
    manual = Transaction(
        user_id=user.id,
        date=date(2026, 9, 1),
        description="MANUAL",
        amount=Decimal("5"),
        type=TransactionType.EXPENSE,
        source=None,
    )
    theirs = _old_tx(db_session, other_user, "t1")  # mesmo id de feed, outro usuário
    db_session.add(manual)
    db_session.commit()

    _sync(db_session, acc, [_feed("t1", "4174")])
    db_session.refresh(manual)
    db_session.refresh(theirs)

    assert manual.card_label is None
    assert theirs.card_label is None


def test_second_sync_does_nothing_more(db_session, user):
    acc = _conn(db_session, user)
    _old_tx(db_session, user, "t1")

    _sync(db_session, acc, [_feed("t1", "4174")])
    again = _sync(db_session, acc, [_feed("t1", "4174")])

    assert again["relabeled"] == 0
