from __future__ import annotations

from datetime import date
from unittest.mock import patch

from app.core.config import settings
from app.jobs.daily_sync import run
from app.models.bank_account import BankAccount
from app.schemas.recurring_payable import RecurringPayableCreate
from app.services.recurring_service import create_recurring


def test_run_with_no_users(db_session):
    result = run(db_session)
    assert result == {"processed_users": 0, "synced_accounts": 0, "errors": 0}


def test_run_claims_multiple_accounts_without_extra_selects(db_session, user):
    """Mesmo achado do code-review da issue #114 que motivou `commit=False`
    em `sync_all_bank_accounts`: reivindicar o lock de cada conta com commit
    individual expiraria (via `expire_on_commit`) as outras contas já
    carregadas no laço, forçando um SELECT implícito extra por conta
    seguinte. A fase de reivindicação de `daily_sync.run` faz um commit só
    pro lote inteiro do usuário."""
    from sqlalchemy import event

    acc1 = BankAccount(
        user_id=user.id,
        name="Conta 1",
        bank_name="Banco",
        account_type="checking",
        external_id="item-1",
    )
    acc2 = BankAccount(
        user_id=user.id,
        name="Conta 2",
        bank_name="Banco",
        account_type="checking",
        external_id="item-2",
    )
    db_session.add_all([acc1, acc2])
    db_session.commit()

    selects = []
    engine = db_session.get_bind()

    def _capture(conn, cursor, statement, parameters, context, executemany):
        if statement.strip().upper().startswith("SELECT") and "bank_accounts" in statement:
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    try:
        with patch(
            "app.jobs.daily_sync.bank_sync_service.run_sync_job", return_value=True
        ) as mock_job:
            result = run(db_session)
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert result["synced_accounts"] == 2
    assert mock_job.call_count == 2
    # 1 SELECT em bank_accounts (a listagem inicial das contas do usuário) —
    # sem o commit único por lote, cada conta reivindicada expiraria a outra
    # e forçaria mais 1 SELECT por conta seguinte.
    assert len(selects) == 1, f"esperava 1 SELECT em bank_accounts, vieram {len(selects)}"


def test_run_processes_user_and_generates_recurring_payables(db_session, user):
    today = date.today()
    create_recurring(
        db_session,
        user.id,
        RecurringPayableCreate(
            title="Academia",
            amount=100,
            day_of_month=1,
            active=True,
            start_date=date(today.year, 1, 1),
        ),
    )

    result = run(db_session)

    assert result["processed_users"] == 1
    assert result["synced_accounts"] == 0

    from app.models.payable import Payable

    generated = (
        db_session.query(Payable)
        .filter(Payable.user_id == user.id, Payable.title == "Academia")
        .all()
    )
    assert len(generated) == 1


def test_run_catches_sync_errors_per_account(db_session, user):
    acc = BankAccount(
        user_id=user.id,
        name="Conta",
        bank_name="Banco",
        account_type="checking",
        external_id="item-123",
    )
    db_session.add(acc)
    db_session.commit()

    with patch("app.jobs.daily_sync.bank_sync_service.sync_account", side_effect=Exception("boom")):
        result = run(db_session)

    assert result["processed_users"] == 1
    assert result["errors"] >= 1

    db_session.refresh(acc)
    assert acc.sync_status.value == "ERROR"
    assert "Falha ao sincronizar" in acc.last_sync_error


def test_run_skips_account_already_being_synced_elsewhere(db_session, user):
    """Achado no code-review da issue #114: o cron chamava `sync_account`
    direto, sem reivindicar o lock de `try_start_sync` — uma corrida com um
    sync manual/automático da mesma conta rodando ao mesmo tempo podia
    colidir em `uq_transactions_user_id_source`, e o lado do usuário marcava
    ERROR numa conta que na verdade o cron sincronizou com sucesso."""
    from datetime import datetime, timezone

    from app.models.bank_account import BankAccountSyncStatus

    acc = BankAccount(
        user_id=user.id,
        name="Conta",
        bank_name="Banco",
        account_type="checking",
        external_id="item-123",
        sync_status=BankAccountSyncStatus.SYNCING,
        sync_started_at=datetime.now(timezone.utc),
    )
    db_session.add(acc)
    db_session.commit()

    with patch("app.jobs.daily_sync.bank_sync_service.sync_account") as mock_sync:
        result = run(db_session)

    mock_sync.assert_not_called()
    assert result["synced_accounts"] == 0
    assert result["errors"] == 0

    db_session.refresh(acc)
    assert acc.sync_status == BankAccountSyncStatus.SYNCING  # não mexeu no lock de outro


def test_run_isolates_a_failed_lock_claim_from_the_rest_of_the_job(db_session, user):
    """Achado no code-review: `try_start_sync` sem try/except no laço fazia
    uma falha transitória (ex: erro de conexão no UPDATE) propagar pros dois
    `for` e abortar o job inteiro — contrariando o próprio comentário do
    arquivo ("falha de UMA conta não pode derrubar o resto"). Duas contas do
    mesmo usuário: a 1ª falha ao reivindicar o lock, a 2ª e o resto do job
    (generate_for_month) continuam normalmente."""
    from app.models.payable import Payable

    acc1 = BankAccount(
        user_id=user.id,
        name="Conta 1",
        bank_name="Banco",
        account_type="checking",
        external_id="item-1",
    )
    acc2 = BankAccount(
        user_id=user.id,
        name="Conta 2",
        bank_name="Banco",
        account_type="checking",
        external_id="item-2",
    )
    db_session.add_all([acc1, acc2])
    db_session.commit()

    create_recurring(
        db_session,
        user.id,
        RecurringPayableCreate(
            title="Academia",
            amount=100,
            day_of_month=1,
            active=True,
            start_date=date(date.today().year, 1, 1),
        ),
    )

    real_try_start_sync = __import__(
        "app.services.bank_sync_service", fromlist=["try_start_sync"]
    ).try_start_sync
    call_count = {"n": 0}

    def _fail_once_then_real(db, account, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("erro transitório de conexão")
        return real_try_start_sync(db, account, **kwargs)

    with (
        patch(
            "app.jobs.daily_sync.bank_sync_service.try_start_sync",
            side_effect=_fail_once_then_real,
        ),
        patch("app.jobs.daily_sync.bank_sync_service.run_sync_job", return_value=True) as mock_job,
    ):
        result = run(db_session)

    assert result["errors"] == 1
    assert result["synced_accounts"] == 1
    mock_job.assert_called_once()

    generated = (
        db_session.query(Payable)
        .filter(Payable.user_id == user.id, Payable.title == "Academia")
        .all()
    )
    assert len(generated) == 1  # o resto do job pro mesmo usuário não foi abortado


def test_run_does_not_lose_an_earlier_successful_claim_when_a_later_one_fails(db_session, user):
    """Achado no code-review: um `db.rollback()` sem savepoint desfaz a
    TRANSAÇÃO INTEIRA, não só a conta que falhou — se a conta A já tivesse
    ganhado o lock (UPDATE ainda não commitado) e a conta B falhasse
    DEPOIS, o rollback também desfazia o claim de A, que `claimed_pairs`
    continuava achando válido. `db.begin_nested()` isola cada tentativa no
    seu próprio savepoint, então só o de B desfaz."""
    from app.models.bank_account import BankAccountSyncStatus

    acc_a = BankAccount(
        user_id=user.id,
        name="Conta A",
        bank_name="Banco",
        account_type="checking",
        external_id="item-a",
    )
    acc_b = BankAccount(
        user_id=user.id,
        name="Conta B",
        bank_name="Banco",
        account_type="checking",
        external_id="item-b",
    )
    db_session.add_all([acc_a, acc_b])
    db_session.commit()

    real_try_start_sync = __import__(
        "app.services.bank_sync_service", fromlist=["try_start_sync"]
    ).try_start_sync

    def _real_a_fail_b(db, account, **kwargs):
        if account.id == acc_b.id:
            raise Exception("erro transitório de conexão")
        return real_try_start_sync(db, account, **kwargs)

    with (
        patch(
            "app.jobs.daily_sync.bank_sync_service.try_start_sync",
            side_effect=_real_a_fail_b,
        ),
        patch("app.jobs.daily_sync.bank_sync_service.run_sync_job", return_value=True) as mock_job,
    ):
        result = run(db_session)

    assert result["errors"] == 1
    assert result["synced_accounts"] == 1
    # A foi mesmo pra fase 2 (run_sync_job) — o claim dela sobreviveu ao
    # rollback do savepoint de B.
    mock_job.assert_called_once_with(acc_a.id, user.id)

    db_session.refresh(acc_a)
    db_session.refresh(acc_b)
    assert acc_a.sync_status == BankAccountSyncStatus.SYNCING  # claim de A persistiu
    assert acc_b.sync_status == BankAccountSyncStatus.IDLE  # B nunca chegou a mudar


def test_daily_sync_endpoint_requires_secret(client):
    response = client.post("/jobs/daily-sync")
    assert response.status_code == 403


def test_daily_sync_endpoint_rejects_wrong_secret(client):
    response = client.post("/jobs/daily-sync", headers={"X-Cron-Secret": "wrong"})
    assert response.status_code == 403


def test_daily_sync_endpoint_accepts_correct_secret(client, monkeypatch):
    # O teste controla o próprio segredo — sem isso ele só passava quando havia
    # um CRON_SECRET no .env local (e falhava em qualquer ambiente limpo, CI
    # incluído).
    monkeypatch.setattr(settings, "cron_secret", "test-cron-secret")
    response = client.post("/jobs/daily-sync", headers={"X-Cron-Secret": "test-cron-secret"})
    assert response.status_code == 200
    assert "processed_users" in response.json()


def test_session_recovers_after_a_failed_commit_mid_loop(db_session, user):
    """Achado na revisão do PR da issue #8: um `db.commit()` que falha de
    verdade (não só uma exceção genérica) deixa a sessão do SQLAlchemy
    abortada até um `rollback()` explícito — sem ele, TODO o resto do job
    (outras contas, outros usuários, generate_for_month, push) quebraria
    com PendingRollbackError depois de uma única falha de commit.

    Desde a issue #114, o passo de sync em si roda numa sessão própria
    (`run_sync_job` abre a sua, isolada de `db`) — o IntegrityError simulado
    aqui nem chega a tocar `db`, então esta falha específica não poderia
    mais abortar a sessão compartilhada. O teste continua valendo pros
    outros dois passos (`generate_for_month`/push), que ainda rodam direto
    em `db` e ainda dependem do rollback explícito deles.
    """
    from app.models.transaction import Transaction, TransactionType

    acc = BankAccount(
        user_id=user.id,
        name="Conta",
        bank_name="Banco",
        account_type="checking",
        external_id="item-123",
    )
    db_session.add(acc)
    db_session.add(
        Transaction(
            user_id=user.id,
            date=date.today(),
            description="já existe",
            amount=100,
            type=TransactionType.EXPENSE,
            source="pluggy:dup",
        )
    )
    db_session.commit()

    def _fail_with_real_integrity_error(db, account):
        # Mesma violação que um IntegrityError real de
        # uq_transactions_user_id_source dispararia — dedup do sync é feito
        # em memória (issue #8) então isso só aconteceria numa corrida entre
        # dois syncs da mesma conta, mas o efeito na sessão é o mesmo.
        db.add(
            Transaction(
                user_id=user.id,
                date=date.today(),
                description="corrida",
                amount=1,
                type=TransactionType.EXPENSE,
                source="pluggy:dup",
            )
        )
        db.commit()

    create_recurring(
        db_session,
        user.id,
        RecurringPayableCreate(
            title="Academia",
            amount=100,
            day_of_month=1,
            active=True,
            start_date=date(date.today().year, 1, 1),
        ),
    )

    with patch(
        "app.jobs.daily_sync.bank_sync_service.sync_account",
        side_effect=_fail_with_real_integrity_error,
    ):
        result = run(db_session)

    assert result["errors"] >= 1
    # a sessão se recuperou: generate_for_month rodou depois do commit
    # falho e gerou o payable normalmente, em vez de propagar
    # PendingRollbackError pro resto do job
    from app.models.payable import Payable

    generated = (
        db_session.query(Payable)
        .filter(Payable.user_id == user.id, Payable.title == "Academia")
        .all()
    )
    assert len(generated) == 1
