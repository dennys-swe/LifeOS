from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.payable import Payable, PayableStatus
from app.models.recurring_payable import RecurringPayable
from app.schemas.recurring_payable import RecurringPayableCreate, RecurringPayableUpdate


def create_recurring(
    db: Session, user_id: UUID, payload: RecurringPayableCreate
) -> RecurringPayable:
    rec = RecurringPayable(user_id=user_id, **payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def list_recurring(db: Session, user_id: UUID) -> List[RecurringPayable]:
    result = db.execute(
        select(RecurringPayable)
        .where(RecurringPayable.user_id == user_id)
        .order_by(RecurringPayable.title.asc())
    )
    return result.scalars().all()


def get_recurring(db: Session, user_id: UUID, recurring_id: UUID) -> Optional[RecurringPayable]:
    return db.execute(
        select(RecurringPayable).where(
            RecurringPayable.id == recurring_id, RecurringPayable.user_id == user_id
        )
    ).scalar_one_or_none()


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


def generate_for_month(db: Session, user_id: UUID, month: int, year: int) -> List[Payable]:
    actives = db.execute(
        select(RecurringPayable).where(
            RecurringPayable.user_id == user_id,
            RecurringPayable.active == True,  # noqa: E712
        )
    ).scalars().all()

    start_date = date(year, month, 1)
    end_day = monthrange(year, month)[1]
    end_date = date(year, month, end_day)

    created: List[Payable] = []

    for rec in actives:
        gen_month = date(year, month, 1)
        if gen_month < date(rec.start_date.year, rec.start_date.month, 1):
            continue
        if rec.end_date and gen_month > date(rec.end_date.year, rec.end_date.month, 1):
            continue

        day = min(rec.day_of_month, end_day)
        due_date = date(year, month, day)

        already_exists = db.execute(
            select(Payable).where(
                Payable.user_id == user_id,
                Payable.recurring_payable_id == rec.id,
                Payable.due_date >= start_date,
                Payable.due_date <= end_date,
            )
        ).scalar_one_or_none()

        if already_exists:
            continue

        same_title = db.execute(
            select(Payable).where(
                Payable.user_id == user_id,
                func.lower(Payable.title) == rec.title.lower(),
                Payable.due_date >= start_date,
                Payable.due_date <= end_date,
            )
        ).scalar_one_or_none()

        if same_title:
            same_title.recurring_payable_id = rec.id
            db.add(same_title)
            continue

        payable = Payable(
            user_id=user_id,
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
