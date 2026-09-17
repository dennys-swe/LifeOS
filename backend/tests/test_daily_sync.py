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
