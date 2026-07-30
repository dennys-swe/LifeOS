from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType
from app.schemas.summary import CategorySummary, HistoryResponse, MonthSummary, SummaryResponse
from app.services.budget_service import build_budget_map


_UNCATEGORIZED_NAME = "Sem categoria"
_UNCATEGORIZED_COLOR = "#64748B"


def is_spend(tx: Transaction) -> bool:
    """A transação conta como gasto?

    Transferência é dinheiro mudando de lugar, não consumo: somá-la contaria a
    mesma grana duas vezes (a compra no cartão E a quitação da fatura; a saída de
    uma conta E a entrada na outra).
    """
    return tx.type == TransactionType.EXPENSE and not tx.is_transfer


def aggregate_spend_by_category(
    transactions: Iterable[Transaction],
) -> tuple[dict, dict]:
    """`(gasto_por_categoria, contagem_por_categoria)`, só de gasto real.

    Compartilhado com `insight_service` para que a comparação mês a mês use
    exatamente a mesma definição de gasto que o dashboard mostra — se as duas
    divergirem, o insight contradiz o número na tela ao lado.
    """
    totals: dict = {}
    counts: dict = {}
    for tx in transactions:
        if not is_spend(tx):
            continue
        key = tx.category_id
        totals[key] = totals.get(key, Decimal("0")) + Decimal(str(tx.amount))
        counts[key] = counts.get(key, 0) + 1
    return totals, counts


def get_summary(db: Session, user_id: UUID, month: int, year: int) -> SummaryResponse:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    payables = db.execute(
        select(Payable).where(
            Payable.user_id == user_id,
            Payable.due_date >= start_date,
            Payable.due_date <= end_date,
        )
    ).scalars().all()

    transactions = db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
    ).scalars().all()

    categories = {
        cat.id: cat
        for cat in db.execute(select(Category).where(Category.user_id == user_id)).scalars().all()
    }

    total_income = Decimal("0")
    total_expenses = Decimal("0")
    total_pending = Decimal("0")
    total_paid = Decimal("0")

    payables_by_category: dict = {}
    for p in payables:
        key = p.category_id
        payables_by_category[key] = payables_by_category.get(key, Decimal("0")) + Decimal(str(p.amount))
        # OVERDUE é dívida em aberto igual a PENDING — tratá-lo como um terceiro
        # caso fazia a conta vencida desaparecer de todos os totais.
        if p.status in (PayableStatus.PENDING, PayableStatus.OVERDUE):
            total_pending += Decimal(str(p.amount))
        elif p.status == PayableStatus.PAID:
            total_paid += Decimal(str(p.amount))

    spend_by_category, count_by_category = aggregate_spend_by_category(transactions)
    for t in transactions:
        if t.is_transfer:
            continue
        if t.type == TransactionType.INCOME:
            total_income += Decimal(str(t.amount))
        else:
            total_expenses += Decimal(str(t.amount))

    budget_map = build_budget_map(db, user_id=user_id, month=month, year=year)
    # Orçamento definido e ainda não consumido precisa aparecer — é justamente o
    # caso em que o usuário quer ver "R$ 0 de R$ 400".
    all_keys = (
        set(payables_by_category)
        | set(spend_by_category)
        | set(budget_map)
    )

    by_category = []
    for key in all_keys:
        if key and key in categories:
            cat = categories[key]
            name = cat.name
            color = cat.color_hex
        else:
            name = _UNCATEGORIZED_NAME
            color = _UNCATEGORIZED_COLOR

        spent = spend_by_category.get(key, Decimal("0"))
        budget_limit = budget_map.get(key) if key else None
        budget_used_pct = None
        if budget_limit and budget_limit > 0:
            # Usa o gasto real, não os payables: "já usei 80% do limite de
            # Mercado" só faz sentido contra o que de fato saiu da conta.
            budget_used_pct = round(float(spent / budget_limit * 100), 1)

        by_category.append(CategorySummary(
            category_id=key,
            category_name=name,
            color_hex=color,
            total_expenses=spent,
            transaction_count=count_by_category.get(key, 0),
            total_payables=payables_by_category.get(key, Decimal("0")),
            budget_limit=budget_limit,
            budget_used_pct=budget_used_pct,
        ))

    # Ordena pelo gasto: com a ordenação antiga (por payables) toda categoria que
    # só tem transação — a maioria, vinda do banco — afundava no fim da lista.
    by_category.sort(key=lambda c: (c.total_expenses, c.total_payables), reverse=True)

    return SummaryResponse(
        total_income=total_income,
        total_expenses=total_expenses,
        total_pending=total_pending,
        total_paid=total_paid,
        balance=total_income - total_expenses,
        by_category=by_category,
    )


def get_history(
    db: Session, user_id: UUID, months: int = 6, today: Optional[date] = None
) -> HistoryResponse:
    """Série mensal para o gráfico de tendência.

    Carrega o intervalo inteiro em 2 queries e agrega em memória. A versão
    anterior chamava `get_summary` uma vez por mês — `3 × months` queries, 72
    para `months=24`.
    """
    today = today or date.today()

    periodos = []
    for i in range(months - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        periodos.append((m, y))

    inicio = date(periodos[0][1], periodos[0][0], 1)
    ultimo_m, ultimo_y = periodos[-1]
    fim = date(ultimo_y, ultimo_m, monthrange(ultimo_y, ultimo_m)[1])

    transactions = db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.date >= inicio,
            Transaction.date <= fim,
        )
    ).scalars().all()

    payables = db.execute(
        select(Payable).where(
            Payable.user_id == user_id,
            Payable.due_date >= inicio,
            Payable.due_date <= fim,
        )
    ).scalars().all()

    income: dict = {}
    expenses: dict = {}
    for t in transactions:
        if t.is_transfer:
            continue
        bucket = income if t.type == TransactionType.INCOME else expenses
        chave = (t.date.month, t.date.year)
        bucket[chave] = bucket.get(chave, Decimal("0")) + Decimal(str(t.amount))

    pending: dict = {}
    paid: dict = {}
    for p in payables:
        chave = (p.due_date.month, p.due_date.year)
        if p.status in (PayableStatus.PENDING, PayableStatus.OVERDUE):
            pending[chave] = pending.get(chave, Decimal("0")) + Decimal(str(p.amount))
        elif p.status == PayableStatus.PAID:
            paid[chave] = paid.get(chave, Decimal("0")) + Decimal(str(p.amount))

    result = []
    for m, y in periodos:
        chave = (m, y)
        mes_income = income.get(chave, Decimal("0"))
        mes_expenses = expenses.get(chave, Decimal("0"))
        result.append(MonthSummary(
            month=m,
            year=y,
            total_income=mes_income,
            total_expenses=mes_expenses,
            total_pending=pending.get(chave, Decimal("0")),
            total_paid=paid.get(chave, Decimal("0")),
            balance=mes_income - mes_expenses,
        ))
    return HistoryResponse(months=result)
