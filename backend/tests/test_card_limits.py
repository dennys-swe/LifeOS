"""Limite consolidado dos cartões (#204).

Semântica de `creditLimit`/`availableCreditLimit` em `tests/fixtures/pluggy/README.md` (#196).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models.account_balance_snapshot import AccountBalanceSnapshot
from app.models.bank_account import BankAccount
from app.models.credit_card_bill import CreditCardBill
from app.models.ignored_card import IgnoredCard
from app.services import card_limit_service as svc

NOW = datetime(2026, 9, 30, 18, 0, 0)


def conn(db, user, **extra) -> BankAccount:
    acc = BankAccount(
        user_id=user.id,
        name="Conexão",
        bank_name="MeuPluggy",
        account_type="checking",
        external_id=str(uuid4()),
        item_status="UPDATED",
        item_checked_at=NOW,
        item_last_updated_at=NOW - timedelta(hours=5),
        item_next_auto_sync_at=NOW + timedelta(hours=19),
        **extra,
    )
    db.add(acc)
    db.flush()
    return acc


def snap(db, user, acc, pluggy_id, limit, available, *, at=NOW, kind="CREDIT"):
    row = AccountBalanceSnapshot(
        user_id=user.id,
        bank_account_id=acc.id,
        pluggy_account_id=pluggy_id,
        account_type=kind,
        balance=None if limit is None else Decimal(str(limit)) - Decimal(str(available or 0)),
        credit_limit=None if limit is None else Decimal(str(limit)),
        available_credit_limit=None if available is None else Decimal(str(available)),
        currency="BRL",
        captured_at=at,
    )
    db.add(row)
    db.flush()
    return row


def bill(db, user, acc, pluggy_id, *, card_name=None, custom=None):
    db.add(
        CreditCardBill(
            user_id=user.id,
            bank_account_id=acc.id,
            pluggy_account_id=pluggy_id,
            external_id=str(uuid4()),
            card_name=card_name,
            custom_card_name=custom,
            due_date=date(2026, 10, 10),
            total_amount=Decimal("100"),
        )
    )
    db.flush()


def test_sums_limits_of_cards_in_different_connections(db_session, user):
    a, b = conn(db_session, user), conn(db_session, user)
    snap(db_session, user, a, "card-1", 1600, 226.86)
    snap(db_session, user, b, "card-2", 914, 70.47)

    result = svc.get_card_limits(db_session, user.id, now=NOW)

    assert result.total_limit == Decimal("2514.00")
    assert result.total_used == Decimal("2216.67")
    assert result.total_available == Decimal("297.33")
    assert result.used_pct == 88.2
    assert result.cards_counted == 2


def test_used_is_limit_minus_available_and_percent_per_card(db_session, user):
    acc = conn(db_session, user)
    snap(db_session, user, acc, "card-1", 2420, 1584.70)

    (card,) = svc.get_card_limits(db_session, user.id, now=NOW).cards

    assert card.used == Decimal("835.30")
    assert card.used_pct == 34.5
    assert card.status == "ok"


def test_only_the_latest_snapshot_of_each_account_counts(db_session, user):
    """Limite é da conta: fotos antigas da mesma conta não somam de novo."""
    acc = conn(db_session, user)
    snap(db_session, user, acc, "card-1", 1600, 1000, at=NOW - timedelta(days=3))
    snap(db_session, user, acc, "card-1", 1600, 226.86, at=NOW)

    result = svc.get_card_limits(db_session, user.id, now=NOW)

    assert result.cards_counted == 1
    assert result.total_limit == Decimal("1600.00")
    assert result.total_used == Decimal("1373.14")


def test_two_cards_sharing_one_pluggy_account_count_the_limit_once(db_session, user):
    """Nubank com 2 finais e Itaú/Luiza com 2 finais: a Pluggy entrega 1 conta e 1 limite."""
    acc = conn(db_session, user)
    snap(db_session, user, acc, "shared-account", 1600, 226.86)
    bill(db_session, user, acc, "shared-account", card_name="gold")

    result = svc.get_card_limits(db_session, user.id, now=NOW)

    assert result.total_limit == Decimal("1600.00")
    assert len(result.cards) == 1


def test_ignored_card_is_left_out_of_totals_and_counted(db_session, user):
    """Cartão em cancelamento: o painel da Pluggy soma o limite dele, nós não."""
    acc = conn(db_session, user)
    snap(db_session, user, acc, "active", 4934, 1882.03)
    snap(db_session, user, acc, "cancelling", 1336, 1336)
    db_session.add(
        IgnoredCard(user_id=user.id, bank_account_id=acc.id, pluggy_account_id="cancelling")
    )
    db_session.flush()

    result = svc.get_card_limits(db_session, user.id, now=NOW)

    assert result.total_limit == Decimal("4934.00")
    assert result.cards_ignored == 1
    assert [c.pluggy_account_id for c in result.cards] == ["active"]


def test_card_without_limit_is_omitted_from_totals_not_shown_as_zero(db_session, user):
    acc = conn(db_session, user)
    snap(db_session, user, acc, "known", 1000, 400)
    snap(db_session, user, acc, "silent", None, None)
    snap(db_session, user, acc, "zeroed", 0, 0)

    result = svc.get_card_limits(db_session, user.id, now=NOW)

    assert result.total_limit == Decimal("1000.00")
    assert result.cards_without_limit == 2
    by_id = {c.pluggy_account_id: c for c in result.cards}
    assert by_id["silent"].status == "no_limit" and by_id["silent"].used is None
    assert by_id["zeroed"].status == "no_limit"


def test_inconsistent_available_is_flagged_and_kept_out_of_totals(db_session, user):
    acc = conn(db_session, user)
    snap(db_session, user, acc, "ok", 1000, 400)
    snap(db_session, user, acc, "over", 1000, 1500)
    snap(db_session, user, acc, "negative", 1000, -10)

    result = svc.get_card_limits(db_session, user.id, now=NOW)

    assert result.cards_inconsistent == 2
    assert result.total_limit == Decimal("1000.00")
    assert {c.status for c in result.cards if c.pluggy_account_id != "ok"} == {"inconsistent"}


def test_no_cards_gives_zero_totals_and_no_percent(db_session, user):
    result = svc.get_card_limits(db_session, user.id, now=NOW)

    assert result.cards == []
    assert (result.total_limit, result.used_pct, result.cards_counted) == (Decimal("0.00"), None, 0)


def test_bank_account_snapshots_are_not_cards(db_session, user):
    acc = conn(db_session, user)
    snap(db_session, user, acc, "checking", None, None, kind="BANK")

    assert svc.get_card_limits(db_session, user.id, now=NOW).cards == []


def test_label_prefers_custom_name_then_card_name_then_generic(db_session, user):
    acc = conn(db_session, user)
    for pid in ("a", "b", "c"):
        snap(db_session, user, acc, pid, 1000, 500)
    bill(db_session, user, acc, "a", card_name="Mastercard Gold", custom="Meu Nubank")
    bill(db_session, user, acc, "b", card_name="Itaú Click")

    labels = {
        c.pluggy_account_id: c.label
        for c in svc.get_card_limits(db_session, user.id, now=NOW).cards
    }

    assert labels == {"a": "Meu Nubank", "b": "Itaú Click", "c": "Cartão"}


def test_stale_connection_makes_the_card_and_the_summary_stale(db_session, user):
    """Limite de uma conexão que parou de atualizar não pode parecer fresco."""
    fresh, stale = conn(db_session, user), conn(db_session, user)
    stale.item_last_updated_at = NOW - timedelta(days=13)
    stale.item_next_auto_sync_at = None
    snap(db_session, user, fresh, "fresh-card", 1000, 500)
    snap(db_session, user, stale, "stale-card", 2420, 1584.70)

    result = svc.get_card_limits(db_session, user.id, now=NOW)

    states = {c.pluggy_account_id: c.freshness_state for c in result.cards}
    assert states == {"fresh-card": "fresh", "stale-card": "stale"}
    assert result.freshness_state == "stale"


def test_connection_never_checked_is_unknown(db_session, user):
    acc = BankAccount(user_id=user.id, name="x", bank_name="y", account_type="checking")
    db_session.add(acc)
    db_session.flush()
    snap(db_session, user, acc, "card", 1000, 500)

    assert svc.get_card_limits(db_session, user.id, now=NOW).freshness_state == "unknown"


def test_other_users_cards_are_never_included(db_session, user, other_user):
    mine, theirs = conn(db_session, user), conn(db_session, other_user)
    snap(db_session, user, mine, "mine", 1000, 500)
    snap(db_session, other_user, theirs, "theirs", 9000, 100)
    db_session.add(
        IgnoredCard(user_id=other_user.id, bank_account_id=theirs.id, pluggy_account_id="mine")
    )
    db_session.flush()

    result = svc.get_card_limits(db_session, user.id, now=NOW)

    assert result.total_limit == Decimal("1000.00")
    assert result.cards_ignored == 0


def test_endpoint_returns_totals_and_cards(client, db_session, user):
    acc = conn(db_session, user)
    snap(db_session, user, acc, "card-1", 1600, 226.86, at=datetime.utcnow())
    bill(db_session, user, acc, "card-1", card_name="gold")
    db_session.commit()

    body = client.get("/cards/limits").json()

    assert Decimal(body["total_limit"]) == Decimal("1600.00")
    assert Decimal(body["total_used"]) == Decimal("1373.14")
    assert body["used_pct"] == 85.8
    assert body["cards"][0]["label"] == "gold"
    assert body["cards"][0]["status"] == "ok"


def test_endpoint_with_no_data_is_empty_not_an_error(client):
    body = client.get("/cards/limits").json()

    assert body["cards"] == [] and body["used_pct"] is None and body["cards_counted"] == 0
