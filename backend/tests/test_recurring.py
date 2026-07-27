from datetime import date

from app.schemas.recurring_payable import RecurringPayableCreate, RecurringPayableUpdate
from app.services.recurring_service import (
    create_recurring,
    delete_recurring,
    generate_for_month,
    get_recurring,
    list_recurring,
    update_recurring,
)


def _make_recurring(db_session, user, title="Internet", amount=99.90, day_of_month=10, active=True, start_date=date(2025, 1, 1)):
    payload = RecurringPayableCreate(
        title=title, amount=amount, day_of_month=day_of_month, active=active, start_date=start_date
    )
    return create_recurring(db_session, user.id, payload)


def test_create_recurring_payable(db_session, user):
    rec = _make_recurring(db_session, user)
    assert rec.id is not None
    assert rec.user_id == user.id
    assert rec.title == "Internet"
    assert rec.active is True


def test_list_recurring_payables(db_session, user):
    _make_recurring(db_session, user, title="Internet")
    _make_recurring(db_session, user, title="Aluguel")
    result = list_recurring(db_session, user.id)
    titles = [r.title for r in result]
    assert "Internet" in titles
    assert "Aluguel" in titles


def test_list_recurring_payables_excludes_other_users(db_session, user, other_user):
    _make_recurring(db_session, user, title="Internet")
    _make_recurring(db_session, other_user, title="Aluguel")
    result = list_recurring(db_session, user.id)
    titles = [r.title for r in result]
    assert titles == ["Internet"]


def test_update_recurring(db_session, user):
    rec = _make_recurring(db_session, user)
    updated = update_recurring(db_session, rec, RecurringPayableUpdate(amount=150.00))
    assert float(updated.amount) == 150.00


def test_generate_creates_payables_for_month(db_session, user):
    _make_recurring(db_session, user, day_of_month=15)
    created = generate_for_month(db_session, user.id, month=5, year=2026)
    assert len(created) == 1
    assert created[0].due_date == date(2026, 5, 15)
    assert created[0].user_id == user.id


def test_generate_no_duplicate(db_session, user):
    _make_recurring(db_session, user, day_of_month=10)
    first = generate_for_month(db_session, user.id, month=5, year=2026)
    assert len(first) == 1
    second = generate_for_month(db_session, user.id, month=5, year=2026)
    assert len(second) == 0


def test_generate_day_exceeds_month_days(db_session, user):
    _make_recurring(db_session, user, day_of_month=31)
    created = generate_for_month(db_session, user.id, month=2, year=2026)
    assert len(created) == 1
    assert created[0].due_date == date(2026, 2, 28)


def test_generate_only_active(db_session, user):
    _make_recurring(db_session, user, title="Ativa", active=True)
    _make_recurring(db_session, user, title="Inativa", active=False)
    created = generate_for_month(db_session, user.id, month=5, year=2026)
    assert len(created) == 1
    assert created[0].title == "Ativa"


def test_generate_only_for_current_user(db_session, user, other_user):
    _make_recurring(db_session, user, title="Minha", day_of_month=10)
    _make_recurring(db_session, other_user, title="Do outro", day_of_month=10)
    created = generate_for_month(db_session, user.id, month=5, year=2026)
    assert len(created) == 1
    assert created[0].title == "Minha"


def test_delete_recurring_preserves_payables(db_session, user):
    rec = _make_recurring(db_session, user)
    payables = generate_for_month(db_session, user.id, month=5, year=2026)
    assert len(payables) == 1
    payable = payables[0]
    payable_id = payable.id

    delete_recurring(db_session, rec)

    db_session.expire_all()
    from app.models.payable import Payable
    remaining = db_session.get(Payable, payable_id)
    assert remaining is not None
    assert remaining.recurring_payable_id is None


def test_get_recurring_not_found(db_session, user):
    import uuid
    result = get_recurring(db_session, user.id, uuid.uuid4())
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
        "start_date": "2026-01-01",
    })
    response = client.post("/recurring-payables/generate?month=6&year=2026")
    assert response.status_code == 201
    assert len(response.json()) == 1


def test_delete_recurring_not_found(client):
    response = client.delete("/recurring-payables/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
