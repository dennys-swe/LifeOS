"""Classificação das transações importadas da Pluggy: tipo, transferência e categoria.

O bug que motivou esses testes: o tipo era inferido do **sinal** do valor, mas o
sinal não é consistente entre tipos de conta — em cartão de crédito a compra vem
positiva. Resultado nos dados reais: 1584 transações que a Pluggy marca DEBIT
estavam gravadas como INCOME/EXPENSE ao contrário, mais da metade do extrato.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.bank_account import BankAccount
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.services import bank_sync_service
from app.services.pluggy_category_map import (
    PLUGGY_TO_CATEGORY,
    TRANSFER_CATEGORIES,
    category_name_for,
    is_transfer,
)


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


def _raw_page(txs):
    return SimpleNamespace(
        data=json.dumps({"results": txs, "totalPages": 1}).encode()
    )


def _tx(tx_id, amount, description, *, tipo=None, category=None, dia="2026-07-10"):
    payload = {
        "id": tx_id,
        "amount": amount,
        "description": description,
        "date": f"{dia}T00:00:00Z",
    }
    if tipo is not None:
        payload["type"] = tipo
    if category is not None:
        payload["category"] = category
    return payload


def _ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _sync(db, acc, txs, *, account_type="BANK"):
    pluggy_acct = SimpleNamespace(id=str(uuid4()), type=account_type, name="conta")
    with (
        patch("app.services.bank_sync_service.get_api_client", return_value=_ctx()),
        patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
    ):
        mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
            results=[pluggy_acct]
        )
        mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _raw_page(txs)
        return bank_sync_service.sync_account(db, acc)


# ---------------------------------------------------------------------------
# Tipo: vem do campo `type` da Pluggy, não do sinal
# ---------------------------------------------------------------------------

def test_credit_card_purchase_is_expense_despite_positive_amount(db_session, user):
    """O bug original: compra de cartão vem POSITIVA com type=DEBIT."""
    acc = _account(db_session, user)

    _sync(db_session, acc, [_tx("t1", 15.99, "ANUIDADE DIFERENCIADA", tipo="DEBIT")])

    tx = db_session.query(Transaction).one()
    assert tx.type == TransactionType.EXPENSE
    assert tx.amount == Decimal("15.99")


def test_credit_type_is_income_despite_negative_amount(db_session, user):
    """E o inverso: pagamento recebido no cartão vem NEGATIVO com type=CREDIT."""
    acc = _account(db_session, user)

    _sync(db_session, acc, [_tx("t1", -670.32, "Pagamento recebido", tipo="CREDIT")])

    tx = db_session.query(Transaction).one()
    assert tx.type == TransactionType.INCOME


def test_checking_account_signs_still_work(db_session, user):
    acc = _account(db_session, user)

    _sync(
        db_session,
        acc,
        [
            _tx("t1", -10.0, "Pix enviado", tipo="DEBIT"),
            _tx("t2", 55.96, "Pix recebido", tipo="CREDIT"),
        ],
    )

    tipos = {t.description: t.type for t in db_session.query(Transaction).all()}
    assert tipos["Pix enviado"] == TransactionType.EXPENSE
    assert tipos["Pix recebido"] == TransactionType.INCOME


def test_falls_back_to_sign_when_type_absent(db_session, user):
    """Extrato CSV e contas sem `type` continuam funcionando pelo sinal."""
    acc = _account(db_session, user)

    _sync(db_session, acc, [_tx("t1", -50.0, "Sem type"), _tx("t2", 80.0, "Entrada")])

    tipos = {t.description: t.type for t in db_session.query(Transaction).all()}
    assert tipos["Sem type"] == TransactionType.EXPENSE
    assert tipos["Entrada"] == TransactionType.INCOME


# ---------------------------------------------------------------------------
# Transferência: dinheiro que só muda de lugar
# ---------------------------------------------------------------------------

def test_credit_card_payment_is_marked_transfer(db_session, user):
    acc = _account(db_session, user)

    _sync(
        db_session,
        acc,
        [_tx("t1", -396.64, "Pagamento de fatura", tipo="DEBIT", category="Credit card payment")],
    )

    tx = db_session.query(Transaction).one()
    assert tx.is_transfer is True
    assert tx.external_category == "Credit card payment"


def test_same_person_transfer_is_marked_transfer(db_session, user):
    acc = _account(db_session, user)

    _sync(
        db_session,
        acc,
        [_tx("t1", -500.0, "Transferência enviada", tipo="DEBIT", category="Same person transfer")],
    )

    assert db_session.query(Transaction).one().is_transfer is True


def test_third_party_transfer_is_a_real_expense(db_session, user):
    """PIX pra outra pessoa é gasto: o dinheiro saiu de vez."""
    acc = _account(db_session, user)

    _sync(
        db_session,
        acc,
        [_tx("t1", -80.0, "Pix enviado Maria", tipo="DEBIT", category="Transfer - PIX")],
    )

    tx = db_session.query(Transaction).one()
    assert tx.is_transfer is False
    assert tx.type == TransactionType.EXPENSE


def test_investment_is_transfer_not_expense(db_session, user):
    acc = _account(db_session, user)

    _sync(
        db_session,
        acc,
        [_tx("t1", -1000.0, "Aporte CDB", tipo="DEBIT", category="Investments")],
    )

    assert db_session.query(Transaction).one().is_transfer is True


# ---------------------------------------------------------------------------
# Categoria: aproveita a classificação que a Pluggy já entrega
# ---------------------------------------------------------------------------

def test_pluggy_category_is_mapped_to_user_category(db_session, user):
    acc = _account(db_session, user)

    _sync(
        db_session,
        acc,
        [_tx("t1", -120.0, "MERCADINHO CENTRAL", tipo="DEBIT", category="Groceries")],
    )

    tx = db_session.query(Transaction).one()
    assert tx.category_id is not None
    assert db_session.get(Category, tx.category_id).name == "Mercado"


def test_missing_default_categories_are_created_on_sync(db_session, user):
    """Quem se registrou antes de Saúde/Compras/Taxas/Seguros existirem
    precisa ganhá-las, senão a categoria da Pluggy não tem destino."""
    acc = _account(db_session, user)
    for cat in db_session.query(Category).filter(Category.name == "Saúde").all():
        db_session.delete(cat)
    db_session.commit()

    _sync(db_session, acc, [_tx("t1", -35.0, "FARMACIA CENTRAL", tipo="DEBIT", category="Pharmacy")])

    tx = db_session.query(Transaction).one()
    assert db_session.get(Category, tx.category_id).name == "Saúde"


def test_user_keyword_rule_wins_over_pluggy_category(db_session, user):
    """Regra do usuário é override explícito da classificação automática."""
    from app.schemas.category_rule import CategoryRuleCreate
    from app.services.category_rule_service import create_rule
    from app.services.category_seed import seed_default_categories

    acc = _account(db_session, user)
    seed_default_categories(db_session, user.id)
    lazer = db_session.query(Category).filter(Category.name == "Lazer").one()
    create_rule(
        db_session,
        user.id,
        CategoryRuleCreate(keyword="MERCADINHO", category_id=lazer.id, priority=10),
    )

    _sync(
        db_session,
        acc,
        [_tx("t1", -120.0, "MERCADINHO CENTRAL", tipo="DEBIT", category="Groceries")],
    )

    tx = db_session.query(Transaction).one()
    assert tx.category_id == lazer.id


def test_unmapped_category_is_stored_but_left_uncategorized(db_session, user):
    """Categoria nova da Pluggy não é adivinhada — fica sem categoria, mas o
    valor cru é guardado pra descobrir o que completar no mapa."""
    acc = _account(db_session, user)

    _sync(
        db_session,
        acc,
        [_tx("t1", -10.0, "Algo novo", tipo="DEBIT", category="Categoria Inventada")],
    )

    tx = db_session.query(Transaction).one()
    assert tx.category_id is None
    assert tx.external_category == "Categoria Inventada"


# ---------------------------------------------------------------------------
# O mapa em si
# ---------------------------------------------------------------------------

def test_map_targets_only_existing_default_categories():
    """Todo destino do mapa tem que ser uma categoria que o seed cria — senão
    a transação fica sem categoria silenciosamente."""
    from app.services.category_seed import DEFAULT_CATEGORIES

    nomes = {c["name"] for c in DEFAULT_CATEGORIES}
    destinos = set(PLUGGY_TO_CATEGORY.values())
    assert destinos <= nomes, f"destinos sem categoria correspondente: {destinos - nomes}"


def test_transfer_and_mapped_categories_do_not_overlap():
    """Uma categoria não pode ser transferência E gasto categorizado."""
    assert not (TRANSFER_CATEGORIES & set(PLUGGY_TO_CATEGORY)), (
        TRANSFER_CATEGORIES & set(PLUGGY_TO_CATEGORY)
    )


def test_helpers_handle_none():
    assert is_transfer(None) is False
    assert category_name_for(None) is None
