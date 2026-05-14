from __future__ import annotations

from datetime import date, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.payable import Payable, PayableStatus
from app.schemas.payable import PayableCreate, PayableResponse, PayableUpdate
from app.services import payable_service
from app.services.reconciliation_service import confirm_reconciliation

router = APIRouter(prefix="/payables", tags=["Payables"])


# Must be registered before /{payable_id} to avoid "upcoming" being parsed as UUID
@router.get("/upcoming", response_model=List[PayableResponse])
def upcoming_payables(
    days: int = Query(default=7, ge=1, le=60),
    db: Session = Depends(get_db),
):
    today = date.today()
    until = today + timedelta(days=days)
    result = db.execute(
        select(Payable).where(
            Payable.status == PayableStatus.PENDING,
            Payable.due_date >= today,
            Payable.due_date <= until,
        ).order_by(Payable.due_date.asc())
    )
    return result.scalars().all()


@router.post("", response_model=PayableResponse, status_code=status.HTTP_201_CREATED)
def create_payable(payload: PayableCreate, db: Session = Depends(get_db)):
    return payable_service.create_payable(db, payload)


@router.get("", response_model=List[PayableResponse])
def list_payables(
    month: int | None = None,
    year: int | None = None,
    db: Session = Depends(get_db),
):
    return payable_service.list_payables(db, month=month, year=year)


@router.put("/{payable_id}", response_model=PayableResponse)
def update_payable(payable_id: UUID, payload: PayableUpdate, db: Session = Depends(get_db)):
    payable = payable_service.get_payable(db, payable_id)
    if payable is None:
        raise HTTPException(status_code=404, detail="Payable not found")
    return payable_service.update_payable(db, payable, payload)


@router.patch("/{payable_id}/pay", response_model=PayableResponse)
def pay_payable(payable_id: UUID, db: Session = Depends(get_db)):
    payable = payable_service.get_payable(db, payable_id)
    if payable is None:
        raise HTTPException(status_code=404, detail="Payable not found")

    payload = PayableUpdate(status=PayableStatus.PAID, payment_date=date.today())
    return payable_service.update_payable(db, payable, payload)


@router.patch("/{payable_id}/reconcile", response_model=PayableResponse)
def reconcile_payable(
    payable_id: UUID,
    transaction_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return confirm_reconciliation(db, transaction_id=transaction_id, payable_id=payable_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{payable_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payable(payable_id: UUID, db: Session = Depends(get_db)):
    payable = payable_service.get_payable(db, payable_id)
    if payable is None:
        raise HTTPException(status_code=404, detail="Payable not found")
    payable_service.delete_payable(db, payable)
    return None
