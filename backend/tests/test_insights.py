"""Regras de insight. As `_rule_*` são puras, então a maior parte dos casos
(limiar, sinal, texto) é testada sem banco."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.services.insight_service import (
    _brl,
    _prev_month,
    _rule_biggest_expense,
    _rule_budgets,
    _rule_category_changes,
    _rule_pace,
    build_insights,
    rank_insights,
)
from app.schemas.insight import Insight

CAT_A = uuid.uuid4()
CAT_B = uuid.uuid4()
NAMES = {CAT_A: "Mercado", CAT_B: "Transporte"}


def _tx(amount, *, dia=10, tipo=TransactionType.EXPENSE, transfer=False, cat=CAT_A, desc="Compra"):
    return Transaction(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        date=date(2026, 7, dia),
        description=desc,
        amount=Decimal(str(amount)),
        type=tipo,
        category_id=cat,
        is_transfer=transfer,
    )


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def test_brl_formats_thousands_ptbr():
    assert _brl(Decimal("1234.56")) == "R$ 1.234,56"
    assert _brl(Decimal("1234567.80")) == "R$ 1.234.567,80"
    assert _brl(Decimal("5")) == "R$ 5,00"


def test_brl_uses_absolute_value():
    """O sinal é dito pelo texto ("R$ 200 menos"), não pelo número."""
    assert _brl(Decimal("-200")) == "R$ 200,00"


def test_prev_month_crosses_year():
    assert _prev_month(1, 2027) == (12, 2026)
    assert _prev_month(7, 2026) == (6, 2026)


# ---------------------------------------------------------------------------
# Variação por categoria
# ---------------------------------------------------------------------------

def test_spending_less_is_a_good_insight():
    insights = _rule_category_changes(
        {CAT_A: Decimal("300")}, {CAT_A: Decimal("500")}, NAMES
    )

    assert len(insights) == 1
    assert insights[0].kind == "category_down"
    assert insights[0].severity == "good"
    assert "R$ 200,00 menos em Mercado" in insights[0].title
    assert insights[0].delta_pct == -40.0


def test_spending_more_is_a_warning():
    insights = _rule_category_changes(
        {CAT_A: Decimal("500")}, {CAT_A: Decimal("300")}, NAMES
    )

    assert insights[0].kind == "category_up"
    assert insights[0].severity == "warning"
    assert "mais em Mercado" in insights[0].title


def test_small_absolute_delta_is_ignored():
    """Variação percentual alta mas irrelevante em dinheiro não vira card."""
    insights = _rule_category_changes(
        {CAT_A: Decimal("40")}, {CAT_A: Decimal("10")}, NAMES
    )

    assert insights == []


def test_small_percentage_delta_is_ignored():
    """E o inverso: R$ 60 sobre R$ 5000 é ruído."""
    insights = _rule_category_changes(
        {CAT_A: Decimal("5060")}, {CAT_A: Decimal("5000")}, NAMES
    )

    assert insights == []


def test_new_category_is_reported_without_percentage():
    insights = _rule_category_changes({CAT_A: Decimal("250")}, {}, NAMES)

    assert insights[0].kind == "category_new"
    assert insights[0].delta_pct is None


def test_new_category_below_threshold_is_ignored():
    insights = _rule_category_changes({CAT_A: Decimal("10")}, {}, NAMES)

    assert insights == []


def test_uncategorized_uses_fallback_name():
    insights = _rule_category_changes(
        {None: Decimal("300")}, {None: Decimal("500")}, NAMES
    )

    assert "Sem categoria" in insights[0].title


# ---------------------------------------------------------------------------
# Maior gasto
# ---------------------------------------------------------------------------

def test_biggest_expense_ignores_income_and_transfer():
    txs = [
        _tx(100, desc="Mercado"),
        _tx(9000, tipo=TransactionType.INCOME, desc="Salário"),
        _tx(5000, transfer=True, desc="Entre contas"),
    ]

    insight = _rule_biggest_expense(txs, NAMES)

    assert insight is not None
    assert insight.amount == Decimal("100")
    assert "Mercado" in insight.detail


def test_biggest_expense_none_when_no_spending():
    assert _rule_biggest_expense([], NAMES) is None
    assert _rule_biggest_expense([_tx(9000, tipo=TransactionType.INCOME)], NAMES) is None


# ---------------------------------------------------------------------------
# Ritmo
# ---------------------------------------------------------------------------

def test_pace_only_applies_to_current_month():
    """Em mês fechado a comparação de totais já é dada pelas regras de categoria."""
    atual = [_tx(500, dia=5)]
    anterior = [_tx(100, dia=5)]

    assert _rule_pace(atual, anterior, date(2026, 8, 15), 7, 2026) is None


def test_pace_compares_same_window_and_projects():
    atual = [_tx(600, dia=5)]
    anterior = [_tx(300, dia=5), _tx(9999, dia=28)]  # o dia 28 fica fora da janela

    insight = _rule_pace(atual, anterior, date(2026, 7, 10), 7, 2026)

    assert insight is not None
    assert insight.severity == "warning"
    assert insight.delta_pct == 100.0
    # 600 em 10 dias -> 31 dias em julho -> 1860
    assert "R$ 1.860,00" in insight.detail


def test_pace_below_last_month_is_good():
    insight = _rule_pace([_tx(200, dia=5)], [_tx(600, dia=5)], date(2026, 7, 10), 7, 2026)

    assert insight is not None
    assert insight.severity == "good"


# ---------------------------------------------------------------------------
# Orçamento
# ---------------------------------------------------------------------------

def test_budget_exceeded():
    insights = _rule_budgets({CAT_A: Decimal("450")}, {CAT_A: Decimal("400")}, NAMES)

    assert insights[0].kind == "budget_exceeded"
    assert insights[0].amount == Decimal("50")


def test_budget_near_limit():
    insights = _rule_budgets({CAT_A: Decimal("340")}, {CAT_A: Decimal("400")}, NAMES)

    assert insights[0].kind == "budget_near"
    assert "Restam R$ 60,00" in insights[0].detail


def test_budget_comfortable_is_silent():
    assert _rule_budgets({CAT_A: Decimal("100")}, {CAT_A: Decimal("400")}, NAMES) == []


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def test_warnings_come_before_good_news():
    boas = Insight(kind="category_down", severity="good", title="a", detail="", amount=Decimal("900"))
    alerta = Insight(kind="category_up", severity="warning", title="b", detail="", amount=Decimal("60"))

    assert [i.severity for i in rank_insights([boas, alerta])] == ["warning", "good"]


def test_ranking_caps_the_list():
    muitos = [
        Insight(kind="category_up", severity="warning", title=str(i), detail="", amount=Decimal(i))
        for i in range(20)
    ]

    assert len(rank_insights(muitos)) == 6


def test_bigger_amount_first_within_same_severity():
    pequeno = Insight(kind="category_up", severity="warning", title="p", detail="", amount=Decimal("60"))
    grande = Insight(kind="category_up", severity="warning", title="g", detail="", amount=Decimal("900"))

    assert [i.title for i in rank_insights([pequeno, grande])] == ["g", "p"]


# ---------------------------------------------------------------------------
# Integração
# ---------------------------------------------------------------------------

def test_build_insights_end_to_end(db_session, user):
    mercado = Category(user_id=user.id, name="Mercado", color_hex="#84CC16")
    db_session.add(mercado)
    db_session.commit()

    def add(amount, month, dia=10, transfer=False):
        db_session.add(Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            date=date(2026, month, dia),
            description="Compra",
            amount=Decimal(str(amount)),
            type=TransactionType.EXPENSE,
            category_id=mercado.id,
            is_transfer=transfer,
        ))

    add(500, 6)
    add(200, 7)
    add(9999, 7, transfer=True)  # transferência não pode influenciar
    db_session.add(Budget(
        user_id=user.id, category_id=mercado.id, month=7, year=2026, limit_amount=100
    ))
    db_session.commit()

    insights = build_insights(db_session, user.id, month=7, year=2026, today=date(2026, 8, 1))
    kinds = {i.kind for i in insights}

    assert "category_down" in kinds  # gastou 300 menos que em junho
    assert "budget_exceeded" in kinds  # 200 de um limite de 100
    assert insights[0].severity == "warning"  # alerta primeiro


def test_insights_endpoint(client, db_session, user):
    resp = client.get("/insights?month=7&year=2026")

    assert resp.status_code == 200
    assert resp.json() == {"insights": []}


def test_insights_endpoint_isolates_users(client, db_session, user, other_user):
    cat = Category(user_id=other_user.id, name="Dele", color_hex="#000000")
    db_session.add(cat)
    db_session.commit()
    db_session.add(Transaction(
        id=uuid.uuid4(),
        user_id=other_user.id,
        date=date(2026, 7, 10),
        description="Gasto de outro",
        amount=Decimal("5000"),
        type=TransactionType.EXPENSE,
        category_id=cat.id,
    ))
    db_session.commit()

    assert client.get("/insights?month=7&year=2026").json() == {"insights": []}
