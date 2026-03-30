from __future__ import annotations

from typing import List
from uuid import UUID

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.payable import PayableStatus
from app.schemas.payable import PayableCreate, PayableResponse, PayableUpdate
from app.services import payable_service

router = APIRouter(prefix="/payables", tags=["Payables"])


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


@router.delete("/{payable_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payable(payable_id: UUID, db: Session = Depends(get_db)):
    payable = payable_service.get_payable(db, payable_id)
    if payable is None:
        raise HTTPException(status_code=404, detail="Payable not found")
    payable_service.delete_payable(db, payable)
    return None
