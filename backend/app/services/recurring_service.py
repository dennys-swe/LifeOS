from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payable import Payable, PayableStatus
from app.models.recurring_payable import RecurringPayable
from app.schemas.recurring_payable import RecurringPayableCreate, RecurringPayableUpdate


def create_recurring(db: Session, payload: RecurringPayableCreate) -> RecurringPayable:
    rec = RecurringPayable(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def list_recurring(db: Session) -> List[RecurringPayable]:
    result = db.execute(select(RecurringPayable).order_by(RecurringPayable.title.asc()))
    return result.scalars().all()


def get_recurring(db: Session, recurring_id: UUID) -> Optional[RecurringPayable]:
    return db.get(RecurringPayable, recurring_id)


def update_recurring(
    db: Session, rec: RecurringPayable, payload: RecurringPayableUpdate
) -> RecurringPayable:
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(rec, key, value)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def delete_recurring(db: Session, rec: RecurringPayable) -> None:
    db.delete(rec)
    db.commit()


def generate_for_month(db: Session, month: int, year: int) -> List[Payable]:
    actives = db.execute(
        select(RecurringPayable).where(RecurringPayable.active == True)  # noqa: E712
    ).scalars().all()

    start_date = date(year, month, 1)
    end_day = monthrange(year, month)[1]
    end_date = date(year, month, end_day)

    created: List[Payable] = []

    for rec in actives:
        day = min(rec.day_of_month, end_day)
        due_date = date(year, month, day)

        already_exists = db.execute(
            select(Payable).where(
                Payable.recurring_payable_id == rec.id,
                Payable.due_date >= start_date,
                Payable.due_date <= end_date,
            )
        ).scalar_one_or_none()

        if already_exists:
            continue

        payable = Payable(
            title=rec.title,
            amount=rec.amount,
            due_date=due_date,
            status=PayableStatus.PENDING,
            category_id=rec.category_id,
            recurring_payable_id=rec.id,
        )
        db.add(payable)
        created.append(payable)

    if created:
        db.commit()
        for p in created:
            db.refresh(p)

    return created
