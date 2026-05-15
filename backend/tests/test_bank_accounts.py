"""Testes manuais da integração Pluggy — endpoints e serviço de bank accounts."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import json

import pytest

from app.models.bank_account import BankAccount
from app.models.transaction import Transaction, TransactionType
from app.services import bank_sync_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_account(db, *, external_id: str | None = None) -> BankAccount:
    acc = BankAccount(
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
    def test_sync_returns_imported_skipped(self, mock_sync, client, db_session):
        acc = _make_account(db_session, external_id=str(uuid4()))
        mock_sync.return_value = {"imported": 5, "skipped": 2}
        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 200
        assert r.json() == {"imported": 5, "skipped": 2}

    def test_sync_nonexistent_account_returns_404(self, client):
        r = client.post(f"/bank-accounts/{uuid4()}/sync")
        assert r.status_code == 404

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.sync_account")
    def test_sync_without_external_id_returns_400(self, mock_sync, client, db_session):
        acc = _make_account(db_session, external_id=None)
        mock_sync.side_effect = ValueError("Conta sem item_id da Pluggy. Conecte o banco primeiro.")
        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 400
        assert "item_id" in r.json()["detail"]

    @patch("app.api.endpoints.bank_accounts.bank_sync_service.sync_account")
    def test_sync_pluggy_error_returns_502(self, mock_sync, client, db_session):
        acc = _make_account(db_session, external_id=str(uuid4()))
        mock_sync.side_effect = Exception("timeout da Pluggy")
        r = client.post(f"/bank-accounts/{acc.id}/sync")
        assert r.status_code == 502
        assert "Pluggy" in r.json()["detail"]


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

    def test_sync_imports_new_transactions(self, db_session):
        acc = _make_account(db_session, external_id=str(uuid4()))

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

    def test_sync_skips_duplicate_transactions(self, db_session):
        acc = _make_account(db_session, external_id=str(uuid4()))
        existing = Transaction(
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

    def test_sync_classifies_income_and_expense(self, db_session):
        acc = _make_account(db_session, external_id=str(uuid4()))

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

    def test_sync_paginates_correctly(self, db_session):
        acc = _make_account(db_session, external_id=str(uuid4()))

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

    def test_sync_updates_last_sync_at(self, db_session):
        acc = _make_account(db_session, external_id=str(uuid4()))
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

    def test_sync_without_external_id_raises(self, db_session):
        acc = _make_account(db_session, external_id=None)
        with pytest.raises(ValueError, match="item_id"):
            bank_sync_service.sync_account(db_session, acc)

    def test_sync_truncates_long_description(self, db_session):
        acc = _make_account(db_session, external_id=str(uuid4()))

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
