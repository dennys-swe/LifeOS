from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.transaction import TransactionType
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.models.category import Category
from app.services.statement_parser import parse_csv
from app.services.transaction_service import (
    create_transaction,
    create_transactions,
    delete_transaction,
    get_transaction,
    get_transactions,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/upload", response_model=List[TransactionResponse], status_code=status.HTTP_201_CREATED)
async def upload_transactions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported in this endpoint.")

    content = await file.read()
    categories = db.execute(
        select(Category).where(Category.name.in_(["Mercado", "Transporte"]))
    ).scalars().all()
    keyword_map = {
        "SUPERMERCADO": None,
        "POSTO": None,
    }
    for category in categories:
        if category.name == "Mercado":
            keyword_map["SUPERMERCADO"] = str(category.id)
        if category.name == "Transporte":
            keyword_map["POSTO"] = str(category.id)
    keyword_map = {k: v for k, v in keyword_map.items() if v}
    try:
        payloads = parse_csv(content, source=file.filename, keyword_map=keyword_map)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return create_transactions(db, payloads)


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction_manual(payload: TransactionCreate, db: Session = Depends(get_db)):
    return create_transaction(db, payload)


@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    db: Session = Depends(get_db),
    type: Optional[TransactionType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
):
    return get_transactions(
        db=db,
        tx_type=type,
        start_date=start_date,
        end_date=end_date,
        month=month,
        year=year,
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_transaction(transaction_id: UUID, db: Session = Depends(get_db)):
    transaction = get_transaction(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    delete_transaction(db, transaction)
    return None
