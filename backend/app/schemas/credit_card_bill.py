from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.credit_card_bill import CreditCardBillStatus


class CreditCardBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bank_account_id: UUID
    # Identifica o cartão: apelido e cor valem para todas as faturas que o
    # compartilham, então a UI precisa dele para refletir a mudança na hora.
    pluggy_account_id: str
    card_name: Optional[str] = None
    custom_card_name: Optional[str] = None
    custom_color_hex: Optional[str] = None
    due_date: date
    total_amount: Decimal
    minimum_payment_amount: Optional[Decimal]
    allows_installments: Optional[bool]
    payable_id: Optional[UUID]
    status: CreditCardBillStatus


class CreditCardBillUpdate(BaseModel):
    custom_card_name: Optional[str] = None
    # `#RRGGBB`. Passar `null` explicitamente volta para a cor padrão; omitir o
    # campo não mexe nele (o PATCH usa `exclude_unset`), senão editar a cor
    # apagaria o apelido e vice-versa.
    custom_color_hex: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

