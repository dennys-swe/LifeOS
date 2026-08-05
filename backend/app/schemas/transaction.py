from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.transaction import TransactionType


class TransactionBase(BaseModel):
    date: date
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0)
    type: TransactionType
    source: Optional[str] = Field(default=None, max_length=100)
    category_id: Optional[UUID] = None


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    """Edição pontual de uma transação importada.

    Só expõe o que o usuário corrige na tela — a categorização automática
    (regras + mapa da Pluggy) erra em lançamento novo, e `is_transfer` decide
    se o valor entra nos totais de gasto. Data, valor e descrição vêm do banco
    e não devem ser reescritos à mão.

    Todos os campos são opcionais e o PATCH usa `exclude_unset`: mandar só a
    categoria não pode alterar `is_transfer` sem querer.
    """

    category_id: Optional[UUID] = None
    is_transfer: Optional[bool] = None


class TransactionResponse(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # Expostos para o cliente conseguir reproduzir os totais do /summary, que
    # exclui transferência. Sem isso, somar as transações na tela dá um número
    # diferente do card ao lado.
    is_transfer: bool = False
    external_category: Optional[str] = None
