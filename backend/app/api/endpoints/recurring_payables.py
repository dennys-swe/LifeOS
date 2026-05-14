from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.payable import PayableResponse
from app.schemas.recurring_payable import (
    RecurringPayableCreate,
    RecurringPayableResponse,
    RecurringPayableUpdate,
)
from app.services import recurring_service

router = APIRouter(prefix="/recurring-payables", tags=["Recurring Payables"])


@router.get("", response_model=List[RecurringPayableResponse])
def list_recurring_payables(db: Session = Depends(get_db)):
    return recurring_service.list_recurring(db)


# /generate must be registered before /{recurring_id} to avoid FastAPI treating "generate" as UUID
@router.post("/generate", response_model=List[PayableResponse], status_code=status.HTTP_201_CREATED)
def generate_payables_for_month(
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    return recurring_service.generate_for_month(db, month=month, year=year)


@router.post("", response_model=RecurringPayableResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_payable(
    payload: RecurringPayableCreate, db: Session = Depends(get_db)
):
    return recurring_service.create_recurring(db, payload)


@router.get("/{recurring_id}", response_model=RecurringPayableResponse)
def get_recurring_payable(recurring_id: UUID, db: Session = Depends(get_db)):
    rec = recurring_service.get_recurring(db, recurring_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recurring payable not found")
    return rec


@router.put("/{recurring_id}", response_model=RecurringPayableResponse)
def update_recurring_payable(
    recurring_id: UUID,
    payload: RecurringPayableUpdate,
    db: Session = Depends(get_db),
):
    rec = recurring_service.get_recurring(db, recurring_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recurring payable not found")
    return recurring_service.update_recurring(db, rec, payload)


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_payable(recurring_id: UUID, db: Session = Depends(get_db)):
    rec = recurring_service.get_recurring(db, recurring_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recurring payable not found")
    recurring_service.delete_recurring(db, rec)
    return None
