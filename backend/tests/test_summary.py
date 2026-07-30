import uuid
from decimal import Decimal
from datetime import date, timedelta

from app.models.budget import Budget
from app.models.category import Category
from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType


def _make_payable(db_session, user, amount, status=PayableStatus.PENDING, month=5, year=2026, category_id=None):
    p = Payable(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Test",
        amount=amount,
        due_date=date(year, month, 15),
        status=status,
        category_id=category_id,
    )
    db_session.add(p)
    db_session.commit()
    return p


def _make_transaction(
    db_session,
    user,
    amount,
    tx_type=TransactionType.EXPENSE,
    month=5,
    year=2026,
    category_id=None,
    is_transfer=False,
):
    t = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        date=date(year, month, 10),
        description="Test",
        amount=amount,
        type=tx_type,
        category_id=category_id,
        is_transfer=is_transfer,
    )
    db_session.add(t)
    db_session.commit()
    return t


def test_transfer_is_excluded_from_totals(db_session, user, client):
    """Transferência é dinheiro mudando de lugar — somá-la contaria a mesma
    grana duas vezes (a compra no cartão E a quitação da fatura)."""
    _make_transaction(db_session, user, 100, TransactionType.EXPENSE)
    _make_transaction(db_session, user, 900, TransactionType.EXPENSE, is_transfer=True)
    _make_transaction(db_session, user, 500, TransactionType.INCOME, is_transfer=True)

    data = client.get("/summary?month=5&year=2026").json()

    assert Decimal(data["total_expenses"]) == Decimal("100")
    assert Decimal(data["total_income"]) == Decimal("0")


def test_transfer_is_excluded_from_by_category(db_session, user, client):
    cat = Category(user_id=user.id, name="Mercado X", color_hex="#84CC16")
    db_session.add(cat)
    db_session.commit()

    _make_transaction(db_session, user, 40, category_id=cat.id)
    _make_transaction(db_session, user, 960, category_id=cat.id, is_transfer=True)

    data = client.get("/summary?month=5&year=2026").json()
    linha = next(c for c in data["by_category"] if c["category_name"] == "Mercado X")

    assert Decimal(linha["total_expenses"]) == Decimal("40")
    assert linha["transaction_count"] == 1


def test_category_expenses_ignore_income(db_session, user, client):
    """O campo antigo (total_transactions) somava receita e despesa no mesmo
    número, então não respondia "quanto gastei nessa categoria"."""
    cat = Category(user_id=user.id, name="Freelas", color_hex="#22C55E")
    db_session.add(cat)
    db_session.commit()

    _make_transaction(db_session, user, 300, TransactionType.EXPENSE, category_id=cat.id)
    _make_transaction(db_session, user, 5000, TransactionType.INCOME, category_id=cat.id)

    data = client.get("/summary?month=5&year=2026").json()
    linha = next(c for c in data["by_category"] if c["category_name"] == "Freelas")

    assert Decimal(linha["total_expenses"]) == Decimal("300")
    assert linha["transaction_count"] == 1


def test_by_category_sorted_by_expenses(db_session, user, client):
    """Categoria que só tem transação não pode afundar no fim da lista — é a
    maioria dos casos, já que o gasto real vem do banco."""
    grande = Category(user_id=user.id, name="Gasto grande", color_hex="#EF4444")
    payavel = Category(user_id=user.id, name="Só payable", color_hex="#38BDF8")
    db_session.add_all([grande, payavel])
    db_session.commit()

    _make_transaction(db_session, user, 900, category_id=grande.id)
    _make_payable(db_session, user, 700, category_id=payavel.id)

    data = client.get("/summary?month=5&year=2026").json()
    nomes = [c["category_name"] for c in data["by_category"]]

    assert nomes.index("Gasto grande") < nomes.index("Só payable")


def test_budget_used_pct_reacts_to_real_spending(db_session, user, client):
    """Antes o percentual vinha dos payables, então gasto de cartão importado do
    banco não movia o orçamento — o oposto do esperado."""
    cat = Category(user_id=user.id, name="Mercado B", color_hex="#84CC16")
    db_session.add(cat)
    db_session.commit()
    db_session.add(
        Budget(user_id=user.id, category_id=cat.id, month=5, year=2026, limit_amount=400)
    )
    db_session.commit()

    _make_transaction(db_session, user, 320, category_id=cat.id)

    data = client.get("/summary?month=5&year=2026").json()
    linha = next(c for c in data["by_category"] if c["category_name"] == "Mercado B")

    assert linha["budget_used_pct"] == 80.0


def test_budget_with_no_movement_still_appears(db_session, user, client):
    """"R$ 0 de R$ 400" é justamente o que o usuário quer ver — a categoria não
    pode desaparecer só porque ainda não houve gasto."""
    cat = Category(user_id=user.id, name="Reservado", color_hex="#A855F7")
    db_session.add(cat)
    db_session.commit()
    db_session.add(
        Budget(user_id=user.id, category_id=cat.id, month=5, year=2026, limit_amount=400)
    )
    db_session.commit()

    data = client.get("/summary?month=5&year=2026").json()
    linha = next((c for c in data["by_category"] if c["category_name"] == "Reservado"), None)

    assert linha is not None
    assert Decimal(linha["total_expenses"]) == Decimal("0")
    assert linha["budget_used_pct"] == 0.0


def test_overdue_counts_as_pending(db_session, user, client):
    """OVERDUE não era somado em nenhum total: a conta vencida sumia do agregado."""
    _make_payable(db_session, user, 250, status=PayableStatus.OVERDUE)

    data = client.get("/summary?month=5&year=2026").json()

    assert Decimal(data["total_pending"]) == Decimal("250")


def test_history_aggregates_each_month(db_session, user):
    from app.services.summary_service import get_history

    _make_transaction(db_session, user, 100, TransactionType.EXPENSE, month=6, year=2026)
    _make_transaction(db_session, user, 250, TransactionType.EXPENSE, month=7, year=2026)
    _make_transaction(db_session, user, 900, TransactionType.INCOME, month=7, year=2026)

    hist = get_history(db_session, user.id, months=3, today=date(2026, 7, 15))
    por_mes = {(m.month, m.year): m for m in hist.months}

    assert [(m.month, m.year) for m in hist.months] == [(5, 2026), (6, 2026), (7, 2026)]
    assert Decimal(por_mes[(6, 2026)].total_expenses) == Decimal("100")
    assert Decimal(por_mes[(7, 2026)].total_expenses) == Decimal("250")
    assert Decimal(por_mes[(7, 2026)].total_income) == Decimal("900")
    assert Decimal(por_mes[(5, 2026)].total_expenses) == Decimal("0")


def test_history_excludes_transfers(db_session, user):
    from app.services.summary_service import get_history

    _make_transaction(db_session, user, 100, month=7, year=2026)
    _make_transaction(db_session, user, 5000, month=7, year=2026, is_transfer=True)

    hist = get_history(db_session, user.id, months=1, today=date(2026, 7, 15))

    assert Decimal(hist.months[0].total_expenses) == Decimal("100")


def test_history_crosses_year_boundary(db_session, user):
    from app.services.summary_service import get_history

    _make_transaction(db_session, user, 70, month=12, year=2025)

    hist = get_history(db_session, user.id, months=3, today=date(2026, 2, 10))
    rotulos = [(m.month, m.year) for m in hist.months]

    assert rotulos == [(12, 2025), (1, 2026), (2, 2026)]
    assert Decimal(hist.months[0].total_expenses) == Decimal("70")


def test_history_isolates_users(db_session, user, other_user):
    from app.services.summary_service import get_history

    _make_transaction(db_session, other_user, 5000, month=7, year=2026)

    hist = get_history(db_session, user.id, months=1, today=date(2026, 7, 15))

    assert Decimal(hist.months[0].total_expenses) == Decimal("0")


def test_summary_empty_month(client):
    resp = client.get("/summary?month=1&year=2000")
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_pending"]) == 0
    assert float(data["total_paid"]) == 0
    assert float(data["balance"]) == 0
    assert data["by_category"] == []


def test_summary_with_payables(client, db_session, user):
    _make_payable(db_session, user, 100, PayableStatus.PENDING)
    _make_payable(db_session, user, 200, PayableStatus.PAID)
    resp = client.get("/summary?month=5&year=2026")
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_pending"]) == 100
    assert float(data["total_paid"]) == 200


def test_summary_excludes_other_users(client, db_session, user, other_user):
    _make_payable(db_session, other_user, 999, PayableStatus.PENDING)
    resp = client.get("/summary?month=5&year=2026")
    data = resp.json()
    assert float(data["total_pending"]) == 0


def test_summary_with_transactions(client, db_session, user):
    _make_transaction(db_session, user, 500, TransactionType.INCOME)
    _make_transaction(db_session, user, 300, TransactionType.EXPENSE)
    resp = client.get("/summary?month=5&year=2026")
    data = resp.json()
    assert float(data["total_income"]) == 500
    assert float(data["total_expenses"]) == 300
    assert float(data["balance"]) == 200


def test_summary_by_category(client, db_session, user):
    cat = Category(id=uuid.uuid4(), user_id=user.id, name="Alimentação", color_hex="#FF0000")
    db_session.add(cat)
    db_session.commit()
    _make_payable(db_session, user, 150, category_id=cat.id)
    resp = client.get("/summary?month=5&year=2026")
    data = resp.json()
    cats = {c["category_name"]: c for c in data["by_category"]}
    assert "Alimentação" in cats
    assert float(cats["Alimentação"]["total_payables"]) == 150


def test_upcoming_returns_pending_within_range(client, db_session, user):
    today = date.today()
    p = Payable(
        id=uuid.uuid4(),
        user_id=user.id,
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


def test_upcoming_excludes_paid(client, db_session, user):
    today = date.today()
    p = Payable(
        id=uuid.uuid4(),
        user_id=user.id,
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


def test_upcoming_excludes_beyond_range(client, db_session, user):
    today = date.today()
    p = Payable(
        id=uuid.uuid4(),
        user_id=user.id,
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


def test_upcoming_excludes_other_users(client, db_session, user, other_user):
    today = date.today()
    p = Payable(
        id=uuid.uuid4(),
        user_id=other_user.id,
        title="De outro usuário",
        amount=50,
        due_date=today + timedelta(days=3),
        status=PayableStatus.PENDING,
    )
    db_session.add(p)
    db_session.commit()
    resp = client.get("/payables/upcoming?days=7")
    ids = [item["id"] for item in resp.json()]
    assert str(p.id) not in ids


def test_history_returns_n_months(client):
    resp = client.get("/summary/history?months=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["months"]) == 3


def test_history_months_in_order(client, db_session):
    resp = client.get("/summary/history?months=6")
    months = resp.json()["months"]
    assert len(months) == 6
    labels = [(m["year"], m["month"]) for m in months]
    assert labels == sorted(labels)


def test_history_default_months(client):
    resp = client.get("/summary/history")
    assert resp.status_code == 200
    assert len(resp.json()["months"]) == 6


def test_history_totals_match_summary(client, db_session, user):
    from datetime import date
    from app.models.transaction import Transaction, TransactionType
    t = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        date=date(2026, 5, 10),
        description="Salário",
        amount=1000,
        type=TransactionType.INCOME,
    )
    db_session.add(t)
    db_session.commit()

    hist = client.get("/summary/history?months=6").json()
    may = next((m for m in hist["months"] if m["month"] == 5 and m["year"] == 2026), None)
    assert may is not None
    assert float(may["total_income"]) == 1000

    summary = client.get("/summary?month=5&year=2026").json()
    assert float(summary["total_income"]) == float(may["total_income"])
