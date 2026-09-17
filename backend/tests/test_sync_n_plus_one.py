"""Issue #8: o dedup do sync fazia um SELECT por transação pra checar
duplicata — uma conta com histórico longo virava centenas de round-trips
por sync. Agora carrega os `source` existentes em uma query só e checa em
memória."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import event

from app.models.bank_account import BankAccount
from app.models.transaction import Transaction, TransactionType
from app.services import bank_sync_service


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


def _tx(tx_id, amount):
    return {
        "id": tx_id,
        "amount": amount,
        "description": f"compra {tx_id}",
        "date": "2026-07-10T00:00:00Z",
        "type": "DEBIT",
    }


def _ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _sync(db, acc, txs):
    pluggy_acct = SimpleNamespace(id=str(uuid4()), type="BANK", name="conta")
    with (
        patch("app.services.bank_sync_service.get_api_client", return_value=_ctx()),
        patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
    ):
        mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
            results=[pluggy_acct]
        )
        mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = SimpleNamespace(
            data=json.dumps({"results": txs, "totalPages": 1}).encode()
        )
        return bank_sync_service.sync_account(db, acc)


def _count_dedup_selects(db_session, fn):
    """Conta só o SELECT que carrega `existing_sources` (projeta a coluna
    `source`) — não os refresh() por linha após o INSERT (`WHERE
    transactions.id = ?`, um padrão N+1 diferente, fora do escopo da issue #8)
    nem o SELECT do dedup por similaridade contra transações já persistidas
    (`_dedup_against_existing`, filtra por `source IS NOT NULL` mas projeta
    amount/description/date, não `source` — checagem pelo SELECT, não pelo
    WHERE, pra não confundir os dois)."""
    engine = db_session.get_bind()
    selects = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        normalized = " ".join(statement.split()).upper()
        if not normalized.startswith("SELECT") or "FROM TRANSACTIONS" not in normalized:
            return
        # A query de `existing_sources` projeta só essa coluna — diferente do
        # refresh() por linha (projeta todas) e do dedup por similaridade
        # (projeta amount/description/date).
        if normalized.startswith("SELECT TRANSACTIONS.SOURCE FROM TRANSACTIONS"):
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", _listener)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", _listener)
    return result, selects


def test_dedup_check_is_a_single_query_regardless_of_transaction_count(db_session, user):
    acc = _account(db_session, user)

    # histórico "longo": 50 transações já sincronizadas antes
    for i in range(50):
        db_session.add(
            Transaction(
                user_id=user.id,
                date=dt.date(2026, 1, 1),
                description=f"antiga {i}",
                amount=Decimal("1.00"),
                type=TransactionType.EXPENSE,
                source=f"pluggy:existing-{i}",
            )
        )
    db_session.commit()

    # 30 novas nesta página + 5 que já existem (reemitidas na mesma página)
    new_txs = [_tx(f"new-{i}", 10 + i) for i in range(30)]
    repeated_txs = [_tx(f"existing-{i}", 1) for i in range(5)]

    result, selects = _count_dedup_selects(
        db_session, lambda: _sync(db_session, acc, new_txs + repeated_txs)
    )

    # exatamente 1 SELECT pra carregar os sources existentes — não um por
    # transação (80 candidatas na página + 50 já no banco)
    assert len(selects) == 1
    assert result["imported"] == 30
    assert result["skipped"] == 5


def test_still_deduplicates_correctly_with_the_single_query_approach(db_session, user):
    acc = _account(db_session, user)
    db_session.add(
        Transaction(
            user_id=user.id,
            date=dt.date(2026, 1, 1),
            description="já sincronizada",
            amount=Decimal("42.00"),
            type=TransactionType.EXPENSE,
            source="pluggy:dup-1",
        )
    )
    db_session.commit()

    result = _sync(db_session, acc, [_tx("dup-1", 42), _tx("nova-1", 15)])

    assert result["imported"] == 1
    assert result["skipped"] == 1
    sources = {t.source for t in db_session.query(Transaction).all()}
    assert sources == {"pluggy:dup-1", "pluggy:nova-1"}
