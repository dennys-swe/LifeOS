from __future__ import annotations

import logging
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


logger = logging.getLogger(__name__)


def run(db: Optional[Session] = None) -> dict:
    owns_session = db is None
    if db is None:
        db = SessionLocal()

    processed_users = 0
    synced_accounts = 0
    errors = 0

    try:
        users = (
            db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            .scalars()
            .all()
        )
        today = date.today()
        logger.info("daily_sync iniciado: %s usuário(s) ativo(s)", len(users))

        for user in users:
            processed_users += 1

            accounts = (
                db.execute(
                    select(BankAccount).where(
                        BankAccount.user_id == user.id,
                        BankAccount.external_id.is_not(None),
                    )
                )
                .scalars()
                .all()
            )

            # Os três try/except abaixo são amplos de propósito: o job roda
            # pra todos os usuários numa só execução, então cada um isola sua
            # etapa — a falha de UM usuário (ou de UMA conta, ou só do push)
            # não pode derrubar o processamento de todo o resto. `errors`
            # conta quantas vezes isso aconteceu e `.exception` garante que
            # nada fica sem rastro no log/Sentry.
            for account in accounts:
                try:
                    bank_sync_service.sync_account(db, account)
                    synced_accounts += 1
                except Exception as exc:
                    # Sem o rollback, um commit que falha (ex: IntegrityError
                    # de uq_transactions_user_id_source — issue #8 — numa
                    # corrida entre este cron e um sync manual da mesma
                    # conta) deixa a sessão abortada pro resto do laço: toda
                    # query seguinte, de qualquer usuário, falharia com
                    # PendingRollbackError. `db` é compartilhado pela
                    # execução inteira do job, não por usuário/conta.
                    db.rollback()
                    errors += 1
                    logger.exception(
                        "sync falhou (user=%s account=%s): %s", user.id, account.id, exc
                    )

            try:
                recurring_service.generate_for_month(
                    db, user.id, month=today.month, year=today.year
                )
            except Exception as exc:
                db.rollback()
                errors += 1
                logger.exception("generate_for_month falhou (user=%s): %s", user.id, exc)

            try:
                push_service.send_upcoming_notifications(db, user.id, days=3)
            except Exception as exc:
                db.rollback()
                errors += 1
                logger.exception("push falhou (user=%s): %s", user.id, exc)

    finally:
        if owns_session:
            db.close()

    result = {
        "processed_users": processed_users,
        "synced_accounts": synced_accounts,
        "errors": errors,
    }
    logger.info("daily_sync concluído: %s", result)
    return result


if __name__ == "__main__":
    from app.core.observability import configure_logging, init_sentry

    configure_logging()
    init_sentry()
    run()
