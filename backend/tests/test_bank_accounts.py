"""Testes manuais da integração Pluggy — endpoints e serviço de bank accounts."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.bank_account import BankAccount, BankAccountSyncStatus
from app.models.category import Category
from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType
from app.schemas.category_rule import CategoryRuleCreate
from app.services import bank_sync_service
from app.services.category_rule_service import create_rule

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account(db, user, *, external_id: str | None = None) -> BankAccount:
    acc = BankAccount(
        user_id=user.id,
        name="Conta Corrente",
        bank_name="Nubank",
        account_type="checking",
        external_id=external_id,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def _pluggy_tx(tx_id: str, amount: float, desc: str, dt: date) -> SimpleNamespace:
    return SimpleNamespace(
        id=tx_id,
        amount=amount,
        description=desc,
        date=datetime.combine(dt, datetime.min.time()),
    )


def _page(results, total_pages=1):
    return SimpleNamespace(results=results, total_pages=total_pages)


def _page_raw(results, total_pages=1):
    """Serializa transações para o formato JSON retornado por transactions_list_without_preload_content."""
    page_data = {
        "results": [
            {
                "id": tx.id,
                "amount": tx.amount,
                "description": tx.description,
                "date": tx.date.isoformat() + "Z",
            }
            for tx in results
        ],
        "totalPages": total_pages,
    }
    return SimpleNamespace(data=json.dumps(page_data).encode())


# ---------------------------------------------------------------------------
# CRUD — sem dependência da Pluggy
# ---------------------------------------------------------------------------


class TestBankAccountCRUD:
    def test_list_empty(self, client):
        r = client.get("/bank-accounts")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_and_list(self, client):
        payload = {"name": "Nubank", "bank_name": "Nu", "account_type": "checking"}
        r = client.post("/bank-accounts", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Nubank"
        assert data["account_type"] == "checking"
        assert data["last_sync_at"] is None

        r2 = client.get("/bank-accounts")
        assert len(r2.json()) == 1

    def test_create_with_external_id(self, client):
        item_id = str(uuid4())
        payload = {
            "name": "BB",
            "bank_name": "Banco do Brasil",
            "account_type": "savings",
            "external_id": item_id,
        }
        r = client.post("/bank-accounts", json=payload)
        assert r.status_code == 201
        assert r.json()["external_id"] == item_id

    def test_account_type_validation(self, client):
        payload = {"name": "X", "bank_name": "Y", "account_type": "invalid"}
        r = client.post("/bank-accounts", json=payload)
        assert r.status_code == 422

    def test_delete_existing(self, client):
        r = client.post(
            "/bank-accounts",
            json={"name": "A", "bank_name": "B", "account_type": "credit"},
        )
        acc_id = r.json()["id"]
        r2 = client.delete(f"/bank-accounts/{acc_id}")
        assert r2.status_code == 204
        assert client.get("/bank-accounts").json() == []

    def test_delete_nonexistent_returns_404(self, client):
        r = client.delete(f"/bank-accounts/{uuid4()}")
        assert r.status_code == 404

    def test_rename(self, client):
        r = client.post("/bank-accounts", json={"name": "MeuPluggy", "bank_name": "MeuPluggy"})
        acc_id = r.json()["id"]

        r2 = client.patch(f"/bank-accounts/{acc_id}", json={"name": "Nubank", "bank_name": "Nu"})
        assert r2.status_code == 200
        assert r2.json()["name"] == "Nubank"
        assert r2.json()["bank_name"] == "Nu"

    def test_rename_partial_keeps_other_fields(self, client):
        r = client.post("/bank-accounts", json={"name": "A", "bank_name": "Banco B"})
        acc_id = r.json()["id"]

        r2 = client.patch(f"/bank-accounts/{acc_id}", json={"name": "Novo"})
        assert r2.status_code == 200
        assert r2.json()["name"] == "Novo"
        assert r2.json()["bank_name"] == "Banco B"

    def test_rename_nonexistent_returns_404(self, client):
        r = client.patch(f"/bank-accounts/{uuid4()}", json={"name": "X"})
        assert r.status_code == 404

    def test_rename_rejects_empty_name(self, client):
        r = client.post("/bank-accounts", json={"name": "A", "bank_name": "B"})
        acc_id = r.json()["id"]

        r2 = client.patch(f"/bank-accounts/{acc_id}", json={"name": ""})
        assert r2.status_code == 422


# ---------------------------------------------------------------------------
# Derivação do nome — com o conector MeuPluggy o frontend só conhece
# connector.name == "MeuPluggy", igual para todo banco conectado.
# ---------------------------------------------------------------------------


class TestNameDerivation:
    def _ctx(self):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    def _pluggy_acct(self, name, acct_type="CREDIT", marketing_name=None):
        # marketing_name vem None no proxy do MeuPluggy — o nome útil está em `name`.
        return SimpleNamespace(
            id=str(uuid4()), name=name, marketing_name=marketing_name, type=acct_type
        )

    def _connect(self, client, accounts):
        with (
            patch("app.services.bank_sync_service.get_api_client", return_value=self._ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=accounts
            )
            return client.post("/bank-accounts", json={"external_id": str(uuid4())})

    def test_derives_name_from_single_account(self, client):
        r = self._connect(client, [self._pluggy_acct("banco-x", "BANK")])

        assert r.status_code == 201
        assert r.json()["name"] == "banco-x"
        assert r.json()["bank_name"] == "banco-x"

    def test_marketing_name_wins_when_present(self, client):
        r = self._connect(
            client, [self._pluggy_acct("conta", "BANK", marketing_name="Nubank Conta")]
        )

        assert r.json()["name"] == "Nubank Conta"

    def test_lists_all_accounts_of_the_item(self, client):
        """Um item do MeuPluggy agrega instituições diferentes — o rótulo lista todas."""
        r = self._connect(
            client,
            [
                self._pluggy_acct("CARTAO LOJA GOLD", "CREDIT"),
                self._pluggy_acct("banco-x", "BANK"),
                self._pluggy_acct("Cartão Múltiplo Platinum", "CREDIT"),
            ],
        )

        # BANK primeiro, mesmo tendo vindo no meio da lista da API.
        assert r.json()["name"] == "banco-x, CARTAO LOJA GOLD, Cartão Múltiplo Platinum"
        assert r.json()["bank_name"] == "banco-x"

    def test_long_label_list_is_truncated_with_count(self, client):
        accounts = [
            self._pluggy_acct(f"Cartão de crédito muito longo numero {i}") for i in range(6)
        ]

        r = self._connect(client, accounts)

        name = r.json()["name"]
        assert len(name) <= 100
        assert name.endswith("(+5)")

    def test_deduplicates_repeated_labels(self, client):
        r = self._connect(
            client, [self._pluggy_acct("banco-x", "BANK"), self._pluggy_acct("banco-x", "BANK")]
        )

        assert r.json()["name"] == "banco-x"

    def test_explicit_name_wins_over_derivation(self, client):
        item_id = str(uuid4())

        with (
            patch("app.services.bank_sync_service.get_api_client", return_value=self._ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            r = client.post(
                "/bank-accounts",
                json={"name": "Meu apelido", "bank_name": "Meu banco", "external_id": item_id},
            )

        assert r.json()["name"] == "Meu apelido"
        mock_sdk.AccountApi.return_value.accounts_list.assert_not_called()

    def test_pluggy_failure_falls_back_instead_of_erroring(self, client):
        """Conectar não pode falhar só porque não deu pra derivar o nome."""
        item_id = str(uuid4())

        with (
            patch("app.services.bank_sync_service.get_api_client", return_value=self._ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.side_effect = RuntimeError("boom")
            r = client.post("/bank-accounts", json={"external_id": item_id})

        assert r.status_code == 201
        assert r.json()["name"] == "Conta bancária"

    def test_no_external_id_uses_fallback_without_calling_pluggy(self, client):
        with patch("app.services.bank_sync_service.get_api_client") as mock_client:
            r = client.post("/bank-accounts", json={})

        assert r.status_code == 201
        assert r.json()["name"] == "Conta bancária"
        assert r.json()["bank_name"] == "Desconhecido"
        mock_client.assert_not_called()


# ---------------------------------------------------------------------------
# connect-token
# ---------------------------------------------------------------------------


class TestConnectToken:
    @patch("app.api.endpoints.bank_accounts.bank_sync_service.get_connect_token")
    def test_connect_token_without_item_id(self, mock_token, client):
        mock_token.return_value = "tok_abc123"
        r = client.post("/bank-accounts/connect-token")
        assert r.status_code == 200
        assert r.json()["access_token"] == "tok_abc123"
        mock_token.assert_called_once_with(item_id=None)

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.get_connect_token")
    def test_connect_token_with_item_id(self, mock_token, client):
        item_id = uuid4()
        mock_token.return_value = "tok_xyz"
        r = client.post(f"/bank-accounts/connect-token?item_id={item_id}")
        assert r.status_code == 200
        mock_token.assert_called_once_with(item_id=item_id)

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.get_connect_token")
    def test_connect_token_missing_credentials_returns_503(self, mock_token, client):
        mock_token.side_effect = RuntimeError(
            "PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET não configurados"
        )
        r = client.post("/bank-accounts/connect-token")
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# is_stale (issue #114)
# ---------------------------------------------------------------------------


class TestTryStartSync:
    def test_claims_lock_when_idle(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        assert bank_sync_service.try_start_sync(db_session, acc) is True
        assert acc.sync_status == BankAccountSyncStatus.SYNCING

    def test_fails_when_already_syncing(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.sync_status = BankAccountSyncStatus.SYNCING
        acc.sync_started_at = datetime.now(timezone.utc)
        db_session.add(acc)
        db_session.commit()

        assert bank_sync_service.try_start_sync(db_session, acc) is False

    def test_two_concurrent_requests_for_the_same_account_only_one_wins(self, db_session, user):
        """Corrida de verdade com uma segunda sessão contra o mesmo banco
        (StaticPool, mesmo padrão do teste de corrida do ignore_card):
        as duas leem sync_status=IDLE antes de qualquer uma escrever — só
        uma pode vencer o UPDATE atômico."""
        from sqlalchemy.orm import sessionmaker

        acc = _make_account(db_session, user, external_id=str(uuid4()))

        OtherSession = sessionmaker(bind=db_session.get_bind())
        other_session = OtherSession()
        try:
            other_account = other_session.get(BankAccount, acc.id)

            first_won = bank_sync_service.try_start_sync(db_session, acc)
            second_won = bank_sync_service.try_start_sync(other_session, other_account)

            assert first_won is True
            assert second_won is False
        finally:
            other_session.close()


class TestIsStale:
    def test_never_synced_is_stale(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        assert bank_sync_service.is_stale(acc) is True

    def test_recently_synced_is_not_stale(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.last_sync_at = datetime.now(timezone.utc)
        assert bank_sync_service.is_stale(acc) is False

    def test_error_status_is_stale_even_with_recent_last_sync_at(self, db_session, user):
        """Achado no code-review: `sync_account` grava `last_sync_at` antes
        de rodar a conciliação — uma falha depois disso deixa a conta em
        ERROR com `last_sync_at` fresco. Sem essa checagem, o sync
        automático (issue #114) ignoraria uma conta visivelmente quebrada
        pelos 45min inteiros do threshold."""
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.last_sync_at = datetime.now(timezone.utc)
        acc.sync_status = BankAccountSyncStatus.ERROR
        assert bank_sync_service.is_stale(acc) is True

    def test_old_sync_is_stale(self, db_session, user):
        from datetime import timedelta

        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.last_sync_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert bank_sync_service.is_stale(acc) is True

    def test_naive_datetime_is_treated_as_utc(self, db_session, user):
        """`last_sync_at` gravado sem tzinfo (SQLite não guarda timezone) não
        pode quebrar a comparação com um datetime aware."""
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
        assert bank_sync_service.is_stale(acc) is False


# ---------------------------------------------------------------------------
# sync-all endpoint (issue #114)
# ---------------------------------------------------------------------------


class TestSyncAllEndpoint:
    @patch("app.api.endpoints.bank_accounts.bank_sync_service.run_sync_job")
    def test_only_stale_accounts_are_triggered_by_default(self, mock_job, client, db_session, user):
        from datetime import timedelta

        fresh = _make_account(db_session, user, external_id=str(uuid4()))
        fresh.last_sync_at = datetime.now(timezone.utc)
        stale = _make_account(db_session, user, external_id=str(uuid4()))
        stale.last_sync_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.add_all([fresh, stale])
        db_session.commit()

        r = client.post("/bank-accounts/sync-all")
        assert r.status_code == 202
        assert r.json()["triggered"] == [str(stale.id)]

        db_session.refresh(fresh)
        db_session.refresh(stale)
        assert fresh.sync_status == BankAccountSyncStatus.IDLE
        assert stale.sync_status == BankAccountSyncStatus.SYNCING

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.run_sync_job")
    def test_one_account_failing_to_claim_lock_does_not_abort_the_whole_request(
        self, mock_job, client, db_session, user
    ):
        """Achado no code-review: sem isolamento por conta, uma falha
        transitória no `try_start_sync` de UMA conta (ex: erro de conexão)
        devolvia 500 pro request inteiro e nenhuma outra conta do usuário
        era disparada. Duas contas: a 1ª falha, a 2ª tem que continuar
        reivindicando o lock normalmente — e o savepoint garante que o claim
        dela não some junto com o rollback da falha da 1ª."""
        from datetime import timedelta

        real_try_start_sync = bank_sync_service.try_start_sync

        old = datetime.now(timezone.utc) - timedelta(hours=2)
        acc_ok = _make_account(db_session, user, external_id=str(uuid4()))
        acc_ok.last_sync_at = old
        acc_fail = _make_account(db_session, user, external_id=str(uuid4()))
        acc_fail.last_sync_at = old
        db_session.add_all([acc_ok, acc_fail])
        db_session.commit()

        def _fail_for_one_account(db, account, **kwargs):
            if account.id == acc_fail.id:
                raise Exception("erro transitório de conexão")
            return real_try_start_sync(db, account, **kwargs)

        with patch(
            "app.api.endpoints.bank_accounts.bank_sync_service.try_start_sync",
            side_effect=_fail_for_one_account,
        ):
            r = client.post("/bank-accounts/sync-all")

        assert r.status_code == 202
        assert r.json()["triggered"] == [str(acc_ok.id)]

        db_session.refresh(acc_ok)
        db_session.refresh(acc_fail)
        assert acc_ok.sync_status == BankAccountSyncStatus.SYNCING
        assert acc_fail.sync_status == BankAccountSyncStatus.IDLE

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.run_sync_job")
    def test_multiple_stale_accounts_all_triggered_without_extra_selects(
        self, mock_job, client, db_session, user
    ):
        """Achado no code-review: `try_start_sync` comitava a cada conta do
        loop, e a sessão padrão expira TODOS os objetos já carregados a cada
        commit (`expire_on_commit`) — a 2ª conta em diante forçava um SELECT
        implícito extra só pra reler atributos que não mudaram. Commit
        deferido pro final do loop (`commit=False`) elimina isso: só 1
        SELECT (a listagem inicial) pro loop inteiro, não importa quantas
        contas sejam disparadas."""
        from datetime import timedelta

        from sqlalchemy import event

        old = datetime.now(timezone.utc) - timedelta(hours=2)
        acc1 = _make_account(db_session, user, external_id=str(uuid4()))
        acc1.last_sync_at = old
        acc2 = _make_account(db_session, user, external_id=str(uuid4()))
        acc2.last_sync_at = old
        db_session.add_all([acc1, acc2])
        db_session.commit()

        selects = []
        engine = db_session.get_bind()

        def _capture(conn, cursor, statement, parameters, context, executemany):
            if statement.strip().upper().startswith("SELECT") and "bank_accounts" in statement:
                selects.append(statement)

        event.listen(engine, "before_cursor_execute", _capture)
        try:
            r = client.post("/bank-accounts/sync-all")
        finally:
            event.remove(engine, "before_cursor_execute", _capture)

        assert r.status_code == 202
        assert set(r.json()["triggered"]) == {str(acc1.id), str(acc2.id)}
        # 1 SELECT em bank_accounts (a listagem inicial) — sem `commit=False`,
        # cada conta commitada expiraria a outra e forçaria mais 1 SELECT por
        # conta seguinte só pra reler atributos que não mudaram.
        assert len(selects) == 1, f"esperava 1 SELECT em bank_accounts, vieram {len(selects)}"

    def test_sync_all_runs_multiple_accounts_concurrently(self, client, db_session, user):
        """Achado no code-review: agendar um `background_tasks.add_task` por
        conta parece paralelo, mas o Starlette roda `BackgroundTasks` em
        sequência — quem tem várias contas ficaria vendo "Atualizando…" pela
        SOMA da duração de cada sync. `run_sync_jobs_concurrently` despacha
        todas numa `asyncio.gather`, cada uma na sua thread de verdade."""
        import time
        from datetime import timedelta

        old = datetime.now(timezone.utc) - timedelta(hours=2)
        acc1 = _make_account(db_session, user, external_id=str(uuid4()))
        acc1.last_sync_at = old
        acc2 = _make_account(db_session, user, external_id=str(uuid4()))
        acc2.last_sync_at = old
        db_session.add_all([acc1, acc2])
        db_session.commit()

        def _slow_sync(account_id, user_id):
            time.sleep(0.2)

        with patch(
            "app.api.endpoints.bank_accounts.bank_sync_service.run_sync_job",
            side_effect=_slow_sync,
        ):
            start = time.monotonic()
            r = client.post("/bank-accounts/sync-all")
            elapsed = time.monotonic() - start

        assert r.status_code == 202
        assert len(r.json()["triggered"]) == 2
        # Sequencial seria ~0.4s (2 × 0.2s); em paralelo fica perto de 0.2s.
        assert elapsed < 0.35, f"esperava rodar em paralelo (~0.2s), levou {elapsed:.2f}s"

    def test_run_sync_jobs_concurrently_caps_max_simultaneous_syncs(self):
        """Achado no code-review: sem limite, um usuário com muitas contas
        conectadas saturaria sozinho o pool de conexões do processo inteiro
        (cada `run_sync_job` segura uma sessão pela duração toda do sync).
        12 contas, teto de 5 (`_MAX_CONCURRENT_SYNCS`) — o pico observado de
        syncs simultâneos nunca pode passar disso."""
        import asyncio
        import threading
        import time

        from app.services.bank_sync_service import run_sync_jobs_concurrently

        lock = threading.Lock()
        active = {"n": 0}
        peak = {"n": 0}

        def _tracked_sync(account_id, user_id):
            with lock:
                active["n"] += 1
                peak["n"] = max(peak["n"], active["n"])
            time.sleep(0.05)
            with lock:
                active["n"] -= 1

        pairs = [(uuid4(), uuid4()) for _ in range(12)]

        with patch("app.services.bank_sync_service.run_sync_job", side_effect=_tracked_sync):
            asyncio.run(run_sync_jobs_concurrently(pairs))

        assert peak["n"] <= 5
        assert peak["n"] > 1  # rodou de verdade em paralelo, não sequencial

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.run_sync_job")
    def test_force_triggers_even_fresh_accounts(self, mock_job, client, db_session, user):
        fresh = _make_account(db_session, user, external_id=str(uuid4()))
        fresh.last_sync_at = datetime.now(timezone.utc)
        db_session.add(fresh)
        db_session.commit()

        r = client.post("/bank-accounts/sync-all", params={"force": True})
        assert r.status_code == 202
        assert r.json()["triggered"] == [str(fresh.id)]

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.run_sync_job")
    def test_skips_account_without_external_id(self, mock_job, client, db_session, user):
        _make_account(db_session, user, external_id=None)
        r = client.post("/bank-accounts/sync-all", params={"force": True})
        assert r.status_code == 202
        assert r.json()["triggered"] == []
        mock_job.assert_not_called()

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.run_sync_job")
    def test_skips_account_already_syncing(self, mock_job, client, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.sync_status = BankAccountSyncStatus.SYNCING
        acc.sync_started_at = datetime.now(timezone.utc)
        db_session.add(acc)
        db_session.commit()

        r = client.post("/bank-accounts/sync-all", params={"force": True})
        assert r.status_code == 202
        assert r.json()["triggered"] == []
        mock_job.assert_not_called()

    def test_no_accounts_returns_empty_list(self, client):
        r = client.post("/bank-accounts/sync-all")
        assert r.status_code == 202
        assert r.json()["triggered"] == []


# ---------------------------------------------------------------------------
# sync endpoint
# ---------------------------------------------------------------------------


class TestRunSyncJobReturnValue:
    """`daily_sync.run` (issue #114) reusa `run_sync_job` em vez de
    reimplementar a transição SYNCING → IDLE/ERROR, e conta
    synced_accounts/errors a partir do que ele devolve."""

    @patch("app.services.bank_sync_service.sync_account")
    def test_returns_true_on_success(self, mock_sync, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        mock_sync.return_value = {}

        assert bank_sync_service.run_sync_job(acc.id, user.id) is True
        db_session.refresh(acc)
        assert acc.sync_status == BankAccountSyncStatus.IDLE

    @patch("app.services.bank_sync_service.sync_account", side_effect=Exception("boom"))
    def test_returns_false_on_failure(self, mock_sync, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))

        assert bank_sync_service.run_sync_job(acc.id, user.id) is False
        db_session.refresh(acc)
        assert acc.sync_status == BankAccountSyncStatus.ERROR

    def test_returns_false_for_nonexistent_account(self, db_session, user):
        assert bank_sync_service.run_sync_job(uuid4(), user.id) is False

    @patch(
        "app.services.bank_sync_service.get_account",
        side_effect=Exception("erro transitório de conexão"),
    )
    def test_never_raises_even_when_get_account_fails(self, mock_get, db_session, user):
        """Achado no code-review: `get_account` ficava FORA do try/except
        interno — uma falha bem aqui escapava da função inteira, quebrando a
        garantia (documentada no docstring) de que `run_sync_job` nunca deixa
        uma exceção vazar. `daily_sync.run`/`run_sync_jobs_concurrently`
        dependem disso pra isolar falha por conta."""
        assert bank_sync_service.run_sync_job(uuid4(), user.id) is False


class TestSyncEndpoint:
    @patch("app.api.endpoints.bank_accounts.bank_sync_service.sync_account")
    def test_sync_starts_background_job_and_returns_202(self, mock_sync, client, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        mock_sync.return_value = {
            "imported": 5,
            "skipped": 2,
            "bills_synced": 0,
            "auto_reconciled": 0,
            "suggestions": [],
        }
        # TestClient roda a BackgroundTask de forma síncrona antes de devolver a
        # resposta, então já dá pra conferir o estado final da conta aqui.
        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 202

        db_session.refresh(acc)
        assert acc.sync_status == BankAccountSyncStatus.IDLE
        assert acc.last_sync_error is None

    def test_sync_nonexistent_account_returns_404(self, client):
        r = client.post(f"/bank-accounts/{uuid4()}/sync")
        assert r.status_code == 404

    def test_sync_without_external_id_returns_400(self, client, db_session, user):
        acc = _make_account(db_session, user, external_id=None)
        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 400
        assert "item_id" in r.json()["detail"]

    def test_sync_already_syncing_is_idempotent(self, client, db_session, user):
        from datetime import datetime

        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.sync_status = BankAccountSyncStatus.SYNCING
        acc.sync_started_at = datetime.now(timezone.utc)
        db_session.add(acc)
        db_session.commit()

        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 202
        assert r.json()["sync_status"] == "SYNCING"

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.run_sync_job")
    def test_sync_breaks_stale_lock(self, mock_job, client, db_session, user):
        from datetime import datetime, timedelta

        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.sync_status = BankAccountSyncStatus.SYNCING
        acc.sync_started_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.add(acc)
        db_session.commit()

        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 202
        mock_job.assert_called_once()
        db_session.refresh(acc)
        assert acc.sync_status == BankAccountSyncStatus.SYNCING  # relançado

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.sync_account")
    def test_sync_job_error_sets_error_status(self, mock_sync, client, db_session, user):
        """`last_sync_error` é exposto na API — não pode vazar `str(exc)` cru
        (pode conter corpo de resposta da Pluggy ou outro detalhe interno).
        O detalhe completo vai só para o log/Sentry."""
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        mock_sync.side_effect = Exception("timeout da Pluggy, resposta: {api_key: 'segredo'}")

        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 202

        db_session.refresh(acc)
        assert acc.sync_status == BankAccountSyncStatus.ERROR
        assert acc.last_sync_error == "Falha ao sincronizar: Exception"


# ---------------------------------------------------------------------------
# bank_sync_service.sync_account — unit tests
# ---------------------------------------------------------------------------


class TestSyncAccountService:
    def _make_api_client_ctx(self):
        """Retorna um MagicMock que funciona como context manager."""
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    def test_sync_imports_new_transactions(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        tx1 = _pluggy_tx("tx-001", -150.0, "Supermercado", date(2026, 5, 1))
        tx2 = _pluggy_tx("tx-002", 3000.0, "Salário", date(2026, 5, 5))

        ctx = self._make_api_client_ctx()
        ctx.AccountApi = MagicMock()
        ctx.TransactionApi = MagicMock()

        with (
            patch("app.services.bank_sync_service.get_api_client", return_value=ctx),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw(
                [tx1, tx2]
            )

            result = bank_sync_service.sync_account(db_session, acc)

        assert result["imported"] == 2
        assert result["skipped"] == 0

        txs = db_session.query(Transaction).all()
        assert len(txs) == 2
        sources = {t.source for t in txs}
        assert "pluggy:tx-001" in sources
        assert "pluggy:tx-002" in sources

    def test_sync_skips_duplicate_transactions(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        existing = Transaction(
            user_id=user.id,
            date=date(2026, 5, 1),
            description="Duplicado",
            amount=Decimal("50.00"),
            type=TransactionType.EXPENSE,
            source="pluggy:tx-dup",
        )
        db_session.add(existing)
        db_session.commit()

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        tx_dup = _pluggy_tx("tx-dup", -50.0, "Duplicado", date(2026, 5, 1))
        tx_new = _pluggy_tx("tx-new", -30.0, "Farmácia", date(2026, 5, 2))

        with (
            patch(
                "app.services.bank_sync_service.get_api_client",
                return_value=self._make_api_client_ctx(),
            ),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw(
                [tx_dup, tx_new]
            )

            result = bank_sync_service.sync_account(db_session, acc)

        assert result["imported"] == 1
        assert result["skipped"] == 1

    def test_sync_classifies_income_and_expense(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        tx_expense = _pluggy_tx("tx-exp", -200.0, "Conta de água", date(2026, 5, 3))
        tx_income = _pluggy_tx("tx-inc", 5000.0, "Transferência recebida", date(2026, 5, 4))

        with (
            patch(
                "app.services.bank_sync_service.get_api_client",
                return_value=self._make_api_client_ctx(),
            ),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw(
                [tx_expense, tx_income]
            )

            bank_sync_service.sync_account(db_session, acc)

        txs = {t.source: t for t in db_session.query(Transaction).all()}
        assert txs["pluggy:tx-exp"].type == TransactionType.EXPENSE
        assert txs["pluggy:tx-inc"].type == TransactionType.INCOME
        assert txs["pluggy:tx-exp"].amount == Decimal("200.00")
        assert txs["pluggy:tx-inc"].amount == Decimal("5000.00")

    def test_sync_paginates_correctly(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        page1_txs = [
            _pluggy_tx(f"tx-p1-{i}", -10.0, f"Desc {i}", date(2026, 5, i + 1)) for i in range(3)
        ]
        page2_txs = [
            _pluggy_tx(f"tx-p2-{i}", -20.0, f"Desc2 {i}", date(2026, 5, i + 10)) for i in range(2)
        ]

        call_count = 0

        def fake_list(account_id, page, page_size):
            nonlocal call_count
            call_count += 1
            if page == 1:
                return _page_raw(page1_txs, total_pages=2)
            return _page_raw(page2_txs, total_pages=2)

        with (
            patch(
                "app.services.bank_sync_service.get_api_client",
                return_value=self._make_api_client_ctx(),
            ),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.side_effect = fake_list

            result = bank_sync_service.sync_account(db_session, acc)

        assert result["imported"] == 5
        assert call_count == 2

    def test_sync_updates_last_sync_at(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        assert acc.last_sync_at is None

        pluggy_acc = SimpleNamespace(id=str(uuid4()))

        with (
            patch(
                "app.services.bank_sync_service.get_api_client",
                return_value=self._make_api_client_ctx(),
            ),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw(
                []
            )

            bank_sync_service.sync_account(db_session, acc)

        db_session.refresh(acc)
        assert acc.last_sync_at is not None

    def test_sync_without_external_id_raises(self, db_session, user):
        acc = _make_account(db_session, user, external_id=None)
        with pytest.raises(ValueError, match="item_id"):
            bank_sync_service.sync_account(db_session, acc)

    def test_sync_truncates_long_description(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        long_desc = "X" * 300
        tx = _pluggy_tx("tx-long", -1.0, long_desc, date(2026, 5, 1))

        with (
            patch(
                "app.services.bank_sync_service.get_api_client",
                return_value=self._make_api_client_ctx(),
            ),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw(
                [tx]
            )

            bank_sync_service.sync_account(db_session, acc)

        saved = db_session.query(Transaction).first()
        assert len(saved.description) == 255

    def test_sync_categorizes_by_keyword_rule(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        cat = Category(user_id=user.id, name="Supermercado", color_hex="#00FF00")
        db_session.add(cat)
        db_session.commit()
        db_session.refresh(cat)
        create_rule(
            db_session, user.id, CategoryRuleCreate(keyword="pao de acucar", category_id=cat.id)
        )

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        tx = _pluggy_tx("tx-cat", -150.0, "Pao de Acucar Compra", date(2026, 5, 1))

        with (
            patch(
                "app.services.bank_sync_service.get_api_client",
                return_value=self._make_api_client_ctx(),
            ),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw(
                [tx]
            )

            bank_sync_service.sync_account(db_session, acc)

        saved = db_session.query(Transaction).filter_by(source="pluggy:tx-cat").one()
        assert str(saved.category_id) == str(cat.id)

    def test_sync_auto_reconciles_exact_match(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        payable = Payable(
            user_id=user.id,
            title="Internet",
            amount=Decimal("99.90"),
            due_date=date(2026, 5, 10),
            status=PayableStatus.PENDING,
        )
        db_session.add(payable)
        db_session.commit()
        db_session.refresh(payable)

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        tx = _pluggy_tx("tx-exact", -99.90, "Pagto Internet", date(2026, 5, 10))

        with (
            patch(
                "app.services.bank_sync_service.get_api_client",
                return_value=self._make_api_client_ctx(),
            ),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw(
                [tx]
            )

            result = bank_sync_service.sync_account(db_session, acc)

        # Match exato (confidence 1.0 e único) é auto-reconciliado — não sobra para revisão manual.
        assert result["auto_reconciled"] == 1
        assert result["suggestions"] == []

        db_session.refresh(payable)
        assert payable.status == PayableStatus.PAID

    def test_sync_keeps_ambiguous_suggestions_for_manual_review(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        payable = Payable(
            user_id=user.id,
            title="Internet",
            amount=Decimal("99.90"),
            due_date=date(2026, 5, 15),
            status=PayableStatus.PENDING,
        )
        db_session.add(payable)
        db_session.commit()
        db_session.refresh(payable)

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        tx = _pluggy_tx("tx-ambig", -99.90, "Pagto Internet", date(2026, 5, 10))

        with (
            patch(
                "app.services.bank_sync_service.get_api_client",
                return_value=self._make_api_client_ctx(),
            ),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(
                results=[pluggy_acc]
            )
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw(
                [tx]
            )

            result = bank_sync_service.sync_account(db_session, acc)

        # Valor exato mas data fora (0.8) — não é auto-confirmado, fica para revisão manual.
        assert len(result["suggestions"]) == 1
        assert result["suggestions"][0].confidence_score == 0.8

        db_session.refresh(payable)
        assert payable.status == PayableStatus.PENDING
