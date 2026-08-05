from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryRuleCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=100)
    category_id: UUID
    priority: int = 0


class CategoryRuleResponse(CategoryRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # Quantos lançamentos já existentes a regra reclassificou ao ser criada.
    # Sem devolver isso, a tela não teria como dizer que a regra fez efeito —
    # o usuário salvaria a regra e o extrato pareceria intacto.
    applied_count: int = 0
