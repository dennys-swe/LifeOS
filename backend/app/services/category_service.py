from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.schemas.category import CategoryCreate


def list_categories(db: Session, user_id: UUID) -> List[Category]:
    result = db.execute(
        select(Category).where(Category.user_id == user_id).order_by(Category.name.asc())
    )
    return result.scalars().all()


def get_category_by_name(db: Session, user_id: UUID, name: str) -> Category | None:
    return db.execute(
        select(Category).where(Category.user_id == user_id, Category.name == name)
    ).scalar_one_or_none()


def create_category(db: Session, user_id: UUID, payload: CategoryCreate) -> Category:
    category = Category(user_id=user_id, **payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
