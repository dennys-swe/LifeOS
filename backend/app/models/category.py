from __future__ import annotations

from uuid import uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)

    transactions = relationship("Transaction", back_populates="category")
    payables = relationship("Payable", back_populates="category")