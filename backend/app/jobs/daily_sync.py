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

            # Os try/except abaixo são amplos de propósito: o job roda pra
            # todos os usuários numa só execução, então cada etapa isola sua
            # falha — a falha de UMA conta (ou de UM usuário, ou só do push)
            # não pode derrubar o processamento de todo o resto. `errors`
            # conta quantas vezes isso aconteceu e `.exception` garante que
            # nada fica sem rastro no log/Sentry.

            # Fase 1: reivindica o lock de cada conta sem commitar uma a uma
            # (commit=False) — commitar a cada conta expiraria (via
            # expire_on_commit da sessão) as outras contas e o `user` já
            # carregados neste laço, forçando um SELECT implícito extra por
            # conta seguinte só pra reler atributos que não mudaram (mesmo
            # cuidado de `sync_all_bank_accounts`, que tem até teste contando
            # queries pra isso).
            # Capturado antes do commit do lote abaixo: acessar `.id` num
            # objeto expirado por `expire_on_commit` dispara um SELECT de
            # reload por atributo, mesmo pra só ler a primary key.
            user_id = user.id
            claimed_pairs: list[tuple] = []
            for account in accounts:
                try:
                    # savepoint (não a transação inteira): se ESTA conta
                    # falhar ao reivindicar o lock, só o savepoint dela
                    # desfaz — sem isso, um `db.rollback()` aqui apagava
                    # também o UPDATE (ainda não commitado) de contas
                    # anteriores deste mesmo usuário que já tinham ganhado o
                    # lock com sucesso neste laço (achado no code-review).
                    with db.begin_nested():
                        # `try_start_sync` (issue #114) evita a mesma corrida
                        # que já existia entre este cron e um sync
                        # manual/automático da mesma conta: sem reivindicar o
                        # lock aqui, os dois podiam sincronizar ao mesmo
                        # tempo, colidir em uq_transactions_user_id_source, e
                        # o `run_sync_job` do lado do usuário marcava
                        # ERROR/"Falha ao sincronizar" numa conta que na
                        # verdade o cron sincronizou com sucesso. Perder a
                        # corrida aqui não é erro — só significa que outra
                        # sync já está cuidando desta conta agora; o cron de
                        # amanhã (ou o próximo sync automático por
                        # staleness) cobre o resto.
                        won = bank_sync_service.try_start_sync(db, account, commit=False)
                except Exception as exc:
                    # Uma falha de verdade aqui (ex: erro transitório de
                    # conexão no UPDATE) não pode propagar pra fora dos dois
                    # `for` e abortar TODO o resto do job (outras contas,
                    # outros usuários) — isolada igual as outras etapas.
                    errors += 1
                    logger.exception(
                        "falha ao reivindicar lock de sync (user=%s account=%s): %s",
                        user.id,
                        account.id,
                        exc,
                    )
                    continue
                if won:
                    claimed_pairs.append((account.id, user_id))
                else:
                    logger.info(
                        "sync pulado (já em andamento): user=%s account=%s", user_id, account.id
                    )

            try:
                db.commit()
            except Exception as exc:
                db.rollback()
                errors += 1
                logger.exception(
                    "falha ao commitar lote de locks de sync (user=%s): %s", user_id, exc
                )
                # Nada do lote persistiu de verdade — rodar `run_sync_job`
                # pra essas contas agora seria fazer o sync sem o lock
                # realmente gravado no banco. Mais seguro pular a fase 2
                # deste usuário; o próximo sync (staleness/foco/manual) tenta
                # de novo pra cada conta.
                claimed_pairs = []

            # Fase 2: roda cada conta reivindicada. Chama `run_sync_job` (a
            # mesma função que o sync manual e o automático usam) em vez de
            # reimplementar a transição SYNCING → IDLE/ERROR aqui — evita as
            # duas cópias divergirem com o tempo. Abre sua própria sessão
            # (isolada de `db`, compartilhado pelo job inteiro), então uma
            # falha de commit dentro dela nunca deixa `db` numa transação
            # abortada pro resto do laço. Itera sobre os ids capturados acima
            # (não sobre os objetos `account`/`user`, expirados pelo commit).
            # `run_sync_job` já nunca deixa uma exceção escapar, mas o
            # try/except aqui é defesa em profundidade — a mesma garantia de
            # isolamento por conta que toda outra etapa deste laço tem.
            for account_id, uid in claimed_pairs:
                try:
                    success = bank_sync_service.run_sync_job(account_id, uid)
                except Exception as exc:
                    errors += 1
                    logger.exception(
                        "run_sync_job falhou de forma inesperada (account=%s user=%s): %s",
                        account_id,
                        uid,
                        exc,
                    )
                    continue
                if success:
                    synced_accounts += 1
                else:
                    errors += 1

            try:
                recurring_service.generate_for_month(
                    db, user_id, month=today.month, year=today.year
                )
            except Exception as exc:
                db.rollback()
                errors += 1
                logger.exception("generate_for_month falhou (user=%s): %s", user_id, exc)

            try:
                push_service.send_upcoming_notifications(db, user_id, days=3)
            except Exception as exc:
                db.rollback()
                errors += 1
                logger.exception("push falhou (user=%s): %s", user_id, exc)

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
