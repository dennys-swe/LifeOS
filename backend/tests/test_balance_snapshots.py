"""Snapshots de saldo e limite gravados pelo sync (#197).

Semântica de `balance`/`creditLimit` em `tests/fixtures/pluggy/README.md` (#196).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.account_balance_snapshot import AccountBalanceSnapshot
from app.models.bank_account import BankAccount
from app.models.ignored_card import IgnoredCard
from app.services import balance_snapshot_service, bank_sync_service

T0 = datetime(2026, 10, 1, 12, 0, 0)


def _bank_account(db, user) -> BankAccount:
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


def _bank(balance=120.5, acct_id="acc-bank"):
    return SimpleNamespace(id=acct_id, type="BANK", balance=balance, currency_code="BRL")


def _card(limit=1600.0, available=226.86, acct_id="acc-card"):
    return SimpleNamespace(
        id=acct_id,
        type="CREDIT",
        balance=round(limit - available, 2),
        currency_code="BRL",
        credit_data=SimpleNamespace(credit_limit=limit, available_credit_limit=available),
    )


def _rows(db) -> list[AccountBalanceSnapshot]:
    return db.query(AccountBalanceSnapshot).order_by(AccountBalanceSnapshot.captured_at).all()


def test_bank_account_records_balance_without_limits(db_session, user):
    acc = _bank_account(db_session, user)

    balance_snapshot_service.record_snapshot(db_session, user.id, acc.id, _bank(), now=T0)
    db_session.commit()

    (row,) = _rows(db_session)
    assert row.account_type == "BANK"
    assert row.balance == Decimal("120.50")
    assert row.credit_limit is None and row.available_credit_limit is None
    assert row.captured_at == T0


def test_credit_card_records_limits_and_consumed_balance(db_session, user):
    acc = _bank_account(db_session, user)

    balance_snapshot_service.record_snapshot(db_session, user.id, acc.id, _card(), now=T0)
    db_session.commit()

    (row,) = _rows(db_session)
    assert row.account_type == "CREDIT"
    assert row.credit_limit == Decimal("1600.00")
    assert row.available_credit_limit == Decimal("226.86")
    assert row.balance == row.credit_limit - row.available_credit_limit


def test_missing_values_are_not_recorded_as_zero(db_session, user):
    """`None` (o banco não informou) é diferente de saldo zero."""
    acc = _bank_account(db_session, user)
    no_data = SimpleNamespace(id="acc-x", type="BANK", balance=None, currency_code="BRL")

    assert balance_snapshot_service.record_snapshot(db_session, user.id, acc.id, no_data) is None
    assert _rows(db_session) == []


def test_zero_balance_is_recorded(db_session, user):
    acc = _bank_account(db_session, user)

    balance_snapshot_service.record_snapshot(db_session, user.id, acc.id, _bank(0), now=T0)
    db_session.commit()

    assert _rows(db_session)[0].balance == Decimal("0.00")


def test_other_account_types_are_ignored(db_session, user):
    acc = _bank_account(db_session, user)
    invest = SimpleNamespace(id="acc-inv", type="INVESTMENT", balance=10.0, currency_code="BRL")

    assert balance_snapshot_service.record_snapshot(db_session, user.id, acc.id, invest) is None


def test_unchanged_values_within_interval_do_not_duplicate(db_session, user):
    acc = _bank_account(db_session, user)
    snap = balance_snapshot_service.record_snapshot

    snap(db_session, user.id, acc.id, _bank(), now=T0)
    db_session.commit()
    again = snap(db_session, user.id, acc.id, _bank(), now=T0 + timedelta(hours=1))

    assert again is None
    assert len(_rows(db_session)) == 1


def test_unchanged_values_after_interval_record_again(db_session, user):
    acc = _bank_account(db_session, user)
    snap = balance_snapshot_service.record_snapshot

    snap(db_session, user.id, acc.id, _bank(), now=T0)
    db_session.commit()
    snap(db_session, user.id, acc.id, _bank(), now=T0 + timedelta(hours=7))
    db_session.commit()

    assert len(_rows(db_session)) == 2


def test_changed_values_record_immediately(db_session, user):
    acc = _bank_account(db_session, user)
    snap = balance_snapshot_service.record_snapshot

    snap(db_session, user.id, acc.id, _bank(100), now=T0)
    db_session.commit()
    snap(db_session, user.id, acc.id, _bank(80), now=T0 + timedelta(minutes=5))
    db_session.commit()

    assert [r.balance for r in _rows(db_session)] == [Decimal("100.00"), Decimal("80.00")]


def test_currency_change_records_even_with_same_values(db_session, user):
    acc = _bank_account(db_session, user)
    snap = balance_snapshot_service.record_snapshot
    brl = _bank(100)
    usd = SimpleNamespace(id=brl.id, type="BANK", balance=100, currency_code="USD")

    snap(db_session, user.id, acc.id, brl, now=T0)
    db_session.commit()
    changed = snap(db_session, user.id, acc.id, usd, now=T0 + timedelta(minutes=5))

    assert changed is not None and changed.currency == "USD"


def test_history_is_isolated_between_users(db_session, user, other_user):
    """Mesmo `pluggy_account_id` em usuários diferentes não se enxerga."""
    acc_a = _bank_account(db_session, user)
    acc_b = _bank_account(db_session, other_user)
    snap = balance_snapshot_service.record_snapshot

    snap(db_session, user.id, acc_a.id, _bank(100, "same-id"), now=T0)
    db_session.commit()
    created = snap(db_session, other_user.id, acc_b.id, _bank(100, "same-id"), now=T0)
    db_session.commit()

    assert created is not None
    assert len(_rows(db_session)) == 2
    latest = balance_snapshot_service.latest_snapshot(db_session, other_user.id, "same-id")
    assert latest.user_id == other_user.id


# ---------------------------------------------------------------------------
# Integração com o sync
# ---------------------------------------------------------------------------


def _ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _sync(db, acc, pluggy_accounts):
    empty_page = SimpleNamespace(data=json.dumps({"results": [], "totalPages": 1}).encode())
    with (
        patch("app.services.bank_sync_service.get_api_client", return_value=_ctx()),
        patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
    ):
        mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
            results=pluggy_accounts
        )
        mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = empty_page
        mock_sdk.BillApi.return_value.bills_list_without_preload_content.return_value = (
            SimpleNamespace(data=json.dumps({"results": []}).encode())
        )
        return bank_sync_service.sync_account(db, acc)


def test_sync_records_snapshot_per_account(db_session, user):
    acc = _bank_account(db_session, user)

    _sync(db_session, acc, [_bank(), _card()])

    by_type = {r.account_type: r for r in _rows(db_session)}
    assert set(by_type) == {"BANK", "CREDIT"}
    assert by_type["BANK"].bank_account_id == acc.id
    assert by_type["CREDIT"].credit_limit == Decimal("1600.00")


def test_sync_twice_in_a_row_does_not_duplicate(db_session, user):
    acc = _bank_account(db_session, user)

    _sync(db_session, acc, [_bank()])
    _sync(db_session, acc, [_bank()])

    assert len(_rows(db_session)) == 1


def test_ignored_card_gets_no_snapshot(db_session, user):
    """Cartão que o usuário ignorou (ex: cancelado) não entra nem no limite consolidado."""
    acc = _bank_account(db_session, user)
    db_session.add(
        IgnoredCard(user_id=user.id, bank_account_id=acc.id, pluggy_account_id="acc-card")
    )
    db_session.commit()

    _sync(db_session, acc, [_bank(), _card(acct_id="acc-card")])

    assert [r.account_type for r in _rows(db_session)] == ["BANK"]
