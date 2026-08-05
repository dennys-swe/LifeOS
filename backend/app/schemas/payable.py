from __future__ import annotations

from datetime import date
from enum import Enum
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payable import PayableStatus


class PayableBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0)
    due_date: date
    status: PayableStatus = PayableStatus.PENDING
    payment_date: Optional[date] = None
    category_id: Optional[UUID] = None


class PayableCreate(PayableBase):
    pass


class PayableUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    due_date: Optional[date] = None
    status: Optional[PayableStatus] = None
    payment_date: Optional[date] = None
    category_id: Optional[UUID] = None


class PayableOrigin(str, Enum):
    """De onde veio a conta — a tela precisa distinguir o que é do usuário.

    Editar ou excluir uma conta gerada de fatura não adianta: o próximo sync
    recria/sobrescreve. Sem esse campo, a tela mostrava os mesmos botões para
    tudo e não havia como saber o que era seguro mexer.
    """

    MANUAL = "MANUAL"
    BILL = "BILL"
    RECURRING = "RECURRING"


class PayableResponse(PayableBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recurring_payable_id: Optional[UUID] = None
    transaction_id: Optional[UUID] = None
    origin: PayableOrigin = PayableOrigin.MANUAL
    # Fatura do ciclo ainda em aberto: o valor muda a cada compra até o banco
    # fechar. A tela avisa para o número não ser lido como definitivo.
    is_estimated: bool = False
