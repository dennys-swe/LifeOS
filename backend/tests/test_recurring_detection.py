from __future__ import annotations

import uuid
from datetime import date

from app.models.recurring_payable import RecurringPayable
from app.models.transaction import Transaction, TransactionType
from app.services.recurring_detection_service import (
    DETECTION_WINDOW_MONTHS,
    _window_start,
    detect_recurring_candidates,
)


def _tx(db, user, description, amount, d):
    t = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        date=d,
        description=description,
        amount=amount,
        type=TransactionType.EXPENSE,
    )
    db.add(t)
    db.commit()
    return t


def test_detects_recurring_expense_across_three_months(db_session, user):
    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 3, 5))
    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 4, 5))
    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 5, 5))

    suggestions = detect_recurring_candidates(db_session, user.id)

    assert len(suggestions) == 1
    assert suggestions[0].title == "NETFLIX.COM"
    assert float(suggestions[0].amount) == 45.90
    assert suggestions[0].day_of_month == 5
    assert suggestions[0].occurrences == 3


def test_ignores_expenses_seen_in_fewer_than_three_months(db_session, user):
    _tx(db_session, user, "ACADEMIA", 100, date(2026, 3, 10))
    _tx(db_session, user, "ACADEMIA", 100, date(2026, 4, 10))

    assert detect_recurring_candidates(db_session, user.id) == []


def test_ignores_amount_outside_tolerance(db_session, user):
    _tx(db_session, user, "ALUGUEL", 1000, date(2026, 3, 10))
    _tx(db_session, user, "ALUGUEL", 1000, date(2026, 4, 10))
    _tx(db_session, user, "ALUGUEL", 1300, date(2026, 5, 10))  # 30% acima

    assert detect_recurring_candidates(db_session, user.id) == []


def test_ignores_day_outside_tolerance(db_session, user):
    _tx(db_session, user, "SPOTIFY", 21.90, date(2026, 3, 1))
    _tx(db_session, user, "SPOTIFY", 21.90, date(2026, 4, 1))
    _tx(db_session, user, "SPOTIFY", 21.90, date(2026, 5, 20))  # dia muito distante

    assert detect_recurring_candidates(db_session, user.id) == []


def test_excludes_titles_already_recurring(db_session, user):
    db_session.add(
        RecurringPayable(
            user_id=user.id,
            title="NETFLIX.COM",
            amount=45.90,
            day_of_month=5,
            active=True,
        )
    )
    db_session.commit()

    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 3, 5))
    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 4, 5))
    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 5, 5))

    assert detect_recurring_candidates(db_session, user.id) == []


def test_ignores_other_users_transactions(db_session, user, other_user):
    _tx(db_session, other_user, "NETFLIX.COM", 45.90, date(2026, 3, 5))
    _tx(db_session, other_user, "NETFLIX.COM", 45.90, date(2026, 4, 5))
    _tx(db_session, other_user, "NETFLIX.COM", 45.90, date(2026, 5, 5))

    assert detect_recurring_candidates(db_session, user.id) == []


def test_ignores_transactions_older_than_detection_window(db_session, user):
    """3 meses consecutivos de outra forma perfeitos (mesmo valor, mesmo dia)
    não geram sugestão quando caem inteiramente antes da janela de detecção
    — não seriam pegos nem no melhor caso (issue #132)."""
    m1 = _window_start(date.today(), DETECTION_WINDOW_MONTHS + 1).replace(day=10)
    m2 = _window_start(date.today(), DETECTION_WINDOW_MONTHS + 2).replace(day=10)
    m3 = _window_start(date.today(), DETECTION_WINDOW_MONTHS + 3).replace(day=10)
    _tx(db_session, user, "SEGURO ANTIGO", 200, m1)
    _tx(db_session, user, "SEGURO ANTIGO", 200, m2)
    _tx(db_session, user, "SEGURO ANTIGO", 200, m3)

    assert detect_recurring_candidates(db_session, user.id) == []


def test_includes_transaction_exactly_at_window_start(db_session, user):
    """A borda da janela é inclusiva — uma transação bem no primeiro dia do
    mês limite ainda conta (issue #132)."""
    window_start = _window_start(date.today(), DETECTION_WINDOW_MONTHS)
    m2 = _window_start(date.today(), DETECTION_WINDOW_MONTHS - 1)
    m3 = _window_start(date.today(), DETECTION_WINDOW_MONTHS - 2)
    _tx(db_session, user, "ASSINATURA LIMITE", 50, window_start)
    _tx(db_session, user, "ASSINATURA LIMITE", 50, m2)
    _tx(db_session, user, "ASSINATURA LIMITE", 50, m3)

    suggestions = detect_recurring_candidates(db_session, user.id)

    assert len(suggestions) == 1
    assert suggestions[0].title == "ASSINATURA LIMITE"


def test_suggestions_endpoint(client, db_session, user):
    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 3, 5))
    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 4, 5))
    _tx(db_session, user, "NETFLIX.COM", 45.90, date(2026, 5, 5))

    response = client.get("/recurring-payables/suggestions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "NETFLIX.COM"
