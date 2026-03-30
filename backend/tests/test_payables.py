from datetime import date, timedelta

from app.models.payable import PayableStatus
from app.schemas.payable import PayableCreate
from app.services.payable_service import create_payable, is_due_today, is_overdue


def test_create_payable(db_session):
    payload = PayableCreate(
        title="Internet",
        amount=120.50,
        due_date=date.today(),
        status=PayableStatus.PENDING,
        payment_date=None,
    )

    payable = create_payable(db_session, payload)

    assert payable.id is not None
    assert payable.title == payload.title
    assert payable.amount == payload.amount
    assert payable.status == PayableStatus.PENDING


def test_due_today_and_overdue_logic():
    today = date(2026, 3, 29)

    class Dummy:
        def __init__(self, due_date, status):
            self.due_date = due_date
            self.status = status

    due_today = Dummy(today, PayableStatus.PENDING)
    overdue = Dummy(today - timedelta(days=1), PayableStatus.PENDING)
    paid = Dummy(today - timedelta(days=1), PayableStatus.PAID)

    assert is_due_today(due_today, today=today) is True
    assert is_overdue(due_today, today=today) is False

    assert is_overdue(overdue, today=today) is True
    assert is_due_today(overdue, today=today) is False

    assert is_overdue(paid, today=today) is False