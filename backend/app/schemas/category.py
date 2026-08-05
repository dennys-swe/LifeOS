from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.category import CategoryKind


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color_hex: str = Field(min_length=4, max_length=7)
    kind: CategoryKind = CategoryKind.EXPENSE


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID