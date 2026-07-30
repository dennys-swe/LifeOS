"""Insights comparativos do mês — "você gastou R$ 200 menos em Mercado".

Calculado no servidor e já com o texto montado: se o frontend refizesse as
contas, o card poderia contradizer o número exibido ao lado dele.

As regras são funções puras sobre dados já carregados (`_rule_*`), então dá para
testá-las sem banco. `build_insights` só carrega os dados e as orquestra.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.insight import Insight
from app.services.budget_service import build_budget_map
from app.services.summary_service import aggregate_spend_by_category, is_spend

# Limiares para não gerar ruído: uma variação só vira insight se for relevante
# em valor **e** em proporção. Sem isso, R$ 3 a mais em Mercado geraria card.
MIN_DELTA_AMOUNT = Decimal("50")
MIN_DELTA_PCT = 10.0

BUDGET_NEAR_PCT = 80.0
MAX_INSIGHTS = 6

_UNCATEGORIZED = "Sem categoria"


def _brl(value: Decimal) -> str:
    """Formata em Real. Feito à mão porque depender de locale pt_BR instalado no
    contêiner do Render é frágil."""
    inteiro, _, centavos = f"{abs(Decimal(value)):.2f}".partition(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return f"R$ {'.'.join(grupos)},{centavos}"


def _pct_change(current: Decimal, previous: Decimal) -> Optional[float]:
    if previous == 0:
        return None
    return round(float((current - previous) / previous * 100), 1)


def _prev_month(month: int, year: int) -> tuple[int, int]:
    return (12, year - 1) if month == 1 else (month - 1, year)


# ---------------------------------------------------------------------------
# Regras (puras)
# ---------------------------------------------------------------------------

def _rule_category_changes(
    current: Dict[Optional[UUID], Decimal],
    previous: Dict[Optional[UUID], Decimal],
    names: Dict[Optional[UUID], str],
) -> List[Insight]:
    insights: List[Insight] = []

    for key, atual in current.items():
        anterior = previous.get(key, Decimal("0"))
        nome = names.get(key, _UNCATEGORIZED)
        delta = atual - anterior

        if anterior == 0:
            # Categoria que não existia no mês anterior: só vale avisar se o
            # valor for relevante por si só (não há percentual pra comparar).
            if atual >= MIN_DELTA_AMOUNT:
                insights.append(Insight(
                    kind="category_new",
                    severity="neutral",
                    title=f"Novo gasto em {nome}",
                    detail=f"{_brl(atual)} neste mês, e nada no mês anterior.",
                    category_id=key,
                    amount=atual,
                ))
            continue

        pct = _pct_change(atual, anterior)
        if abs(delta) < MIN_DELTA_AMOUNT or pct is None or abs(pct) < MIN_DELTA_PCT:
            continue

        if delta < 0:
            insights.append(Insight(
                kind="category_down",
                severity="good",
                title=f"{_brl(delta)} menos em {nome}",
                detail=f"{_brl(atual)} neste mês contra {_brl(anterior)} no anterior.",
                category_id=key,
                amount=abs(delta),
                delta_pct=pct,
            ))
        else:
            insights.append(Insight(
                kind="category_up",
                severity="warning",
                title=f"{_brl(delta)} mais em {nome}",
                detail=f"{_brl(atual)} neste mês contra {_brl(anterior)} no anterior.",
                category_id=key,
                amount=delta,
                delta_pct=pct,
            ))

    return insights


def _rule_biggest_expense(
    transactions: Sequence[Transaction],
    names: Dict[Optional[UUID], str],
) -> Optional[Insight]:
    gastos = [t for t in transactions if is_spend(t)]
    if not gastos:
        return None

    maior = max(gastos, key=lambda t: Decimal(str(t.amount)))
    valor = Decimal(str(maior.amount))
    if valor < MIN_DELTA_AMOUNT:
        return None

    nome = names.get(maior.category_id, _UNCATEGORIZED)
    return Insight(
        kind="biggest_expense",
        severity="neutral",
        title=f"Maior gasto: {_brl(valor)}",
        detail=f"{maior.description} — {nome}, dia {maior.date.day}.",
        category_id=maior.category_id,
        amount=valor,
    )


def _rule_pace(
    current: Sequence[Transaction],
    previous: Sequence[Transaction],
    today: date,
    month: int,
    year: int,
) -> Optional[Insight]:
    """Ritmo de gasto vs o mesmo trecho do mês anterior.

    Só faz sentido no mês corrente: em mês fechado a comparação de totais já é
    dada pelas regras de categoria.
    """
    if (today.month, today.year) != (month, year):
        return None

    dia = today.day
    gasto_ate_hoje = sum(
        (Decimal(str(t.amount)) for t in current if is_spend(t) and t.date.day <= dia),
        Decimal("0"),
    )
    gasto_anterior = sum(
        (Decimal(str(t.amount)) for t in previous if is_spend(t) and t.date.day <= dia),
        Decimal("0"),
    )

    delta = gasto_ate_hoje - gasto_anterior
    pct = _pct_change(gasto_ate_hoje, gasto_anterior)
    if abs(delta) < MIN_DELTA_AMOUNT or pct is None or abs(pct) < MIN_DELTA_PCT:
        return None

    dias_no_mes = monthrange(year, month)[1]
    projecao = (gasto_ate_hoje / dia * dias_no_mes) if dia else gasto_ate_hoje

    if delta > 0:
        return Insight(
            kind="pace",
            severity="warning",
            title=f"Ritmo {abs(pct):.0f}% acima do mês passado",
            detail=(
                f"{_brl(gasto_ate_hoje)} até o dia {dia}, contra "
                f"{_brl(gasto_anterior)} no mesmo trecho. Nesse ritmo, "
                f"{_brl(projecao)} no mês."
            ),
            amount=delta,
            delta_pct=pct,
        )
    return Insight(
        kind="pace",
        severity="good",
        title=f"Ritmo {abs(pct):.0f}% abaixo do mês passado",
        detail=(
            f"{_brl(gasto_ate_hoje)} até o dia {dia}, contra "
            f"{_brl(gasto_anterior)} no mesmo trecho. Nesse ritmo, "
            f"{_brl(projecao)} no mês."
        ),
        amount=abs(delta),
        delta_pct=pct,
    )


def _rule_budgets(
    spend: Dict[Optional[UUID], Decimal],
    budget_map: Dict[UUID, Decimal],
    names: Dict[Optional[UUID], str],
) -> List[Insight]:
    insights: List[Insight] = []
    for category_id, limite in budget_map.items():
        if not limite or limite <= 0:
            continue
        gasto = spend.get(category_id, Decimal("0"))
        pct = round(float(gasto / limite * 100), 1)
        nome = names.get(category_id, _UNCATEGORIZED)

        if pct >= 100:
            insights.append(Insight(
                kind="budget_exceeded",
                severity="warning",
                title=f"Limite de {nome} estourado",
                detail=f"{_brl(gasto)} de {_brl(limite)} ({pct:.0f}%).",
                category_id=category_id,
                amount=gasto - limite,
                delta_pct=pct,
            ))
        elif pct >= BUDGET_NEAR_PCT:
            insights.append(Insight(
                kind="budget_near",
                severity="warning",
                title=f"{pct:.0f}% do limite de {nome}",
                detail=f"{_brl(gasto)} de {_brl(limite)}. Restam {_brl(limite - gasto)}.",
                category_id=category_id,
                amount=limite - gasto,
                delta_pct=pct,
            ))
    return insights


def rank_insights(insights: List[Insight]) -> List[Insight]:
    """Alerta antes de elogio, e dentro de cada grupo o de maior valor primeiro —
    o usuário deve ver o que exige ação no topo."""
    prioridade = {"warning": 0, "good": 1, "neutral": 2}
    return sorted(
        insights,
        key=lambda i: (prioridade[i.severity], -(i.amount or Decimal("0"))),
    )[:MAX_INSIGHTS]


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def build_insights(
    db: Session, user_id: UUID, month: int, year: int, today: Optional[date] = None
) -> List[Insight]:
    today = today or date.today()
    prev_month, prev_year = _prev_month(month, year)

    current_txs = _transactions_of_month(db, user_id, month, year)
    previous_txs = _transactions_of_month(db, user_id, prev_month, prev_year)

    names: Dict[Optional[UUID], str] = {
        cat.id: cat.name
        for cat in db.execute(select(Category).where(Category.user_id == user_id)).scalars().all()
    }

    current_spend, _ = aggregate_spend_by_category(current_txs)
    previous_spend, _ = aggregate_spend_by_category(previous_txs)
    budget_map = build_budget_map(db, user_id=user_id, month=month, year=year)

    insights = _rule_budgets(current_spend, budget_map, names)
    insights += _rule_category_changes(current_spend, previous_spend, names)

    maior = _rule_biggest_expense(current_txs, names)
    if maior:
        insights.append(maior)

    ritmo = _rule_pace(current_txs, previous_txs, today, month, year)
    if ritmo:
        insights.append(ritmo)

    return rank_insights(insights)


def _transactions_of_month(
    db: Session, user_id: UUID, month: int, year: int
) -> List[Transaction]:
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return list(
        db.execute(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).scalars().all()
    )
