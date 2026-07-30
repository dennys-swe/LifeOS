from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.credit_card_bill import CreditCardBillResponse, CreditCardBillUpdate
from app.services import bill_service


router = APIRouter(prefix="/credit-card-bills", tags=["Credit Card Bills"])


@router.get("", response_model=List[CreditCardBillResponse])
def list_credit_card_bills(
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return bill_service.list_bills(db, user.id, month=month, year=year)


@router.patch("/{bill_id}", response_model=CreditCardBillResponse)
def update_credit_card_bill_alias(
    bill_id: UUID,
    payload: CreditCardBillUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    updated = bill_service.update_bill_alias(db, user.id, bill_id, payload.custom_card_name)
    if updated is None:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    return updated

