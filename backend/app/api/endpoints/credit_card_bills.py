import json
import logging
from datetime import date
from typing import List, Optional
from uuid import UUID

import pluggy_sdk
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.bank_account import BankAccount
from app.models.credit_card_bill import CreditCardBill, CreditCardBillStatus
from app.models.payable import Payable
from app.models.user import User
from app.schemas.credit_card_bill import CreditCardBillResponse, CreditCardBillUpdate
from app.services import bill_service
from app.services.open_bill_service import explain_open_bill_amount, next_due_date
from app.services.pluggy_client import get_api_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credit-card-bills", tags=["Credit Card Bills"])


def _raw_transactions(tx_api: pluggy_sdk.TransactionApi, account_id: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        raw = tx_api.transactions_list_without_preload_content(
            account_id=account_id, page=page, page_size=500
        )
        data = json.loads(raw.data)
        results = data.get("results") or []
        out.extend(results)
        if not results or page >= (data.get("totalPages") or 1):
            break
        page += 1
    return out


@router.get("/debug")
def debug_open_bills(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Diagnóstico temporário (issue #20): mostra a fatura em aberto calculada
    transação por transação, por cartão, e compara com o que está salvo.

    Marca também faturas OPEN cujo cartão sumiu do item da Pluggy (issue #25).
    """
    accounts = db.execute(
        select(BankAccount).where(
            BankAccount.user_id == user.id, BankAccount.external_id.is_not(None)
        )
    ).scalars().all()

    saldo = {
        b.pluggy_account_id: b
        for b in db.execute(
            select(CreditCardBill).where(
                CreditCardBill.user_id == user.id,
                CreditCardBill.status == CreditCardBillStatus.OPEN,
            )
        ).scalars().all()
    }

    out: list[dict] = []
    seen_pluggy_accounts: set[str] = set()

    with get_api_client() as ac:
        account_api = pluggy_sdk.AccountApi(ac)
        tx_api = pluggy_sdk.TransactionApi(ac)
        bill_api = pluggy_sdk.BillApi(ac)

        for account in accounts:
            try:
                pluggy_accounts = account_api.accounts_list(item_id=account.external_id).results or []
            except Exception as exc:  # noqa: BLE001
                out.append({"conexao": account.name, "erro": f"{type(exc).__name__}: {exc}"})
                continue

            for pa in pluggy_accounts:
                if getattr(pa, "type", None) != "CREDIT":
                    continue
                seen_pluggy_accounts.add(pa.id)
                card_name = getattr(pa, "marketing_name", None) or getattr(pa, "name", None)

                try:
                    raw_bills = json.loads(
                        bill_api.bills_list_without_preload_content(account_id=pa.id).data
                    ).get("results") or []
                except Exception:  # noqa: BLE001
                    raw_bills = []
                bills_by_due = sorted(
                    (b for b in raw_bills if b.get("dueDate")), key=lambda b: b["dueDate"]
                )
                hoje = date.today()
                ja_venceram = [
                    b for b in bills_by_due if date.fromisoformat(b["dueDate"][:10]) <= hoje
                ]
                # Escolha atual (bugada): a fatura de data mais alta — pega projeções futuras.
                atual = (
                    date.fromisoformat(bills_by_due[-1]["dueDate"][:10]) if bills_by_due else None
                )
                # Escolha correta: a última fatura já vencida.
                corrigida = (
                    date.fromisoformat(ja_venceram[-1]["dueDate"][:10]) if ja_venceram else None
                )
                last_closed_due = atual

                stored_bills = db.execute(
                    select(CreditCardBill).where(
                        CreditCardBill.user_id == user.id,
                        CreditCardBill.pluggy_account_id == pa.id,
                    ).order_by(CreditCardBill.due_date)
                ).scalars().all()

                entry: dict = {
                    "conexao": account.name,
                    "cartao": card_name,
                    "pluggy_account_id": pa.id,
                    "conta_pluggy": {
                        "status": getattr(pa, "status", None),
                        "subtype": getattr(pa, "subtype", None),
                        "number": getattr(pa, "number", None),
                        "name": getattr(pa, "name", None),
                    },
                    "faturas_pluggy": [
                        {
                            "dueDate": (b.get("dueDate") or "")[:10],
                            "totalAmount": b.get("totalAmount"),
                            "id": b.get("id"),
                        }
                        for b in bills_by_due
                    ],
                    "faturas_salvas": [
                        {
                            "due_date": b.due_date.isoformat(),
                            "total_amount": str(b.total_amount),
                            "status": b.status.value,
                            "external_id": b.external_id,
                        }
                        for b in stored_bills
                    ],
                    "ultima_fatura_fechada": last_closed_due.isoformat() if last_closed_due else None,
                    "ultima_fatura_ja_vencida": corrigida.isoformat() if corrigida else None,
                }

                if last_closed_due is None:
                    entry["nota"] = "sem fatura fechada — não dá para reconstruir o ciclo aberto"
                    out.append(entry)
                    continue

                transactions = _raw_transactions(tx_api, pa.id)
                target_due = next_due_date(last_closed_due, hoje)
                explained = explain_open_bill_amount(transactions, target_due, last_closed_due)

                # E se a "última fechada" fosse a última já vencida?
                simulado = None
                if corrigida and corrigida != last_closed_due:
                    alt_target = next_due_date(corrigida, hoje)
                    alt = explain_open_bill_amount(transactions, alt_target, corrigida)
                    simulado = {
                        "ultima_fatura_fechada": corrigida.isoformat(),
                        "vencimento_alvo": alt_target.isoformat(),
                        "total_calculado": str(alt["total"]),
                    }

                salvo = saldo.get(pa.id)
                payable = db.get(Payable, salvo.payable_id) if salvo and salvo.payable_id else None
                entry.update(
                    {
                        "vencimento_alvo": target_due.isoformat(),
                        "total_calculado": str(explained["total"]),
                        "total_salvo": str(salvo.total_amount) if salvo else None,
                        "payable": (
                            {"valor": str(payable.amount), "status": payable.status.value}
                            if payable
                            else None
                        ),
                        "simulado_com_ultima_vencida": simulado,
                        "linhas": explained["linhas"],
                    }
                )
                out.append(entry)

    fantasmas = [
        {
            "cartao": b.custom_card_name or b.card_name,
            "pluggy_account_id": pid,
            "total_salvo": str(b.total_amount),
            "payable_id": str(b.payable_id) if b.payable_id else None,
            "nota": "cartão não apareceu no item da Pluggy nesta consulta (issue #25)",
        }
        for pid, b in saldo.items()
        if pid not in seen_pluggy_accounts
    ]

    return {"cartoes": out, "faturas_fantasma": fantasmas}


@router.get("", response_model=List[CreditCardBillResponse])
def list_credit_card_bills(
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return bill_service.list_bills(db, user.id, month=month, year=year)


@router.patch("/{bill_id}", response_model=CreditCardBillResponse)
def update_credit_card_bill(
    bill_id: UUID,
    payload: CreditCardBillUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    # `exclude_unset`: alterar só a cor não pode apagar o apelido, e vice-versa.
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Nada para atualizar.")

    updated = bill_service.update_bill_customization(db, user.id, bill_id, changes)
    if updated is None:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    return updated

