from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.credit_card_bill import CreditCardBillResponse
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
