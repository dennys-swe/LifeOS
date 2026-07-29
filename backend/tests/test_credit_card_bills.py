from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.bank_account import BankAccount
from app.models.credit_card_bill import CreditCardBill
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


def _bill_payload(bill_id="bill-1", due_date="2026-08-10T00:00:00Z", total_amount=850.0):
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
    assert bill.due_date == date(2026, 8, 10)
    assert bill.payable_id is not None

    payable = db_session.get(Payable, bill.payable_id)
    assert payable is not None
    assert payable.amount == Decimal("850.00")
    assert payable.due_date == date(2026, 8, 10)
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
        _bill_payload(bill_id="bill-original", due_date="2026-05-10T00:00:00Z", total_amount=655.34),
    )
    second = bill_service.upsert_bill(
        db_session, user.id, acc, "pluggy-acc-1",
        _bill_payload(bill_id="bill-reissued", due_date="2026-05-11T00:00:00Z", total_amount=655.34),
    )

    bills = db_session.query(CreditCardBill).all()
    payables = db_session.query(Payable).all()
    assert len(bills) == 1
    assert len(payables) == 1
    assert second.id == first.id
    assert second.external_id == "bill-reissued"
    assert second.due_date == date(2026, 5, 11)


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
    bill_service.upsert_bill(db_session, user.id, acc, "pluggy-acc-1", _bill_payload())

    response = client.get("/credit-card-bills?month=8&year=2026")
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
    assert len(bills) == 1
    assert bills[0].payable_id is not None
