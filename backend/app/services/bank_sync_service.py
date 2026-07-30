from __future__ import annotations

import json
import sys
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import pluggy_sdk
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.bank_account import BankAccount, BankAccountSyncStatus
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.schemas.bank_account import BankAccountCreate, BankAccountUpdate
from app.services import bill_service
from app.services.category_rule_service import build_keyword_map
from app.services.category_seed import seed_default_categories
from app.services.pluggy_category_map import category_name_for, is_transfer
from app.services.pluggy_client import get_api_client
from app.services.reconciliation_service import (
    auto_reconcile_confident_matches,
    drop_resolved_payables,
    suggest_reconciliation,
)


def _log(message: str) -> None:
    print(f"[bank_sync] {message}", file=sys.stderr)


def list_accounts(db: Session, user_id: UUID) -> List[BankAccount]:
    return db.execute(
        select(BankAccount).where(BankAccount.user_id == user_id).order_by(BankAccount.name.asc())
    ).scalars().all()


def get_account(db: Session, user_id: UUID, account_id: UUID) -> Optional[BankAccount]:
    return db.execute(
        select(BankAccount).where(
            BankAccount.id == account_id, BankAccount.user_id == user_id
        )
    ).scalar_one_or_none()


def describe_item(item_id: UUID) -> tuple[str, str]:
    """Deriva `(name, bank_name)` legíveis para um item recém-conectado da Pluggy.

    No uso pessoal o único conector habilitado é o MeuPluggy, então
    `connector.name` é literalmente "MeuPluggy" em toda conexão — usá-lo como
    rótulo não diz nada. Os nomes úteis estão nas accounts do item (`name`;
    `marketingName` vem `None` no proxy do MeuPluggy).

    Um item do MeuPluggy agrega accounts de **instituições diferentes** (ex:
    corrente do Itaú + cartão Magalu + cartão Itaú), então o rótulo lista as
    accounts em vez de eleger uma: nomear a conexão inteira com o primeiro
    cartão da lista seria enganoso, e a ordem que a API devolve é arbitrária.
    """
    with get_api_client() as ac:
        pluggy_accounts = pluggy_sdk.AccountApi(ac).accounts_list(item_id=item_id).results or []

    # Contas BANK primeiro — a conta corrente é o rótulo menos surpreendente
    # para encabeçar a conexão.
    ordered = sorted(pluggy_accounts, key=lambda a: 0 if getattr(a, "type", None) == "BANK" else 1)

    labels: List[str] = []
    for pluggy_acct in ordered:
        label = (
            getattr(pluggy_acct, "marketing_name", None)
            or getattr(pluggy_acct, "name", None)
            or ""
        ).strip()
        if label and label not in labels:
            labels.append(label)

    if not labels:
        return "Conta bancária", "Desconhecido"

    name = ", ".join(labels)
    if len(name) > 100:
        name = f"{labels[0][:80]} (+{len(labels) - 1})"
    return name, labels[0][:100]


def create_account(db: Session, user_id: UUID, payload: BankAccountCreate) -> BankAccount:
    data = payload.model_dump()

    if (not data.get("name") or not data.get("bank_name")) and data.get("external_id"):
        try:
            derived_name, derived_bank = describe_item(UUID(data["external_id"]))
        except Exception as exc:  # noqa: BLE001
            # Nome ruim é bem melhor que falhar a conexão — o usuário pode
            # renomear depois via PATCH.
            _log(f"não foi possível derivar o nome do item {data['external_id']}: {type(exc).__name__}: {exc}")
            derived_name, derived_bank = "Conta bancária", "Desconhecido"
        data["name"] = data.get("name") or derived_name
        data["bank_name"] = data.get("bank_name") or derived_bank

    data["name"] = data.get("name") or "Conta bancária"
    data["bank_name"] = data.get("bank_name") or "Desconhecido"

    account = BankAccount(user_id=user_id, **data)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, account: BankAccount, payload: BankAccountUpdate) -> BankAccount:
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(account, field, value)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account: BankAccount) -> None:
    db.delete(account)
    db.commit()


def get_connect_token(item_id: Optional[UUID] = None) -> str:
    with get_api_client() as ac:
        auth_api = pluggy_sdk.AuthApi(ac)
        payload = pluggy_sdk.ConnectTokenRequest(itemId=item_id) if item_id else None
        resp = auth_api.connect_token_create(connect_token_request=payload)
    return resp.access_token


def _parse_pluggy_date(date_str: str) -> date_type:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()


def _transaction_type(tx: dict) -> TransactionType:
    """Deriva INCOME/EXPENSE do campo `type` da Pluggy, não do sinal do valor.

    O sinal **não** é consistente entre tipos de conta: em conta corrente a
    saída vem negativa, mas em cartão de crédito a **compra vem positiva**
    (verificado nos dados reais: `+15.99 type=DEBIT ANUIDADE`). Inferir pelo
    sinal marcava toda compra de cartão como receita — mais da metade das
    transações importadas ficou com o tipo invertido.

    `type` vem explícito da API: DEBIT = saiu dinheiro, CREDIT = entrou.
    """
    pluggy_type = (tx.get("type") or "").upper()
    if pluggy_type == "DEBIT":
        return TransactionType.EXPENSE
    if pluggy_type == "CREDIT":
        return TransactionType.INCOME
    # Sem `type` utilizável, cai no sinal — que é correto para conta corrente,
    # de onde vêm os extratos CSV e as contas sem esse campo.
    return TransactionType.INCOME if (tx.get("amount") or 0) > 0 else TransactionType.EXPENSE


def sync_account(db: Session, account: BankAccount) -> dict:
    if not account.external_id:
        raise ValueError("Conta sem item_id da Pluggy. Conecte o banco primeiro.")

    item_id = UUID(account.external_id)
    imported = 0
    skipped = 0
    bills_synced = 0
    new_transactions: List[Transaction] = []
    keyword_map = build_keyword_map(db, account.user_id)
    # Garante que as categorias que o mapa da Pluggy referencia existem — quem
    # se registrou antes de "Saúde"/"Compras"/"Taxas"/"Seguros" entrarem no
    # DEFAULT_CATEGORIES ainda não as tem.
    seed_default_categories(db, account.user_id)
    category_ids_by_name = {
        cat.name: cat.id
        for cat in db.execute(
            select(Category).where(Category.user_id == account.user_id)
        ).scalars().all()
    }

    with get_api_client() as ac:
        account_api = pluggy_sdk.AccountApi(ac)
        tx_api = pluggy_sdk.TransactionApi(ac)
        bill_api = pluggy_sdk.BillApi(ac)

        pluggy_accounts = account_api.accounts_list(item_id=item_id).results or []

        for pluggy_acct in pluggy_accounts:
            if getattr(pluggy_acct, "type", None) == "CREDIT":
                card_name = getattr(pluggy_acct, "marketing_name", None) or getattr(pluggy_acct, "name", None)
                try:
                    # Mesmo workaround do sync de transações: bypass da validação
                    # Pydantic do SDK usando o JSON bruto.
                    raw_bills = bill_api.bills_list_without_preload_content(
                        account_id=pluggy_acct.id
                    )
                    bills_data = json.loads(raw_bills.data).get("results") or []
                except Exception as exc:  # noqa: BLE001
                    # Bills só existem em conexões Open Finance Regulado — degrada
                    # para lista vazia quando a conexão não as suporta, mas loga:
                    # sem isso não há como distinguir "conector não expõe faturas"
                    # de um bug nosso, e a geração automática de Payable de fatura
                    # some sem aviso.
                    _log(
                        f"bills indisponíveis (account={pluggy_acct.id} card={card_name!r}): "
                        f"{type(exc).__name__}: {exc}"
                    )
                    bills_data = []

                for bill_data in bills_data:
                    bill_service.upsert_bill(
                        db, account.user_id, account, pluggy_acct.id, bill_data, card_name=card_name
                    )
                    bills_synced += 1

            page = 1
            while True:
                # Use without_preload_content + raw JSON to bypass Pluggy SDK Pydantic
                # validation errors caused by type mismatches in nested models
                # (e.g. CreditCardMetadata.payeeMCC returned as int, declared as StrictStr).
                raw_resp = tx_api.transactions_list_without_preload_content(
                    account_id=pluggy_acct.id,
                    page=page,
                    page_size=500,
                )
                page_data = json.loads(raw_resp.data)
                transactions = page_data.get("results") or []
                total_pages = page_data.get("totalPages") or 1

                if not transactions:
                    break

                for tx in transactions:
                    source_key = f"pluggy:{tx['id']}"
                    exists = db.execute(
                        select(Transaction).where(
                            Transaction.user_id == account.user_id,
                            Transaction.source == source_key,
                        )
                    ).scalar_one_or_none()

                    if exists:
                        skipped += 1
                        continue

                    amount_raw = tx.get("amount", 0) or 0
                    tx_type = _transaction_type(tx)
                    tx_date = _parse_pluggy_date(tx["date"]) if tx.get("date") else date_type.today()
                    description = (tx.get("description") or "")[:255]
                    normalized = description.upper()
                    pluggy_category = tx.get("category")

                    # Regra do usuário ganha da categoria da Pluggy: é override
                    # explícito dele sobre a classificação automática.
                    category_id = None
                    for keyword, mapped_id in keyword_map.items():
                        if keyword in normalized:
                            category_id = UUID(mapped_id)
                            break
                    if category_id is None:
                        mapped_name = category_name_for(pluggy_category)
                        if mapped_name:
                            category_id = category_ids_by_name.get(mapped_name)

                    new_tx = Transaction(
                        user_id=account.user_id,
                        date=tx_date,
                        description=description,
                        amount=Decimal(str(abs(amount_raw))),
                        type=tx_type,
                        source=source_key,
                        category_id=category_id,
                        is_transfer=is_transfer(pluggy_category),
                        external_category=(pluggy_category or None),
                    )
                    db.add(new_tx)
                    new_transactions.append(new_tx)
                    imported += 1

                if page >= total_pages:
                    break
                page += 1

    account.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    for tx in new_transactions:
        db.refresh(tx)

    suggestions = suggest_reconciliation(db, account.user_id, new_transactions)
    auto_confirmed = auto_reconcile_confident_matches(db, account.user_id, suggestions)
    remaining_suggestions = drop_resolved_payables(suggestions, auto_confirmed)

    return {
        "imported": imported,
        "skipped": skipped,
        "bills_synced": bills_synced,
        "auto_reconciled": len(auto_confirmed),
        "suggestions": remaining_suggestions,
    }


def start_sync(db: Session, account: BankAccount) -> None:
    """Marca a conta como 'sincronizando' — chamado na request antes de agendar o job em background."""
    account.sync_status = BankAccountSyncStatus.SYNCING
    account.last_sync_error = None
    db.add(account)
    db.commit()


def run_sync_job(account_id: UUID, user_id: UUID) -> None:
    """Job de background: roda fora do ciclo de vida da request, então abre sua própria sessão."""
    db = SessionLocal()
    try:
        account = get_account(db, user_id, account_id)
        if account is None:
            return
        try:
            sync_account(db, account)
            account.sync_status = BankAccountSyncStatus.IDLE
            account.last_sync_error = None
            db.add(account)
            db.commit()
        except Exception as exc:
            db.rollback()
            account = get_account(db, user_id, account_id)
            if account is not None:
                account.sync_status = BankAccountSyncStatus.ERROR
                account.last_sync_error = str(exc)
                db.add(account)
                db.commit()
    finally:
        db.close()
