from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.transaction import TransactionType
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services.transaction_service import (
    create_transaction,
    delete_transaction,
    get_transaction,
    get_transactions,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction_manual(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return create_transaction(db, user.id, payload)


@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
    type: Optional[TransactionType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category_id: Optional[UUID] = None,
    uncategorized: bool = False,
    include_transfers: bool = True,
    limit: Optional[int] = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return get_transactions(
        db=db,
        user_id=user.id,
        tx_type=type,
        start_date=start_date,
        end_date=end_date,
        month=month,
        year=year,
        category_id=category_id,
        uncategorized=uncategorized,
        include_transfers=include_transfers,
        limit=limit,
        offset=offset,
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    transaction = get_transaction(db, user.id, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    delete_transaction(db, transaction)
    return None
