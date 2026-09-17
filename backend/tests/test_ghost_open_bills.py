"""Issue #25: cartão cancelado/desativado some da resposta da Pluggy pro
item, mas nada parava de gerar conta a pagar pra ele — a fatura em aberto
(reconstruída) e o payable PENDING ligado ficavam órfãos pra sempre."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import select

from app.models.bank_account import BankAccount
from app.models.credit_card_bill import CreditCardBill, CreditCardBillStatus
from app.models.payable import Payable, PayableStatus
from app.services import bank_sync_service


def _age_open_bills(db, user, days):
    """Simula que a fatura foi sincronizada pela última vez há `days` dias —
    a carência de `retire_vanished_open_bills` (issue #25, achado na
    revisão: um glitch transitório da Pluggy não pode apagar fatura de
    cartão que continua ativo) só libera a retirada depois de 2 dias sem o
    cartão aparecer."""
    bills = (
        db.execute(
            select(CreditCardBill).where(
                CreditCardBill.user_id == user.id,
                CreditCardBill.status == CreditCardBillStatus.OPEN,
            )
        )
        .scalars()
        .all()
    )
    for bill in bills:
        bill.synced_at = datetime.now(timezone.utc) - timedelta(days=days)
        db.add(bill)
    db.commit()


def _account(db, user) -> BankAccount:
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


def _ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _closed_bill_payload(card_id, due_date):
    return {
        "id": f"closed-{card_id}",
        "dueDate": f"{due_date.isoformat()}T00:00:00Z",
        "totalAmount": 100.0,
    }


def _purchase(card_id, amount=50.0):
    return {
        "id": f"tx-{card_id}",
        "amount": amount,
        "description": f"compra {card_id}",
        "date": f"{date.today().isoformat()}T00:00:00Z",
        "type": "DEBIT",
    }


def _sync_two_cards(db, acc, card_ids):
    """Simula um sync do item com os cartões em `card_ids` — cada um com uma
    fatura fechada hoje (pra `upsert_open_bill` ter de onde partir) e uma
    compra no ciclo aberto, gerando um Payable PENDING."""
    pluggy_accounts = [
        SimpleNamespace(id=card_id, type="CREDIT", name=card_id, marketing_name=card_id)
        for card_id in card_ids
    ]

    def _bills_for(account_id, **kwargs):
        return SimpleNamespace(
            data=json.dumps({"results": [_closed_bill_payload(account_id, date.today())]}).encode()
        )

    def _tx_for(account_id, **kwargs):
        return SimpleNamespace(
            data=json.dumps({"results": [_purchase(account_id)], "totalPages": 1}).encode()
        )

    with (
        patch("app.services.bank_sync_service.get_api_client", return_value=_ctx()),
        patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
    ):
        mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
            results=pluggy_accounts
        )
        mock_sdk.BillApi.return_value.bills_list_without_preload_content.side_effect = (
            lambda account_id, **kw: _bills_for(account_id)
        )
        mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.side_effect = (
            lambda account_id, **kw: _tx_for(account_id)
        )
        return bank_sync_service.sync_account(db, acc)


def test_card_that_vanishes_has_its_ghost_bill_and_payable_retired(db_session, user):
    acc = _account(db_session, user)

    _sync_two_cards(db_session, acc, ["card-a", "card-b"])

    bills = (
        db_session.execute(select(CreditCardBill).where(CreditCardBill.user_id == user.id))
        .scalars()
        .all()
    )
    open_bills = [b for b in bills if b.status == CreditCardBillStatus.OPEN]
    assert {b.pluggy_account_id for b in open_bills} == {"card-a", "card-b"}
    payable_ids_before = {b.pluggy_account_id: b.payable_id for b in open_bills}
    assert all(payable_ids_before.values())

    # 2ª sincronização, 3 dias depois (fora da carência): card-b sumiu do
    # item (cancelado)
    _age_open_bills(db_session, user, days=3)
    result = _sync_two_cards(db_session, acc, ["card-a"])

    assert result["retired_open_bills"] == 1

    remaining_bills = (
        db_session.execute(select(CreditCardBill).where(CreditCardBill.user_id == user.id))
        .scalars()
        .all()
    )
    remaining_open = {
        b.pluggy_account_id for b in remaining_bills if b.status == CreditCardBillStatus.OPEN
    }
    assert remaining_open == {"card-a"}

    # o payable do card-a permanece intacto
    card_a_payable_id = payable_ids_before["card-a"]
    assert db_session.get(Payable, card_a_payable_id) is not None

    # o payable do card-b (que estava PENDING) foi removido
    card_b_payable_id = payable_ids_before["card-b"]
    assert db_session.get(Payable, card_b_payable_id) is None


def test_paid_payable_of_a_vanished_card_is_never_touched(db_session, user):
    acc = _account(db_session, user)
    _sync_two_cards(db_session, acc, ["card-a", "card-b"])

    # o dono paga a fatura do card-b antes do cartão ser cancelado
    bill_b = (
        db_session.execute(
            select(CreditCardBill).where(
                CreditCardBill.user_id == user.id,
                CreditCardBill.pluggy_account_id == "card-b",
                CreditCardBill.status == CreditCardBillStatus.OPEN,
            )
        )
        .scalars()
        .one()
    )
    payable_b = db_session.get(Payable, bill_b.payable_id)
    payable_b.status = PayableStatus.PAID
    payable_b.payment_date = date.today()
    db_session.add(payable_b)
    db_session.commit()

    _age_open_bills(db_session, user, days=3)
    result = _sync_two_cards(db_session, acc, ["card-a"])

    # a fatura OPEN órfã ainda é removida (não é mais o ciclo corrente)...
    assert result["retired_open_bills"] == 1
    # ...mas o payable já PAID continua exatamente como estava
    still_there = db_session.get(Payable, payable_b.id)
    assert still_there is not None
    assert still_there.status == PayableStatus.PAID


def test_a_single_missing_sync_does_not_retire_yet(db_session, user):
    """Achado na revisão do PR desta issue: `accounts_list` pode devolver uma
    resposta parcial (não vazia, só incompleta) por um glitch transitório —
    retirar na primeira passada em que um cartão ainda ativo não aparece
    apagaria fatura/payable reais por causa de uma falha de rede."""
    acc = _account(db_session, user)
    _sync_two_cards(db_session, acc, ["card-a", "card-b"])

    bill_b = (
        db_session.execute(
            select(CreditCardBill).where(
                CreditCardBill.user_id == user.id,
                CreditCardBill.pluggy_account_id == "card-b",
                CreditCardBill.status == CreditCardBillStatus.OPEN,
            )
        )
        .scalars()
        .one()
    )
    payable_b_id = bill_b.payable_id

    # card-b não aparece nesta passada, mas o bill foi sincronizado com
    # sucesso há poucos minutos — ainda dentro da carência
    result = _sync_two_cards(db_session, acc, ["card-a"])

    assert result["retired_open_bills"] == 0
    assert db_session.get(CreditCardBill, bill_b.id) is not None
    assert db_session.get(Payable, payable_b_id) is not None


def test_empty_accounts_list_does_not_retire_anything(db_session, user):
    """Resposta vazia da Pluggy é sinal ambíguo (glitch), não "cartão
    nenhum existe mais" — não pode apagar fatura/payable de ninguém."""
    acc = _account(db_session, user)
    _sync_two_cards(db_session, acc, ["card-a"])

    with (
        patch("app.services.bank_sync_service.get_api_client", return_value=_ctx()),
        patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
    ):
        mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[])
        result = bank_sync_service.sync_account(db_session, acc)

    assert result["retired_open_bills"] == 0
    remaining = (
        db_session.execute(
            select(CreditCardBill).where(
                CreditCardBill.user_id == user.id,
                CreditCardBill.status == CreditCardBillStatus.OPEN,
            )
        )
        .scalars()
        .all()
    )
    assert len(remaining) == 1
