from __future__ import annotations

import sys
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.bank_account import BankAccount
from app.models.user import User
from app.services import bank_sync_service, push_service, recurring_service

"""Job de sync diário — pensado para rodar como Render Cron Job
(`python -m app.jobs.daily_sync`) ou via POST /jobs/daily-sync (X-Cron-Secret).

Por usuário: sincroniza contas Pluggy conectadas (transações + faturas +
auto-reconciliação, tudo dentro de bank_sync_service.sync_account), gera os
payables do mês a partir dos recorrentes, e dispara push de contas vencendo.
Falhas em um usuário não derrubam o job inteiro.
"""


def _log(message: str) -> None:
    print(f"[daily_sync] {message}", file=sys.stderr)


def run(db: Optional[Session] = None) -> dict:
    owns_session = db is None
    if db is None:
        db = SessionLocal()

    processed_users = 0
    synced_accounts = 0
    errors = 0

    try:
        users = db.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        ).scalars().all()
        today = date.today()

        for user in users:
            processed_users += 1

            accounts = db.execute(
                select(BankAccount).where(
                    BankAccount.user_id == user.id,
                    BankAccount.external_id.is_not(None),
                )
            ).scalars().all()

            for account in accounts:
                try:
                    bank_sync_service.sync_account(db, account)
                    synced_accounts += 1
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    _log(f"sync falhou (user={user.id} account={account.id}): {exc}")

            try:
                recurring_service.generate_for_month(db, user.id, month=today.month, year=today.year)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                _log(f"generate_for_month falhou (user={user.id}): {exc}")

            try:
                push_service.send_upcoming_notifications(db, user.id, days=3)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                _log(f"push falhou (user={user.id}): {exc}")

    finally:
        if owns_session:
            db.close()

    return {"processed_users": processed_users, "synced_accounts": synced_accounts, "errors": errors}


if __name__ == "__main__":
    result = run()
    _log(f"concluído: {result}")
