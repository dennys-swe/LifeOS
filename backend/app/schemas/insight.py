from __future__ import annotations

from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel

InsightSeverity = Literal["good", "warning", "neutral"]

InsightKind = Literal[
    "category_down",
    "category_up",
    "category_new",
    "biggest_expense",
    "pace",
    "budget_exceeded",
    "budget_near",
]


class Insight(BaseModel):
    """Um fato pronto para exibir, calculado no servidor.

    O texto vem montado daqui de propósito: se o frontend recalculasse os
    números, ele poderia contradizer o card ao lado dele na mesma tela.
    """

    kind: InsightKind
    severity: InsightSeverity
    title: str
    detail: str
    category_id: Optional[UUID] = None
    amount: Optional[Decimal] = None
    delta_pct: Optional[float] = None


class InsightsResponse(BaseModel):
    insights: List[Insight]
