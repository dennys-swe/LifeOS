from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.category import Category
from app.models.transaction import TransactionType
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionResponse, TransactionUpdate
from app.services.transaction_service import (
    create_transaction,
    delete_transaction,
    get_transaction,
    get_transactions,
    update_transaction,
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


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction_fields(
    transaction_id: UUID,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    transaction = get_transaction(db, user.id, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Nada para atualizar.")

    # Sem isso daria para mover a transação para a categoria de outro usuário —
    # `category_id` é um UUID vindo do cliente, não uma escolha confiável.
    category_id = changes.get("category_id")
    if category_id is not None:
        owned = db.execute(
            select(Category).where(
                Category.id == category_id, Category.user_id == user.id
            )
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    return update_transaction(db, transaction, changes)


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
