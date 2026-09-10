"""Popula o banco de DESENVOLVIMENTO com um dono e dados plausíveis.

    python -m scripts.seed_dev            # idempotente: não duplica
    python -m scripts.seed_dev --reset    # apaga os dados do dono e recria

Nunca roda contra produção: aborta se ENVIRONMENT=production (e o guard de
app/db/database.py já barra um DATABASE_URL de banco gerenciado).

Login gerado: dono@lifeos.local / devpassword
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal

from fastapi_users.password import PasswordHelper
from sqlalchemy import delete, select

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.bank_account import BankAccount
from app.models.category import Category
from app.models.credit_card_bill import CreditCardBill, CreditCardBillStatus
from app.models.payable import Payable, PayableStatus
from app.models.recurring_payable import RecurringPayable
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.category_seed import seed_default_categories

SEED_EMAIL = "dono@lifeos.local"
SEED_PASSWORD = "devpassword"


def _reset(db, user_id) -> None:
    for model in (CreditCardBill, BankAccount, Transaction, Payable, RecurringPayable):
        db.execute(delete(model).where(model.user_id == user_id))
    db.commit()


def _get_or_create_user(db) -> User:
    user = db.execute(select(User).where(User.email == SEED_EMAIL)).scalar_one_or_none()
    if user:
        return user
    user = User(
        email=SEED_EMAIL,
        full_name="Dono (dev)",
        hashed_password=PasswordHelper().hash(SEED_PASSWORD),
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _cat(db, user_id, name: str):
    return db.execute(
        select(Category).where(Category.user_id == user_id, Category.name == name)
    ).scalar_one_or_none()


def seed(reset: bool = False) -> None:
    if settings.environment == "production":
        sys.exit("seed_dev: recusado — ENVIRONMENT=production")

    db = SessionLocal()
    try:
        user = _get_or_create_user(db)
        seed_default_categories(db, user.id)

        already_seeded = db.execute(
            select(RecurringPayable.id).where(RecurringPayable.user_id == user.id).limit(1)
        ).scalar_one_or_none()
        if already_seeded and not reset:
            print(f"seed_dev: {SEED_EMAIL} já tem dados — use --reset para recriar")
            return
        if reset:
            _reset(db, user.id)

        today = date.today()
        moradia = _cat(db, user.id, "Moradia")
        alimentacao = _cat(db, user.id, "Alimentação")
        transporte = _cat(db, user.id, "Transporte")

        db.add_all(
            [
                RecurringPayable(
                    user_id=user.id, title="Aluguel", amount=Decimal("1800.00"),
                    day_of_month=5, active=True, start_date=date(today.year, 1, 1),
                    category_id=moradia.id if moradia else None,
                ),
                RecurringPayable(
                    user_id=user.id, title="Internet", amount=Decimal("120.00"),
                    day_of_month=12, active=True, start_date=date(today.year, 1, 1),
                ),
                RecurringPayable(
                    user_id=user.id, title="Academia", amount=Decimal("99.90"),
                    day_of_month=10, active=True, start_date=date(today.year, 1, 1),
                ),
            ]
        )

        db.add_all(
            [
                Payable(
                    user_id=user.id, title="Conta de luz", amount=Decimal("210.45"),
                    due_date=today + timedelta(days=4), status=PayableStatus.PENDING,
                    category_id=moradia.id if moradia else None,
                ),
                Payable(
                    user_id=user.id, title="Água", amount=Decimal("88.10"),
                    due_date=today + timedelta(days=9), status=PayableStatus.PENDING,
                ),
                Payable(
                    user_id=user.id, title="IPTU (parcela)", amount=Decimal("143.00"),
                    due_date=today - timedelta(days=3), status=PayableStatus.PENDING,
                ),
                Payable(
                    user_id=user.id, title="Plano de saúde", amount=Decimal("389.00"),
                    due_date=today - timedelta(days=10), status=PayableStatus.PAID,
                    payment_date=today - timedelta(days=10),
                ),
            ]
        )

        db.add_all(
            [
                Transaction(
                    user_id=user.id, date=today - timedelta(days=d), description=desc,
                    amount=Decimal(str(amount)), type=ttype,
                    is_transfer=is_transfer,
                    category_id=(cat.id if cat else None),
                )
                for d, desc, amount, ttype, is_transfer, cat in [
                    (1, "SUPERMERCADO BOM PRECO", "245.90", TransactionType.EXPENSE, False, alimentacao),
                    (2, "POSTO SHELL", "180.00", TransactionType.EXPENSE, False, transporte),
                    (3, "IFOOD *RESTAURANTE", "54.30", TransactionType.EXPENSE, False, alimentacao),
                    (4, "UBER *TRIP", "23.80", TransactionType.EXPENSE, False, transporte),
                    (5, "SALARIO EMPRESA X", "6500.00", TransactionType.INCOME, False, None),
                    (6, "PIX RECEBIDO CLIENTE", "1200.00", TransactionType.INCOME, False, None),
                    (7, "PAGAMENTO FATURA CARTAO", "1340.00", TransactionType.EXPENSE, True, None),
                    (8, "TRANSFERENCIA POUPANCA", "800.00", TransactionType.EXPENSE, True, None),
                ]
            ]
        )

        account = BankAccount(
            user_id=user.id, name="Conta corrente (dev)", bank_name="Banco Dev",
            account_type="checking", external_id="dev-item-0001",
        )
        db.add(account)
        db.flush()

        db.add_all(
            [
                CreditCardBill(
                    user_id=user.id, bank_account_id=account.id,
                    pluggy_account_id="dev-card-0001", external_id="dev-bill-closed",
                    card_name="Cartão Dev", due_date=today - timedelta(days=2),
                    total_amount=Decimal("1340.00"), status=CreditCardBillStatus.CLOSED,
                ),
                CreditCardBill(
                    user_id=user.id, bank_account_id=account.id,
                    pluggy_account_id="dev-card-0001", external_id="dev-bill-open",
                    card_name="Cartão Dev", due_date=today + timedelta(days=26),
                    total_amount=Decimal("612.55"), status=CreditCardBillStatus.OPEN,
                ),
            ]
        )

        db.commit()
        print(f"seed_dev: pronto. login {SEED_EMAIL} / {SEED_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="apaga os dados do dono e recria")
    seed(reset=parser.parse_args().reset)
