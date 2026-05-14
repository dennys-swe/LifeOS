import io
import uuid
from datetime import date

from app.models.category import Category
from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType
from app.services.reconciliation_service import confirm_reconciliation, suggest_reconciliation


def _payable(db_session, amount, due_date=None, status=PayableStatus.PENDING):
    p = Payable(
        id=uuid.uuid4(),
        title="Conta Teste",
        amount=amount,
        due_date=due_date or date(2026, 5, 10),
        status=status,
    )
    db_session.add(p)
    db_session.commit()
    return p


def _transaction(db_session, amount, tx_date=None, tx_type=TransactionType.EXPENSE):
    t = Transaction(
        id=uuid.uuid4(),
        date=tx_date or date(2026, 5, 10),
        description="Pagamento Teste",
        amount=amount,
        type=tx_type,
    )
    db_session.add(t)
    db_session.commit()
    return t


def test_suggest_exact_match(db_session):
    p = _payable(db_session, 100, date(2026, 5, 10))
    t = _transaction(db_session, 100, date(2026, 5, 10))
    suggestions = suggest_reconciliation(db_session, [t])
    assert len(suggestions) == 1
    assert suggestions[0].confidence_score == 1.0
    assert suggestions[0].payable_id == p.id
    assert suggestions[0].transaction_id == t.id


def test_suggest_amount_tolerance(db_session):
    _payable(db_session, 100, date(2026, 5, 10))
    t = _transaction(db_session, 103, date(2026, 5, 10))  # 3% dentro da tolerância de 5%
    suggestions = suggest_reconciliation(db_session, [t])
    assert len(suggestions) == 1
    assert suggestions[0].confidence_score < 1.0


def test_suggest_date_tolerance(db_session):
    _payable(db_session, 100, date(2026, 5, 15))
    t = _transaction(db_session, 100, date(2026, 5, 10))  # 5 dias de diferença
    suggestions = suggest_reconciliation(db_session, [t])
    assert len(suggestions) == 1
    assert suggestions[0].confidence_score == 0.8  # exact amount, date not exact


def test_suggest_no_match(db_session):
    _payable(db_session, 100, date(2026, 5, 10))
    t = _transaction(db_session, 200, date(2026, 5, 10))  # 100% diferença, fora da tolerância
    suggestions = suggest_reconciliation(db_session, [t])
    assert len(suggestions) == 0


def test_suggest_excludes_paid_payables(db_session):
    _payable(db_session, 100, date(2026, 5, 10), status=PayableStatus.PAID)
    t = _transaction(db_session, 100, date(2026, 5, 10))
    suggestions = suggest_reconciliation(db_session, [t])
    assert len(suggestions) == 0


def test_suggest_excludes_income_transactions(db_session):
    _payable(db_session, 100, date(2026, 5, 10))
    t = _transaction(db_session, 100, date(2026, 5, 10), tx_type=TransactionType.INCOME)
    suggestions = suggest_reconciliation(db_session, [t])
    assert len(suggestions) == 0


def test_confirm_reconciliation_marks_paid(db_session):
    p = _payable(db_session, 150, date(2026, 5, 10))
    t = _transaction(db_session, 150, date(2026, 5, 12))

    updated = confirm_reconciliation(db_session, transaction_id=t.id, payable_id=p.id)

    assert updated.status == PayableStatus.PAID
    assert updated.payment_date == date(2026, 5, 12)
    assert updated.transaction_id == t.id


def test_upload_returns_suggestions(client, db_session):
    p = Payable(
        id=uuid.uuid4(),
        title="Internet",
        amount=99.90,
        due_date=date(2026, 5, 10),
        status=PayableStatus.PENDING,
    )
    db_session.add(p)
    db_session.commit()

    csv_content = "Data,Descricao,Valor\n10/05/2026,Pagto Internet,-99.90\n"
    csv_bytes = csv_content.encode()

    response = client.post(
        "/transactions/upload",
        files={"file": ("extrato.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert "transactions" in data
    assert "suggestions" in data
    assert len(data["transactions"]) == 1
    assert len(data["suggestions"]) >= 1
    suggestion = data["suggestions"][0]
    assert suggestion["payable_id"] == str(p.id)
    assert suggestion["confidence_score"] == 1.0
