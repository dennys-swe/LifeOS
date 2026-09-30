"""Limite consolidado dos cartões: total, usado, disponível e % usado (#204).

Semântica confirmada contra a API real (#196, `tests/fixtures/pluggy/README.md`):

- o limite é da **conta da Pluggy** e compartilhado entre os cartões dela; a soma é por
  `pluggy_account_id`, nunca por cartão nem por `disaggregatedCreditLimits` (que repete o
  mesmo limite por final de cartão e inflaria o total);
- usado = `credit_limit - available_credit_limit`, que coincidiu com `balance` em todos os
  cartões testados. Não é o valor da fatura: inclui parcelas futuras.

Lê a última foto de cada conta (`account_balance_snapshots`, #197). Cartão marcado como
ignorado (`IgnoredCard`) fica fora do total, e o resultado conta quantos ficaram de fora para
não parecer divergência com o painel da Pluggy, que soma tudo. O dado de um cartão vale tanto
quanto a conexão dele: a idade vem de `connection_freshness` (#214).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account_balance_snapshot import AccountBalanceSnapshot
from app.models.bank_account import BankAccount
from app.models.credit_card_bill import CreditCardBill
from app.services import bill_service
from app.services.connection_freshness import (
    ATTENTION,
    FRESH,
    STALE,
    UNKNOWN,
    assess_connection_freshness,
)

OK = "ok"
NO_LIMIT = "no_limit"
INCONSISTENT = "inconsistent"

_CENTS = Decimal("0.01")
# Do mais grave ao menos: o pior estado entre os cartões vira o do conjunto.
_FRESHNESS_ORDER = (ATTENTION, STALE, UNKNOWN, FRESH)


@dataclass(frozen=True)
class CardLimit:
    pluggy_account_id: str
    bank_account_id: UUID
    label: str
    status: str  # ok | no_limit | inconsistent
    credit_limit: Optional[Decimal]
    available: Optional[Decimal]
    used: Optional[Decimal]
    used_pct: Optional[float]
    captured_at: datetime
    freshness_state: str


@dataclass(frozen=True)
class CardLimitsSummary:
    cards: list[CardLimit] = field(default_factory=list)
    total_limit: Decimal = Decimal("0.00")
    total_used: Decimal = Decimal("0.00")
    total_available: Decimal = Decimal("0.00")
    used_pct: Optional[float] = None
    cards_counted: int = 0
    cards_ignored: int = 0
    cards_without_limit: int = 0
    cards_inconsistent: int = 0
    freshness_state: str = FRESH


def _pct(part: Decimal, whole: Decimal) -> Optional[float]:
    return round(float(part) / float(whole) * 100, 1) if whole > 0 else None


def _status(limit: Optional[Decimal], available: Optional[Decimal]) -> str:
    """`no_limit`: o banco não informou (ou limite zerado, ex: cartão em cancelamento).
    `inconsistent`: disponível negativo ou maior que o total; não entra na soma."""
    if limit is None or available is None or limit <= 0:
        return NO_LIMIT
    if available < 0 or available > limit:
        return INCONSISTENT
    return OK


def _latest_credit_snapshots(db: Session, user_id: UUID) -> list[AccountBalanceSnapshot]:
    latest = (
        select(
            AccountBalanceSnapshot.pluggy_account_id.label("pid"),
            func.max(AccountBalanceSnapshot.captured_at).label("ts"),
        )
        .where(
            AccountBalanceSnapshot.user_id == user_id,
            AccountBalanceSnapshot.account_type == "CREDIT",
        )
        .group_by(AccountBalanceSnapshot.pluggy_account_id)
        .subquery()
    )
    rows = db.execute(
        select(AccountBalanceSnapshot)
        .join(
            latest,
            (AccountBalanceSnapshot.pluggy_account_id == latest.c.pid)
            & (AccountBalanceSnapshot.captured_at == latest.c.ts),
        )
        .where(AccountBalanceSnapshot.user_id == user_id)
        .order_by(AccountBalanceSnapshot.pluggy_account_id)
    ).scalars()
    # Duas fotos no mesmo instante exato (raro) não podem contar o limite duas vezes.
    by_account: dict[str, AccountBalanceSnapshot] = {}
    for row in rows:
        by_account.setdefault(row.pluggy_account_id, row)
    return list(by_account.values())


def _labels(db: Session, user_id: UUID) -> dict[str, str]:
    """Apelido do cartão: o mesmo que a tela de faturas usa (`custom_card_name` > `card_name`)."""
    bills = db.execute(
        select(CreditCardBill)
        .where(CreditCardBill.user_id == user_id)
        .order_by(CreditCardBill.due_date.desc())
    ).scalars()
    labels: dict[str, str] = {}
    for bill in bills:
        labels.setdefault(bill.pluggy_account_id, bill.custom_card_name or bill.card_name or "")
    return {k: v for k, v in labels.items() if v}


def get_card_limits(
    db: Session, user_id: UUID, *, now: Optional[datetime] = None
) -> CardLimitsSummary:
    snapshots = _latest_credit_snapshots(db, user_id)
    ignored_ids = bill_service.list_ignored_pluggy_account_ids(db, user_id)
    labels = _labels(db, user_id)
    connections = {
        c.id: c
        for c in db.execute(select(BankAccount).where(BankAccount.user_id == user_id)).scalars()
    }

    cards: list[CardLimit] = []
    ignored_count = 0
    for snap in snapshots:
        if snap.pluggy_account_id in ignored_ids:
            ignored_count += 1
            continue
        conn = connections.get(snap.bank_account_id)
        freshness = assess_connection_freshness(
            item_checked_at=conn.item_checked_at if conn else None,
            item_status=conn.item_status if conn else None,
            item_user_action=conn.item_user_action if conn else None,
            item_last_updated_at=conn.item_last_updated_at if conn else None,
            item_next_auto_sync_at=conn.item_next_auto_sync_at if conn else None,
            consent_expires_at=conn.consent_expires_at if conn else None,
            now=now,
        )
        limit, available = snap.credit_limit, snap.available_credit_limit
        status = _status(limit, available)
        used = (limit - available).quantize(_CENTS) if status == OK else None
        cards.append(
            CardLimit(
                pluggy_account_id=snap.pluggy_account_id,
                bank_account_id=snap.bank_account_id,
                label=labels.get(snap.pluggy_account_id, "Cartão"),
                status=status,
                credit_limit=limit,
                available=available,
                used=used,
                used_pct=_pct(used, limit) if used is not None else None,
                captured_at=snap.captured_at,
                freshness_state=freshness.state,
            )
        )

    counted = [c for c in cards if c.status == OK]
    total_limit = sum((c.credit_limit for c in counted), Decimal("0.00"))
    total_used = sum((c.used for c in counted), Decimal("0.00"))
    states = {c.freshness_state for c in counted}
    worst = next((s for s in _FRESHNESS_ORDER if s in states), FRESH)

    return CardLimitsSummary(
        cards=cards,
        total_limit=total_limit,
        total_used=total_used,
        total_available=total_limit - total_used,
        used_pct=_pct(total_used, total_limit),
        cards_counted=len(counted),
        cards_ignored=ignored_count,
        cards_without_limit=sum(1 for c in cards if c.status == NO_LIMIT),
        cards_inconsistent=sum(1 for c in cards if c.status == INCONSISTENT),
        freshness_state=worst,
    )
