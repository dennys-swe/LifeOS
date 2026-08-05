from datetime import date
from decimal import Decimal

from app.models.category import Category
from app.models.transaction import Transaction, TransactionType


def _category(db_session, user, name="Mercado"):
    cat = Category(user_id=user.id, name=name, color_hex="#059669")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


def _transaction(db_session, user, **kwargs):
    tx = Transaction(
        user_id=user.id,
        date=date(2026, 8, 1),
        description="MERCADINHO SAO LUIZ",
        amount=Decimal("87.48"),
        type=TransactionType.EXPENSE,
        **kwargs,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


def test_change_category(client, db_session, user):
    cat = _category(db_session, user)
    tx = _transaction(db_session, user)

    response = client.patch(f"/transactions/{tx.id}", json={"category_id": str(cat.id)})

    assert response.status_code == 200
    assert response.json()["category_id"] == str(cat.id)
    db_session.refresh(tx)
    assert tx.category_id == cat.id


def test_clear_category(client, db_session, user):
    """`category_id: null` é limpeza explícita, não "campo ausente"."""
    cat = _category(db_session, user)
    tx = _transaction(db_session, user, category_id=cat.id)

    response = client.patch(f"/transactions/{tx.id}", json={"category_id": None})

    assert response.status_code == 200
    db_session.refresh(tx)
    assert tx.category_id is None


def test_changing_category_does_not_touch_is_transfer(client, db_session, user):
    cat = _category(db_session, user)
    tx = _transaction(db_session, user, is_transfer=True)

    client.patch(f"/transactions/{tx.id}", json={"category_id": str(cat.id)})

    db_session.refresh(tx)
    assert tx.is_transfer is True
    assert tx.category_id == cat.id


def test_toggle_is_transfer(client, db_session, user):
    tx = _transaction(db_session, user)

    client.patch(f"/transactions/{tx.id}", json={"is_transfer": True})

    db_session.refresh(tx)
    assert tx.is_transfer is True


def test_cannot_move_transaction_into_another_users_category(client, db_session, user, other_user):
    """`category_id` vem do cliente — sem checar o dono dava para vazar entre contas."""
    foreign = _category(db_session, other_user, name="Categoria alheia")
    tx = _transaction(db_session, user)

    response = client.patch(f"/transactions/{tx.id}", json={"category_id": str(foreign.id)})

    assert response.status_code == 404
    db_session.refresh(tx)
    assert tx.category_id is None


def test_cannot_update_another_users_transaction(client, db_session, user, other_user):
    cat = _category(db_session, user)
    foreign_tx = _transaction(db_session, other_user)

    response = client.patch(f"/transactions/{foreign_tx.id}", json={"category_id": str(cat.id)})

    assert response.status_code == 404


def test_empty_payload_is_rejected(client, db_session, user):
    tx = _transaction(db_session, user)
    assert client.patch(f"/transactions/{tx.id}", json={}).status_code == 400
