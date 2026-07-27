from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.category import Category

DEFAULT_CATEGORIES = [
    {"name": "Moradia", "color_hex": "#38BDF8"},
    {"name": "Alimentação", "color_hex": "#22C55E"},
    {"name": "Transporte", "color_hex": "#F97316"},
    {"name": "Educação", "color_hex": "#6366F1"},
    {"name": "Lazer", "color_hex": "#EC4899"},
    {"name": "Mercado", "color_hex": "#84CC16"},
]


def seed_default_categories(db: Session, user_id: UUID) -> None:
    for data in DEFAULT_CATEGORIES:
        db.add(Category(user_id=user_id, **data))
    db.commit()
