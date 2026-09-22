"""Issue #134: trava contra regressão de N+1 em `detect_recurring_candidates`,
depois das otimizações das issues #131 (só as colunas usadas) e #132 (janela
de 18 meses). O nº de queries tem que ser fixo — não pode crescer com o
volume de transações do usuário."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.models.transaction import Transaction, TransactionType
from app.services.recurring_detection_service import detect_recurring_candidates
from tests.conftest import count_select_queries


def _month_date(index: int, day: int = 5) -> dt.date:
    """`index`-ésimo mês a partir de janeiro/2026, sempre no mesmo dia — evita
    o desvio de dia-do-mês (`MAX_DAY_DEVIATION`) que uma soma ingênua de dias
    fixos introduziria em meses de tamanhos diferentes."""
    year = 2026 + (index // 12)
    month = index % 12 + 1
    return dt.date(year, month, day)


def _seed_months(db_session, user, description: str, months: int) -> None:
    for i in range(months):
        db_session.add(
            Transaction(
                user_id=user.id,
                date=_month_date(i),
                description=description,
                amount=Decimal("50.00"),
                type=TransactionType.EXPENSE,
                source=f"pluggy:{description}-{i}",
            )
        )
    db_session.commit()


def test_detect_recurring_candidates_query_count_does_not_grow_with_volume(db_session, user):
    _seed_months(db_session, user, "ASSINATURA A", 4)
    _, small = count_select_queries(
        db_session, lambda: detect_recurring_candidates(db_session, user.id)
    )

    for i in range(10):
        _seed_months(db_session, user, f"ASSINATURA {i}", 4)
    _, large = count_select_queries(
        db_session, lambda: detect_recurring_candidates(db_session, user.id)
    )

    assert len(small) == len(large)


def test_detect_recurring_candidates_still_finds_pattern(db_session, user):
    _seed_months(db_session, user, "NETFLIX", 4)

    suggestions = detect_recurring_candidates(db_session, user.id)

    assert len(suggestions) == 1
    assert suggestions[0].title == "NETFLIX"
    assert suggestions[0].occurrences == 4
