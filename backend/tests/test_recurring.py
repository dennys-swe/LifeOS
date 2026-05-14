from datetime import date

import pytest

from app.models.recurring_payable import RecurringPayable
from app.schemas.recurring_payable import RecurringPayableCreate, RecurringPayableUpdate
from app.services.recurring_service import (
    create_recurring,
    delete_recurring,
    generate_for_month,
    get_recurring,
    list_recurring,
    update_recurring,
)


def _make_recurring(db_session, title="Internet", amount=99.90, day_of_month=10, active=True):
    payload = RecurringPayableCreate(
        title=title, amount=amount, day_of_month=day_of_month, active=active
    )
    return create_recurring(db_session, payload)


def test_create_recurring_payable(db_session):
    rec = _make_recurring(db_session)
    assert rec.id is not None
    assert rec.title == "Internet"
    assert rec.active is True


def test_list_recurring_payables(db_session):
    _make_recurring(db_session, title="Internet")
    _make_recurring(db_session, title="Aluguel")
    result = list_recurring(db_session)
    titles = [r.title for r in result]
    assert "Internet" in titles
    assert "Aluguel" in titles


def test_update_recurring(db_session):
    rec = _make_recurring(db_session)
    updated = update_recurring(db_session, rec, RecurringPayableUpdate(amount=150.00))
    assert float(updated.amount) == 150.00


def test_generate_creates_payables_for_month(db_session):
    _make_recurring(db_session, day_of_month=15)
    created = generate_for_month(db_session, month=5, year=2026)
    assert len(created) == 1
    assert created[0].due_date == date(2026, 5, 15)


def test_generate_no_duplicate(db_session):
    _make_recurring(db_session, day_of_month=10)
    first = generate_for_month(db_session, month=5, year=2026)
    assert len(first) == 1
    second = generate_for_month(db_session, month=5, year=2026)
    assert len(second) == 0


def test_generate_day_exceeds_month_days(db_session):
    _make_recurring(db_session, day_of_month=31)
    created = generate_for_month(db_session, month=2, year=2026)
    assert len(created) == 1
    assert created[0].due_date == date(2026, 2, 28)


def test_generate_only_active(db_session):
    _make_recurring(db_session, title="Ativa", active=True)
    _make_recurring(db_session, title="Inativa", active=False)
    created = generate_for_month(db_session, month=5, year=2026)
    assert len(created) == 1
    assert created[0].title == "Ativa"


def test_delete_recurring_preserves_payables(db_session):
    rec = _make_recurring(db_session)
    payables = generate_for_month(db_session, month=5, year=2026)
    assert len(payables) == 1
    payable = payables[0]
    payable_id = payable.id

    delete_recurring(db_session, rec)

    db_session.expire_all()
    from app.models.payable import Payable
    remaining = db_session.get(Payable, payable_id)
    assert remaining is not None
    assert remaining.recurring_payable_id is None


def test_get_recurring_not_found(db_session):
    import uuid
    result = get_recurring(db_session, uuid.uuid4())
    assert result is None


def test_create_recurring_via_api(client):
    response = client.post("/recurring-payables", json={
        "title": "Netflix",
        "amount": 45.90,
        "day_of_month": 5,
        "active": True,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["id"]
    assert data["title"] == "Netflix"


def test_generate_via_api(client):
    client.post("/recurring-payables", json={
        "title": "Academia",
        "amount": 80.00,
        "day_of_month": 1,
        "active": True,
    })
    response = client.post("/recurring-payables/generate?month=6&year=2026")
    assert response.status_code == 201
    assert len(response.json()) == 1


def test_delete_recurring_not_found(client):
    response = client.delete("/recurring-payables/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
