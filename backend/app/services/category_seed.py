from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category

DEFAULT_CATEGORIES = [
    {"name": "Moradia", "color_hex": "#38BDF8"},
    {"name": "Alimentação", "color_hex": "#22C55E"},
    {"name": "Transporte", "color_hex": "#F97316"},
    {"name": "Educação", "color_hex": "#6366F1"},
    {"name": "Lazer", "color_hex": "#EC4899"},
    {"name": "Mercado", "color_hex": "#84CC16"},
    # As 4 abaixo cobrem categorias que a Pluggy classifica e que não tinham
    # destino — sem elas, farmácia/academia/compras/tarifas/seguro ficavam sem
    # categoria mesmo vindo classificadas da API. Ver `pluggy_category_map`.
    {"name": "Saúde", "color_hex": "#14B8A6"},
    {"name": "Compras", "color_hex": "#A855F7"},
    {"name": "Taxas", "color_hex": "#EF4444"},
    {"name": "Seguros", "color_hex": "#0EA5E9"},
    # PIX/TED/boleto para terceiros: é gasto (o dinheiro saiu de vez), mas não
    # tem natureza de consumo. Sem essa categoria eram ~21% das transações
    # entrando no total de despesa sem aparecer no "gastos por categoria".
    {"name": "Transferências", "color_hex": "#64748B"},
]


def seed_default_categories(db: Session, user_id: UUID) -> None:
    """Cria as categorias padrão que ainda não existem para o usuário.

    Idempotente de propósito: além do registro de novo usuário, é chamada para
    completar as categorias de quem se registrou antes de uma nova entrada ser
    adicionada em `DEFAULT_CATEGORIES` (`UniqueConstraint(user_id, name)`).
    """
    existing = {
        name
        for (name,) in db.execute(
            select(Category.name).where(Category.user_id == user_id)
        ).all()
    }
    for data in DEFAULT_CATEGORIES:
        if data["name"] not in existing:
            db.add(Category(user_id=user_id, **data))
    db.commit()
