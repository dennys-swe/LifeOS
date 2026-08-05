from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.credit_card_bill import CreditCardBill, CreditCardBillStatus
from app.models.payable import Payable, PayableStatus
from app.schemas.payable import PayableOrigin, PayableCreate, PayableUpdate


def create_payable(db: Session, user_id: UUID, payload: PayableCreate) -> Payable:
    payable = Payable(user_id=user_id, **payload.model_dump())
    db.add(payable)
    db.commit()
    db.refresh(payable)
    return payable


def list_payables(
    db: Session, user_id: UUID, month: Optional[int] = None, year: Optional[int] = None
) -> Iterable[Payable]:
    query = select(Payable).where(Payable.user_id == user_id)

    if month is not None and year is not None:
        start_date = date(year, month, 1)
        end_day = monthrange(year, month)[1]
        end_date = date(year, month, end_day)
        query = query.where(Payable.due_date >= start_date).where(
            Payable.due_date <= end_date
        )

    result = db.execute(query.order_by(Payable.due_date.asc()))
    return annotate_origin(db, result.scalars().all())


def annotate_origin(db: Session, payables: Iterable[Payable]) -> list[Payable]:
    """Marca cada payable com `origin`/`is_estimated` para a resposta da API.

    São atributos calculados, não colunas: a origem já está implícita no
    `recurring_payable_id` e no `CreditCardBill.payable_id` que aponta de
    volta. Resolver as faturas em **uma** consulta evita um N+1 na listagem.
    """
    payables = list(payables)
    if not payables:
        return payables

    bills = db.execute(
        select(CreditCardBill.payable_id, CreditCardBill.status).where(
            CreditCardBill.payable_id.in_([p.id for p in payables])
        )
    ).all()
    bill_status = {payable_id: status for payable_id, status in bills}

    for payable in payables:
        status = bill_status.get(payable.id)
        if status is not None:
            payable.origin = PayableOrigin.BILL
            payable.is_estimated = status == CreditCardBillStatus.OPEN
        elif payable.recurring_payable_id is not None:
            payable.origin = PayableOrigin.RECURRING
            payable.is_estimated = False
        else:
            payable.origin = PayableOrigin.MANUAL
            payable.is_estimated = False
    return payables


def get_payable(db: Session, user_id: UUID, payable_id: UUID) -> Optional[Payable]:
    return db.execute(
        select(Payable).where(Payable.id == payable_id, Payable.user_id == user_id)
    ).scalar_one_or_none()


def update_payable(db: Session, payable: Payable, payload: PayableUpdate) -> Payable:
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(payable, key, value)
    db.add(payable)
    db.commit()
    db.refresh(payable)
    return payable


def delete_payable(db: Session, payable: Payable) -> None:
    db.delete(payable)
    db.commit()


def is_due_today(payable: Payable, today: Optional[date] = None) -> bool:
    today = today or date.today()
    return payable.due_date == today


def is_overdue(payable: Payable, today: Optional[date] = None) -> bool:
    today = today or date.today()
    return payable.status == PayableStatus.PENDING and payable.due_date < today
