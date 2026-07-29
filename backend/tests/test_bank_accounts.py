"""Testes manuais da integração Pluggy — endpoints e serviço de bank accounts."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import json

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
        accounts = [self._pluggy_acct(f"Cartão de crédito muito longo numero {i}") for i in range(6)]

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
        mock_token.side_effect = RuntimeError("PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET não configurados")
        r = client.post("/bank-accounts/connect-token")
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# sync endpoint
# ---------------------------------------------------------------------------

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
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        acc.sync_status = BankAccountSyncStatus.SYNCING
        db_session.add(acc)
        db_session.commit()

        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 202
        assert r.json()["sync_status"] == "SYNCING"

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.sync_account")
    def test_sync_job_error_sets_error_status(self, mock_sync, client, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        mock_sync.side_effect = Exception("timeout da Pluggy")

        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 202

        db_session.refresh(acc)
        assert acc.sync_status == BankAccountSyncStatus.ERROR
        assert "timeout da Pluggy" in acc.last_sync_error


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
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw([tx1, tx2])

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
            patch("app.services.bank_sync_service.get_api_client", return_value=self._make_api_client_ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw([tx_dup, tx_new])

            result = bank_sync_service.sync_account(db_session, acc)

        assert result["imported"] == 1
        assert result["skipped"] == 1

    def test_sync_classifies_income_and_expense(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        tx_expense = _pluggy_tx("tx-exp", -200.0, "Conta de água", date(2026, 5, 3))
        tx_income = _pluggy_tx("tx-inc", 5000.0, "Transferência recebida", date(2026, 5, 4))

        with (
            patch("app.services.bank_sync_service.get_api_client", return_value=self._make_api_client_ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw([tx_expense, tx_income])

            bank_sync_service.sync_account(db_session, acc)

        txs = {t.source: t for t in db_session.query(Transaction).all()}
        assert txs["pluggy:tx-exp"].type == TransactionType.EXPENSE
        assert txs["pluggy:tx-inc"].type == TransactionType.INCOME
        assert txs["pluggy:tx-exp"].amount == Decimal("200.00")
        assert txs["pluggy:tx-inc"].amount == Decimal("5000.00")

    def test_sync_paginates_correctly(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        page1_txs = [_pluggy_tx(f"tx-p1-{i}", -10.0, f"Desc {i}", date(2026, 5, i + 1)) for i in range(3)]
        page2_txs = [_pluggy_tx(f"tx-p2-{i}", -20.0, f"Desc2 {i}", date(2026, 5, i + 10)) for i in range(2)]

        call_count = 0

        def fake_list(account_id, page, page_size):
            nonlocal call_count
            call_count += 1
            if page == 1:
                return _page_raw(page1_txs, total_pages=2)
            return _page_raw(page2_txs, total_pages=2)

        with (
            patch("app.services.bank_sync_service.get_api_client", return_value=self._make_api_client_ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.side_effect = fake_list

            result = bank_sync_service.sync_account(db_session, acc)

        assert result["imported"] == 5
        assert call_count == 2

    def test_sync_updates_last_sync_at(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        assert acc.last_sync_at is None

        pluggy_acc = SimpleNamespace(id=str(uuid4()))

        with (
            patch("app.services.bank_sync_service.get_api_client", return_value=self._make_api_client_ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw([])

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
            patch("app.services.bank_sync_service.get_api_client", return_value=self._make_api_client_ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw([tx])

            bank_sync_service.sync_account(db_session, acc)

        saved = db_session.query(Transaction).first()
        assert len(saved.description) == 255

    def test_sync_categorizes_by_keyword_rule(self, db_session, user):
        acc = _make_account(db_session, user, external_id=str(uuid4()))
        cat = Category(user_id=user.id, name="Supermercado", color_hex="#00FF00")
        db_session.add(cat)
        db_session.commit()
        db_session.refresh(cat)
        create_rule(db_session, user.id, CategoryRuleCreate(keyword="pao de acucar", category_id=cat.id))

        pluggy_acc = SimpleNamespace(id=str(uuid4()))
        tx = _pluggy_tx("tx-cat", -150.0, "Pao de Acucar Compra", date(2026, 5, 1))

        with (
            patch("app.services.bank_sync_service.get_api_client", return_value=self._make_api_client_ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw([tx])

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
            patch("app.services.bank_sync_service.get_api_client", return_value=self._make_api_client_ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw([tx])

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
            patch("app.services.bank_sync_service.get_api_client", return_value=self._make_api_client_ctx()),
            patch("app.services.bank_sync_service.pluggy_sdk") as mock_sdk,
        ):
            mock_sdk.AccountApi.return_value.accounts_list.return_value = SimpleNamespace(results=[pluggy_acc])
            mock_sdk.TransactionApi.return_value.transactions_list_without_preload_content.return_value = _page_raw([tx])

            result = bank_sync_service.sync_account(db_session, acc)

        # Valor exato mas data fora (0.8) — não é auto-confirmado, fica para revisão manual.
        assert len(result["suggestions"]) == 1
        assert result["suggestions"][0].confidence_score == 0.8

        db_session.refresh(payable)
        assert payable.status == PayableStatus.PENDING
