from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.bank_account import BankAccount
from app.models.credit_card_bill import CreditCardBill, CreditCardBillStatus
from app.models.payable import Payable, PayableStatus
from app.services import bill_service


def _make_account(db, user) -> BankAccount:
    acc = BankAccount(
        user_id=user.id,
        name="Cartão Nubank",
        bank_name="Nubank",
        account_type="credit",
        external_id=str(uuid4()),
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def _in_window(day: int = 10, *, months_ahead: int = 0) -> date:
    """Data dentro da janela que gera Payable (mês atual ou o seguinte).

    Relativa a hoje de propósito: a janela é calculada a partir de `date.today()`,
    então data fixa faria o teste passar ou falhar dependendo do calendário.
    """
    today = date.today()
    year, month = today.year, today.month + months_ahead
    if month > 12:
        year, month = year + 1, month - 12
    return date(year, month, min(day, monthrange(year, month)[1]))


def _iso(d: date) -> str:
    return f"{d.isoformat()}T00:00:00Z"


def _bill_payload(bill_id="bill-1", due_date=None, total_amount=850.0):
    due_date = due_date or _iso(_in_window(10, months_ahead=1))
    return {
        "id": bill_id,
        "dueDate": due_date,
        "totalAmount": total_amount,
        "totalAmountCurrencyCode": "BRL",
        "minimumPaymentAmount": 100.0,
        "allowsInstallments": True,
    }


def test_upsert_bill_creates_payable(db_session, user):
    acc = _make_account(db_session, user)
    bill = bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload())

    assert bill.external_id == "bill-1"
    assert bill.total_amount == Decimal("850.00")
    assert bill.due_date == _in_window(10, months_ahead=1)
    assert bill.payable_id is not None

    payable = db_session.get(Payable, bill.payable_id)
    assert payable is not None
    assert payable.amount == Decimal("850.00")
    assert payable.due_date == bill.due_date
    assert payable.status == PayableStatus.PENDING
    assert "Cartão Nubank" in payable.title


def test_upsert_bill_is_idempotent(db_session, user):
    acc = _make_account(db_session, user)
    bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload())
    bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload())

    bills = db_session.query(CreditCardBill).all()
    payables = db_session.query(Payable).all()
    assert len(bills) == 1
    assert len(payables) == 1


def test_upsert_bill_reuses_existing_bill_when_pluggy_reissues_external_id(db_session, user):
    """Observado em dados reais: a Pluggy reemitiu um novo external_id pra
    mesma fatura entre dois syncs (mesmo cartão, mesmo mês, 1 dia de diferença
    no vencimento), criando faturas e payables duplicados. Como um cartão só
    tem uma fatura por mês, tratamos isso como a mesma fatura."""
    acc = _make_account(db_session, user)
    first = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1",
        _bill_payload(bill_id="bill-original", due_date=_iso(_in_window(10)), total_amount=655.34),
    )
    second = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1",
        _bill_payload(bill_id="bill-reissued", due_date=_iso(_in_window(11)), total_amount=655.34),
    )

    bills = db_session.query(CreditCardBill).all()
    payables = db_session.query(Payable).all()
    assert len(bills) == 1
    assert len(payables) == 1
    assert second.id == first.id
    assert second.external_id == "bill-reissued"
    assert second.due_date == _in_window(11)


def test_upsert_bill_does_not_merge_bills_from_different_cards(db_session, user):
    acc = _make_account(db_session, user)
    bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1",
        _bill_payload(bill_id="bill-card-1", due_date="2026-05-10T00:00:00Z", total_amount=655.34),
    )
    bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-2",
        _bill_payload(bill_id="bill-card-2", due_date="2026-05-11T00:00:00Z", total_amount=472.95),
    )

    bills = db_session.query(CreditCardBill).all()
    assert len(bills) == 2


def test_upsert_bill_updates_amount_on_resync(db_session, user):
    acc = _make_account(db_session, user)
    bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload(total_amount=850.0))
    updated = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1", _bill_payload(total_amount=920.0)
    )

    assert updated.total_amount == Decimal("920.00")
    payable = db_session.get(Payable, updated.payable_id)
    assert payable.amount == Decimal("920.00")


def test_upsert_bill_does_not_update_paid_payable(db_session, user):
    acc = _make_account(db_session, user)
    bill = bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload(total_amount=850.0))
    payable = db_session.get(Payable, bill.payable_id)
    payable.status = PayableStatus.PAID
    db_session.add(payable)
    db_session.commit()

    bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload(total_amount=920.0))
    db_session.refresh(payable)
    assert payable.amount == Decimal("850.00")


def test_upsert_bill_fixes_title_of_paid_payable(db_session, user):
    """O título é rótulo, não fato financeiro — payables antigos ficaram com o nome
    da conexão ("Fatura MeuPluggy") e precisam ser corrigidos mesmo já pagos."""
    acc = _make_account(db_session, user)
    bill = bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload())
    payable = db_session.get(Payable, bill.payable_id)
    payable.status = PayableStatus.PAID
    db_session.add(payable)
    db_session.commit()
    amount_before, due_before = payable.amount, payable.due_date

    bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1", _bill_payload(), card_name="Cartão Platinum"
    )

    db_session.refresh(payable)
    assert payable.title.startswith("Fatura Cartão Platinum —")
    # valor e vencimento seguem congelados
    assert payable.amount == amount_before
    assert payable.due_date == due_before


def test_two_cards_same_month_get_distinct_titles(db_session, user):
    acc = _make_account(db_session, user)

    bill_a = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1", _bill_payload("bill-a"), card_name="Cartão Loja"
    )
    bill_b = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-2", _bill_payload("bill-b"), card_name="Cartão Platinum"
    )

    title_a = db_session.get(Payable, bill_a.payable_id).title
    title_b = db_session.get(Payable, bill_b.payable_id).title
    assert title_a != title_b
    assert "Cartão Loja" in title_a and "Cartão Platinum" in title_b


def test_old_bill_is_saved_without_generating_payable(db_session, user):
    """Histórico antigo não vira conta a pagar: sem isso, fatura antiga que a
    conciliação não casou fica PENDING pra sempre e aparece como 'vencida'."""
    acc = _make_account(db_session, user)
    old = date.today().replace(day=1) - timedelta(days=120)

    bill = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1", _bill_payload(due_date=_iso(old))
    )

    assert bill.id is not None  # a fatura em si continua salva
    assert bill.payable_id is None
    assert db_session.query(Payable).count() == 0


def test_far_future_projected_bill_does_not_generate_payable(db_session, user):
    """Alguns bancos devolvem faturas projetadas de parcelamento — um cartão do
    Inter veio com 48 faturas, a mais distante ~1 ano à frente."""
    acc = _make_account(db_session, user)

    bill = bill_service.upsert_bill(
        db_session,
        user.id,
        acc,
        "pluggy-acc-1",
        _bill_payload(due_date=_iso(_in_window(12, months_ahead=6))),
    )

    assert bill.payable_id is None
    assert db_session.query(Payable).count() == 0


def test_current_and_next_month_bills_generate_payables(db_session, user):
    acc = _make_account(db_session, user)

    atual = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1", _bill_payload("b-atual", _iso(_in_window(10)))
    )
    proxima = bill_service.upsert_bill(
        db_session,
        user.id,
        acc,
        "pluggy-acc-2",
        _bill_payload("b-prox", _iso(_in_window(10, months_ahead=1))),
    )

    assert atual.payable_id is not None
    assert proxima.payable_id is not None


def test_existing_payable_still_syncs_after_bill_leaves_window(db_session, user):
    """A janela filtra só a criação — payable que já existe segue mantido."""
    acc = _make_account(db_session, user)
    bill = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1", _bill_payload(total_amount=500.0)
    )
    payable_id = bill.payable_id
    assert payable_id is not None

    # Fatura "envelhece" para fora da janela, mas o payable já existe.
    bill.due_date = date.today().replace(day=1) - timedelta(days=200)
    db_session.add(bill)
    db_session.commit()

    bill_service.upsert_bill(
        db_session,
        user.id,
        acc,
        "pluggy-acc-1",
        _bill_payload(total_amount=777.0),
        card_name="Cartão Renomeado",
    )

    payable = db_session.get(Payable, payable_id)
    assert payable is not None
    assert "Cartão Renomeado" in payable.title
    assert db_session.query(Payable).count() == 1


def test_is_in_payable_window_boundaries():
    today = date(2026, 7, 29)

    assert bill_service.is_in_payable_window(date(2026, 7, 1), today) is True
    assert bill_service.is_in_payable_window(date(2026, 8, 31), today) is True
    assert bill_service.is_in_payable_window(date(2026, 6, 30), today) is False
    assert bill_service.is_in_payable_window(date(2026, 9, 1), today) is False


def test_is_in_payable_window_crosses_year():
    today = date(2026, 12, 15)

    assert bill_service.is_in_payable_window(date(2026, 12, 10), today) is True
    assert bill_service.is_in_payable_window(date(2027, 1, 31), today) is True
    assert bill_service.is_in_payable_window(date(2027, 2, 1), today) is False


def test_list_bills_filters_by_month_and_user(db_session, user, other_user):
    acc = _make_account(db_session, user)
    other_acc = _make_account(db_session, other_user)
    bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload("bill-aug", "2026-08-10T00:00:00Z"))
    bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload("bill-sep", "2026-09-10T00:00:00Z"))
    bill_service.upsert_bill(db_session, other_user.id, other_acc, "pluggy-acc-2", _bill_payload("bill-other", "2026-08-15T00:00:00Z"))

    august_bills = bill_service.list_bills(db_session, user.id, month=8, year=2026)
    assert len(august_bills) == 1
    assert august_bills[0].external_id == "bill-aug"


def test_credit_card_bills_endpoint(client, db_session, user):
    acc = _make_account(db_session, user)
    # O payload padrão vence no mês seguinte ao de hoje; fixar "8/2026" no
    # filtro fazia o teste passar só enquanto durasse aquele mês.
    due = _in_window(10, months_ahead=1)
    bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload())

    response = client.get(f"/credit-card-bills?month={due.month}&year={due.year}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["total_amount"] == "850.00" or float(data[0]["total_amount"]) == 850.0


def test_sync_account_imports_bills_for_credit_accounts(db_session, user):
    from app.services import bank_sync_service

    acc = _make_account(db_session, user)
    pluggy_acc = SimpleNamespace(id=str(uuid4()), type="CREDIT")

    def _make_api_client_ctx():
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    bills_raw = SimpleNamespace(data=json.dumps({"results": [_bill_payload()]}).encode())
    tx_raw = SimpleNamespace(data=json.dumps({"results": [], "totalPages": 1}).encode())

    with (
        patch("app.services.bank_sync_service.get_api_client", return_value=_make_api_client_ctx()),
        patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
    ):
        mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
        mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = tx_raw
        mock_sdk.BillApi.return_value.bills_list_without_preload_content.return_value = bills_raw

        result = bank_sync_service.sync_account(db_session, acc)

    assert result["bills_synced"] == 1
    bills = db_session.query(CreditCardBill).all()
    # Além da fatura fechada, o sync reconstrói o ciclo seguinte ainda em aberto.
    closed = [b for b in bills if b.status == CreditCardBillStatus.CLOSED]
    assert len(closed) == 1
    assert closed[0].payable_id is not None


def test_update_card_alias_updates_all_bills_and_payables(client, db_session, user):
    acc = _make_account(db_session, user)
    bill1 = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-inter", _bill_payload("b1", _iso(_in_window(10)))
    )
    bill2 = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-inter", _bill_payload("b2", _iso(_in_window(10, months_ahead=1)))
    )

    resp = client.patch(f"/credit-card-bills/{bill1.id}", json={"custom_card_name": "Inter Black"})
    assert resp.status_code == 200
    assert resp.json()["custom_card_name"] == "Inter Black"

    db_session.refresh(bill1)
    db_session.refresh(bill2)
    assert bill1.custom_card_name == "Inter Black"
    assert bill2.custom_card_name == "Inter Black"

    payable1 = db_session.get(Payable, bill1.payable_id)
    payable2 = db_session.get(Payable, bill2.payable_id)
    assert "Fatura Inter Black —" in payable1.title
    assert "Fatura Inter Black —" in payable2.title

