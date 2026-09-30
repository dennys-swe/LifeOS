"""Grava fotos de saldo e limite a cada sync (#197).

Só grava quando algo mudou ou quando a última foto já é antiga: o sync roda várias vezes
ao dia (webhook + cron) e uma linha por execução encheria a tabela sem informação nova. A
"idade do dado" para a tela vem de `BankAccount.last_sync_at`; aqui importa a série de
valores (base da conciliação, #198).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account_balance_snapshot import AccountBalanceSnapshot

logger = logging.getLogger(__name__)

# Valores iguais à última foto só geram nova linha depois deste intervalo.
UNCHANGED_SNAPSHOT_INTERVAL = timedelta(hours=6)

_SNAPSHOT_TYPES = {"BANK", "CREDIT"}
_CENTS = Decimal("0.01")


def _money(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(_CENTS)


def _now() -> datetime:
    """UTC sem tzinfo, igual ao resto do schema (`DateTime` ingênuo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def latest_snapshot(
    db: Session, user_id: UUID, pluggy_account_id: str
) -> AccountBalanceSnapshot | None:
    return db.execute(
        select(AccountBalanceSnapshot)
        .where(
            AccountBalanceSnapshot.user_id == user_id,
            AccountBalanceSnapshot.pluggy_account_id == pluggy_account_id,
        )
        .order_by(AccountBalanceSnapshot.captured_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def record_snapshot(
    db: Session,
    user_id: UUID,
    bank_account_id: UUID,
    pluggy_account: Any,
    *,
    now: datetime | None = None,
) -> AccountBalanceSnapshot | None:
    """Grava a foto de uma conta da Pluggy; devolve `None` se não havia o que gravar.

    Aceita o objeto `Account` do SDK. Campos ausentes viram `None` (nunca zero): "o banco não
    informou" é diferente de "o saldo é zero". Conta de investimento e afins não geram foto.
    """
    account_type = getattr(pluggy_account, "type", None)
    if account_type not in _SNAPSHOT_TYPES:
        return None

    balance = _money(getattr(pluggy_account, "balance", None))
    credit_limit = available = None
    if account_type == "CREDIT":
        credit_data = getattr(pluggy_account, "credit_data", None)
        credit_limit = _money(getattr(credit_data, "credit_limit", None))
        available = _money(getattr(credit_data, "available_credit_limit", None))

    if balance is None and credit_limit is None and available is None:
        return None

    now = now or _now()
    last = latest_snapshot(db, user_id, pluggy_account.id)
    if (
        last is not None
        and (last.balance, last.credit_limit, last.available_credit_limit)
        == (balance, credit_limit, available)
        and now - last.captured_at < UNCHANGED_SNAPSHOT_INTERVAL
    ):
        return None

    snapshot = AccountBalanceSnapshot(
        user_id=user_id,
        bank_account_id=bank_account_id,
        pluggy_account_id=pluggy_account.id,
        account_type=account_type,
        balance=balance,
        credit_limit=credit_limit,
        available_credit_limit=available,
        currency=getattr(pluggy_account, "currency_code", None),
        captured_at=now,
    )
    db.add(snapshot)
    return snapshot
