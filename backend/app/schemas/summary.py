from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class CategorySummary(BaseModel):
    category_id: Optional[UUID]
    category_name: str
    color_hex: str
    # Gasto real da categoria: só transações EXPENSE, sem transferência. É a
    # resposta para "pra onde vai meu dinheiro". Substituiu `total_transactions`,
    # que somava receita e despesa no mesmo número e portanto não servia pra nada.
    total_expenses: Decimal
    transaction_count: int
    # Compromissos da categoria (contas a pagar). Nunca somar com total_expenses:
    # a fatura do cartão é um payable e as compras dela são transações — seria a
    # mesma grana duas vezes.
    total_payables: Decimal
    budget_limit: Optional[Decimal] = None
    budget_used_pct: Optional[float] = None


class SummaryResponse(BaseModel):
    total_income: Decimal
    total_expenses: Decimal
    total_pending: Decimal
    total_paid: Decimal
    balance: Decimal
    by_category: List[CategorySummary]


class MonthSummary(BaseModel):
    month: int
    year: int
    total_income: Decimal
    total_expenses: Decimal
    total_pending: Decimal
    total_paid: Decimal
    balance: Decimal


class HistoryResponse(BaseModel):
    months: List[MonthSummary]
