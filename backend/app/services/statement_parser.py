from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Iterable, List

import pandas as pd

from app.models.transaction import TransactionType
from app.schemas.transaction import TransactionCreate


_DATE_COLUMNS = {"data", "date"}
_DESC_COLUMNS = {"descricao", "descri??o", "description", "historico", "hist?rico"}
_VALUE_COLUMNS = {"valor", "value", "amount"}


def _normalize_column(name: str) -> str:
    return name.strip().lower()


def _pick_column(columns: Iterable[str], candidates: set[str]) -> str:
    for col in columns:
        if _normalize_column(col) in candidates:
            return col
    raise ValueError("Colunas obrigat?rias n?o encontradas (Data, Descri??o, Valor).")


def parse_csv(
    content: bytes,
    source: str | None = None,
    keyword_map: dict[str, str] | None = None,
) -> List[TransactionCreate]:
    df = pd.read_csv(BytesIO(content))

    date_col = _pick_column(df.columns, _DATE_COLUMNS)
    desc_col = _pick_column(df.columns, _DESC_COLUMNS)
    value_col = _pick_column(df.columns, _VALUE_COLUMNS)

    parsed: List[TransactionCreate] = []

    keyword_map = keyword_map or {}

    for _, row in df.iterrows():
        raw_date = pd.to_datetime(row[date_col], errors="coerce", dayfirst=True)
        if pd.isna(raw_date):
            continue

        raw_amount = row[value_col]
        if pd.isna(raw_amount):
            continue

        amount = Decimal(str(raw_amount))
        tx_type = TransactionType.INCOME if amount >= 0 else TransactionType.EXPENSE
        amount = abs(amount)

        description = str(row[desc_col]).strip()
        normalized = description.upper()
        category_id = None
        for keyword, mapped_id in keyword_map.items():
            if keyword in normalized:
                category_id = mapped_id
                break

        parsed.append(
            TransactionCreate(
                date=raw_date.date(),
                description=description,
                amount=amount,
                type=tx_type,
                source=source,
                category_id=category_id,
            )
        )

    return parsed
