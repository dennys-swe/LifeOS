from datetime import date
from decimal import Decimal

from app.models.credit_card_bill import CreditCardBill, CreditCardBillStatus
from app.models.payable import Payable
from app.services import bill_service, open_bill_service


def _tx(amount, tx_date, *, forecast=None, bill_id=None, status="PENDING",
        description="COMPRA", installment=None, total_installments=None,
        card="1111", category_id=None, converted=None):
    meta = {"cardNumber": card}
    if forecast:
        meta["billForecastDate"] = forecast
    if bill_id:
        meta["billId"] = bill_id
    if installment:
        meta["installmentNumber"] = installment
        meta["totalInstallments"] = total_installments
    return {
        "amount": amount,
        "amountInAccountCurrency": converted,
        "date": f"{tx_date}T03:00:00.000Z",
        "status": status,
        "description": description,
        "categoryId": category_id,
        "creditCardMetadata": meta,
    }


def test_sums_transactions_forecast_to_target_month():
    txs = [
        _tx(100, "2026-07-20", forecast="2026-08"),
        _tx(50, "2026-07-25", forecast="2026-08"),
        _tx(999, "2026-07-31", forecast="2026-09"),  # ciclo seguinte, fora
    ]
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 8), date(2026, 7, 8)
    ) == Decimal("150.00")


def test_includes_pending_between_closing_and_due_date():
    """Nubank não etiqueta competência nesse intervalo — sem isso some da conta."""
    txs = [_tx(200.98, "2026-07-03")]
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 8), date(2026, 7, 8)
    ) == Decimal("200.98")


def test_excludes_bill_payment_even_when_categorized_as_transfer():
    """"PAGAMENTO COM SALDO" vem como `Transfers`, não como pagamento de fatura."""
    txs = [
        _tx(100, "2026-07-20", forecast="2026-08"),
        _tx(-1214.35, "2026-07-12", forecast="2026-08", description="PAGAMENTO COM SALDO"),
    ]
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 8), date(2026, 7, 8)
    ) == Decimal("100.00")


def test_uses_converted_amount_for_foreign_currency():
    txs = [_tx(7.75, "2026-07-10", forecast="2026-08", converted=41.37)]
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 8), date(2026, 7, 8)
    ) == Decimal("41.37")


def test_projects_next_installment_when_bank_does_not_emit_it():
    """Nubank só emite a parcela do ciclo corrente; a seguinte precisa ser projetada."""
    txs = [
        _tx(55.77, "2026-04-03", forecast="2026-05", description="GUANABARA 1/5",
            installment=1, total_installments=5),
        _tx(55.77, "2026-05-01", forecast="2026-06", description="GUANABARA 2/5",
            installment=2, total_installments=5),
        _tx(55.77, "2026-06-03", forecast="2026-07", description="GUANABARA 3/5",
            installment=3, total_installments=5),
    ]
    # Projeta 4/5 uma única vez — projetar a partir de cada parcela conhecida
    # contaria o valor três vezes.
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 8), date(2026, 7, 8)
    ) == Decimal("55.77")


def test_does_not_project_beyond_contracted_installments():
    txs = [
        _tx(55.77, "2026-06-03", forecast="2026-07", bill_id="bill-jul", status="POSTED",
            description="GUANABARA 5/5", installment=5, total_installments=5),
    ]
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 8), date(2026, 7, 8)
    ) == Decimal("0.00")


def test_counts_future_dated_installment_without_projecting_it_twice():
    """Itaú/Luiza já emitem a parcela futura datada no vencimento em que cai."""
    txs = [
        _tx(15.99, "2026-08-10", description="ANUIDADE 02/12",
            installment=2, total_installments=12),
        _tx(15.99, "2026-09-10", description="ANUIDADE 03/12",
            installment=3, total_installments=12),
    ]
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 10), date(2026, 7, 10)
    ) == Decimal("15.99")


def test_ignores_installment_already_charged_in_closed_bill():
    """A mesma parcela reemitida como pendência não pode ser cobrada de novo."""
    txs = [
        _tx(29.82, "2026-06-30", bill_id="bill-jul", status="POSTED",
            description="PIX MARIA 02/02", installment=2, total_installments=2),
        _tx(29.82, "2026-07-10", description="PIX MARIA 02/02",
            installment=2, total_installments=2),
    ]
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 10), date(2026, 7, 10)
    ) == Decimal("0.00")


def test_pending_with_stale_forecast_rolls_into_open_cycle():
    """Itaú rotula pelo mês da compra: '2026-07' com a fatura de julho já paga."""
    txs = [_tx(78.12, "2026-07-21", forecast="2026-07")]
    assert open_bill_service.compute_open_bill_amount(
        txs, date(2026, 8, 10), date(2026, 7, 10)
    ) == Decimal("78.12")


def test_next_due_date_keeps_day_of_month():
    assert open_bill_service.next_due_date(date(2026, 7, 8), date(2026, 8, 4)) == date(2026, 8, 8)
    assert open_bill_service.next_due_date(date(2026, 12, 10), date(2027, 1, 2)) == date(2027, 1, 10)


def test_next_due_date_clamps_to_short_month():
    assert open_bill_service.next_due_date(date(2027, 1, 31), date(2027, 2, 1)) == date(2027, 2, 28)


def _make_account(db_session, user):
    from app.models.bank_account import BankAccount

    account = BankAccount(
        user_id=user.id, name="Cartão", bank_name="Banco", account_type="checking",
        external_id="item-1",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def _closed_bill(db_session, user, account, due_date):
    return bill_service.upsert_bill(
        db_session, user.id, account, "pluggy-acc-1",
        {"id": f"closed-{due_date}", "dueDate": f"{due_date}T00:00:00Z", "totalAmount": 400.0},
        card_name="Cartão X",
    )


def test_open_bill_does_not_create_payable(db_session, user):
    """Fatura aberta muda a cada compra — não é obrigação a pagar ainda."""
    account = _make_account(db_session, user)
    _closed_bill(db_session, user, account, "2026-07-08")

    bill = bill_service.upsert_open_bill(
        db_session, user.id, account, "pluggy-acc-1",
        [_tx(150, "2026-07-20", forecast="2026-08")],
        card_name="Cartão X", today=date(2026, 8, 4),
    )

    assert bill.status == CreditCardBillStatus.OPEN
    assert bill.total_amount == Decimal("150.00")
    assert bill.payable_id is None
    assert db_session.query(Payable).filter(Payable.title.like("%08/2026%")).count() == 0


def test_open_bill_needs_a_previous_closed_bill(db_session, user):
    """Sem fatura fechada não há dia de vencimento nem corte de ciclo conhecidos."""
    account = _make_account(db_session, user)

    assert bill_service.upsert_open_bill(
        db_session, user.id, account, "pluggy-acc-1",
        [_tx(150, "2026-07-20", forecast="2026-08")],
        today=date(2026, 8, 4),
    ) is None


def test_closed_bill_replaces_open_estimate_and_generates_payable(db_session, user):
    account = _make_account(db_session, user)
    _closed_bill(db_session, user, account, "2026-07-08")
    estimate = bill_service.upsert_open_bill(
        db_session, user.id, account, "pluggy-acc-1",
        [_tx(150, "2026-07-20", forecast="2026-08")],
        card_name="Cartão X", today=date(2026, 8, 4),
    )

    official = bill_service.upsert_bill(
        db_session, user.id, account, "pluggy-acc-1",
        {"id": "real-aug", "dueDate": "2026-08-08T00:00:00Z", "totalAmount": 588.37},
        card_name="Cartão X",
    )

    # Mesmo registro, agora oficial — não duplica a fatura do mês.
    assert official.id == estimate.id
    assert official.status == CreditCardBillStatus.CLOSED
    assert official.total_amount == Decimal("588.37")
    assert db_session.query(CreditCardBill).filter(
        CreditCardBill.due_date == date(2026, 8, 8)
    ).count() == 1


def test_open_bill_is_recomputed_on_next_sync(db_session, user):
    account = _make_account(db_session, user)
    _closed_bill(db_session, user, account, "2026-07-08")
    first = bill_service.upsert_open_bill(
        db_session, user.id, account, "pluggy-acc-1",
        [_tx(150, "2026-07-20", forecast="2026-08")], today=date(2026, 8, 4),
    )
    second = bill_service.upsert_open_bill(
        db_session, user.id, account, "pluggy-acc-1",
        [_tx(150, "2026-07-20", forecast="2026-08"), _tx(70, "2026-08-01", forecast="2026-08")],
        today=date(2026, 8, 4),
    )

    assert second.id == first.id
    assert second.total_amount == Decimal("220.00")


def test_no_open_bill_when_bank_already_projects_far_ahead(db_session, user):
    """Inter publica faturas até 2027 — o "mês seguinte" não é ciclo corrente."""
    account = _make_account(db_session, user)
    _closed_bill(db_session, user, account, "2027-06-12")

    assert bill_service.upsert_open_bill(
        db_session, user.id, account, "pluggy-acc-1",
        [_tx(150, "2026-07-20", forecast="2026-08")],
        today=date(2026, 8, 4),
    ) is None
