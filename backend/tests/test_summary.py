import uuid
from datetime import date, timedelta

from app.models.category import Category
from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType


def _make_payable(db_session, amount, status=PayableStatus.PENDING, month=5, year=2026, category_id=None):
    p = Payable(
        id=uuid.uuid4(),
        title="Test",
        amount=amount,
        due_date=date(year, month, 15),
        status=status,
        category_id=category_id,
    )
    db_session.add(p)
    db_session.commit()
    return p


def _make_transaction(db_session, amount, tx_type=TransactionType.EXPENSE, month=5, year=2026, category_id=None):
    t = Transaction(
        id=uuid.uuid4(),
        date=date(year, month, 10),
        description="Test",
        amount=amount,
        type=tx_type,
        category_id=category_id,
    )
    db_session.add(t)
    db_session.commit()
    return t


def test_summary_empty_month(client):
    resp = client.get("/summary?month=1&year=2000")
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_pending"]) == 0
    assert float(data["total_paid"]) == 0
    assert float(data["balance"]) == 0
    assert data["by_category"] == []


def test_summary_with_payables(client, db_session):
    _make_payable(db_session, 100, PayableStatus.PENDING)
    _make_payable(db_session, 200, PayableStatus.PAID)
    resp = client.get("/summary?month=5&year=2026")
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_pending"]) == 100
    assert float(data["total_paid"]) == 200


def test_summary_with_transactions(client, db_session):
    _make_transaction(db_session, 500, TransactionType.INCOME)
    _make_transaction(db_session, 300, TransactionType.EXPENSE)
    resp = client.get("/summary?month=5&year=2026")
    data = resp.json()
    assert float(data["total_income"]) == 500
    assert float(data["total_expenses"]) == 300
    assert float(data["balance"]) == 200


def test_summary_by_category(client, db_session):
    cat = Category(id=uuid.uuid4(), name="Alimentação", color_hex="#FF0000")
    db_session.add(cat)
    db_session.commit()
    _make_payable(db_session, 150, category_id=cat.id)
    resp = client.get("/summary?month=5&year=2026")
    data = resp.json()
    cats = {c["category_name"]: c for c in data["by_category"]}
    assert "Alimentação" in cats
    assert float(cats["Alimentação"]["total_payables"]) == 150


def test_upcoming_returns_pending_within_range(client, db_session):
    today = date.today()
    p = Payable(
        id=uuid.uuid4(),
        title="Vence em breve",
        amount=50,
        due_date=today + timedelta(days=3),
        status=PayableStatus.PENDING,
    )
    db_session.add(p)
    db_session.commit()
    resp = client.get("/payables/upcoming?days=7")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()]
    assert str(p.id) in ids


def test_upcoming_excludes_paid(client, db_session):
    today = date.today()
    p = Payable(
        id=uuid.uuid4(),
        title="Já pago",
        amount=50,
        due_date=today + timedelta(days=2),
        status=PayableStatus.PAID,
    )
    db_session.add(p)
    db_session.commit()
    resp = client.get("/payables/upcoming?days=7")
    ids = [item["id"] for item in resp.json()]
    assert str(p.id) not in ids


def test_upcoming_excludes_beyond_range(client, db_session):
    today = date.today()
    p = Payable(
        id=uuid.uuid4(),
        title="Longe",
        amount=50,
        due_date=today + timedelta(days=15),
        status=PayableStatus.PENDING,
    )
    db_session.add(p)
    db_session.commit()
    resp = client.get("/payables/upcoming?days=7")
    ids = [item["id"] for item in resp.json()]
    assert str(p.id) not in ids
