"""Issue #134: trava contra regressão de N+1 em `suggest_pending`, depois das
otimizações das issues #129 (janela de datas) e #130 (hash join por valor
exato em `suggest_reconciliation`). O nº de queries tem que ser fixo — não
pode crescer com o volume de transações/payables do usuário."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType
from app.services.reconciliation_service import suggest_pending
from tests.conftest import count_select_queries


def _seed(db_session, user, n: int, offset: int = 0) -> None:
    """`n` payables PENDING + `n` transações que NÃO batem com nenhum deles
    (valor fora de qualquer payable) — garante volume sem gerar sugestão
    nenhuma, então `auto_reconcile_confident_matches` não confirma nada e não
    soma queries variáveis de `confirm_reconciliation` ao total."""
    for i in range(offset, offset + n):
        db_session.add(
            Payable(
                user_id=user.id,
                title=f"Conta {i}",
                amount=Decimal("100.00"),
                due_date=dt.date(2026, 8, 15),
                status=PayableStatus.PENDING,
            )
        )
        db_session.add(
            Transaction(
                user_id=user.id,
                date=dt.date(2026, 8, 15),
                description=f"transação {i}",
                amount=Decimal("999.00"),
                type=TransactionType.EXPENSE,
                source=f"pluggy:tx-{i}",
            )
        )
    db_session.commit()


def test_suggest_pending_query_count_does_not_grow_with_volume(db_session, user):
    _seed(db_session, user, 5)
    _, small = count_select_queries(db_session, lambda: suggest_pending(db_session, user.id))

    _seed(db_session, user, 50, offset=5)
    _, large = count_select_queries(db_session, lambda: suggest_pending(db_session, user.id))

    assert len(small) == len(large)


def test_suggest_pending_still_finds_matches(db_session, user):
    # Data 3 dias fora do vencimento (dentro da tolerância de 7, mas não
    # exata) — gera confidence 0.8, que fica como sugestão manual em vez de
    # ser auto-confirmada (só confidence 1.0 é auto-confirmada), então dá pra
    # checar o retorno de `suggest_pending` sem o payable já sair PAID.
    db_session.add(
        Payable(
            user_id=user.id,
            title="Água",
            amount=Decimal("120.50"),
            due_date=dt.date(2026, 8, 10),
            status=PayableStatus.PENDING,
        )
    )
    db_session.add(
        Transaction(
            user_id=user.id,
            date=dt.date(2026, 8, 13),
            description="pagamento água",
            amount=Decimal("120.50"),
            type=TransactionType.EXPENSE,
            source="pluggy:agua-1",
        )
    )
    db_session.commit()

    suggestions = suggest_pending(db_session, user.id)

    assert len(suggestions) == 1
    assert suggestions[0].confidence_score == 0.8
