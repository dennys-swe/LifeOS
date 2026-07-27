import uuid
from datetime import date
from decimal import Decimal

from app.models.bank_account import BankAccount
from app.models.credit_card_bill import CreditCardBill
from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType
from app.services.reconciliation_service import (
    auto_reconcile_confident_matches,
    confirm_reconciliation,
    suggest_pending,
    suggest_reconciliation,
)


def _payable(db_session, user, amount, due_date=None, status=PayableStatus.PENDING):
    p = Payable(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Conta Teste",
        amount=amount,
        due_date=due_date or date(2026, 5, 10),
        status=status,
    )
    db_session.add(p)
    db_session.commit()
    return p


def _transaction(db_session, user, amount, tx_date=None, tx_type=TransactionType.EXPENSE):
    t = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        date=tx_date or date(2026, 5, 10),
        description="Pagamento Teste",
        amount=amount,
        type=tx_type,
    )
    db_session.add(t)
    db_session.commit()
    return t


def _bill_payable(db_session, user, amount, due_date):
    """Cria um payable de fatura (linkado a um CreditCardBill), diferente de
    _payable — é o que ativa a heurística de "eco" de pagamento de fatura."""
    p = _payable(db_session, user, amount, due_date)
    acc = BankAccount(user_id=user.id, name="Cartão", bank_name="Banco Teste", account_type="credit")
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)

    bill = CreditCardBill(
        user_id=user.id,
        bank_account_id=acc.id,
        pluggy_account_id="pluggy-acc-1",
        external_id=str(uuid.uuid4()),
        due_date=due_date,
        total_amount=amount,
        payable_id=p.id,
    )
    db_session.add(bill)
    db_session.commit()
    return p


def test_suggest_exact_match(db_session, user):
    p = _payable(db_session, user, 100, date(2026, 5, 10))
    t = _transaction(db_session, user, 100, date(2026, 5, 10))
    suggestions = suggest_reconciliation(db_session, user.id, [t])
    assert len(suggestions) == 1
    assert suggestions[0].confidence_score == 1.0
    assert suggestions[0].payable_id == p.id
    assert suggestions[0].transaction_id == t.id


def test_suggest_amount_tolerance(db_session, user):
    _payable(db_session, user, 100, date(2026, 5, 10))
    t = _transaction(db_session, user, 103, date(2026, 5, 10))  # 3% dentro da tolerância de 5%
    suggestions = suggest_reconciliation(db_session, user.id, [t])
    assert len(suggestions) == 1
    assert suggestions[0].confidence_score < 1.0


def test_suggest_date_tolerance(db_session, user):
    _payable(db_session, user, 100, date(2026, 5, 15))
    t = _transaction(db_session, user, 100, date(2026, 5, 10))  # 5 dias de diferença
    suggestions = suggest_reconciliation(db_session, user.id, [t])
    assert len(suggestions) == 1
    assert suggestions[0].confidence_score == 0.8  # exact amount, date not exact


def test_suggest_no_match(db_session, user):
    _payable(db_session, user, 100, date(2026, 5, 10))
    t = _transaction(db_session, user, 200, date(2026, 5, 10))  # 100% diferença, fora da tolerância
    suggestions = suggest_reconciliation(db_session, user.id, [t])
    assert len(suggestions) == 0


def test_suggest_excludes_paid_payables(db_session, user):
    _payable(db_session, user, 100, date(2026, 5, 10), status=PayableStatus.PAID)
    t = _transaction(db_session, user, 100, date(2026, 5, 10))
    suggestions = suggest_reconciliation(db_session, user.id, [t])
    assert len(suggestions) == 0


def test_suggest_excludes_income_transactions(db_session, user):
    _payable(db_session, user, 100, date(2026, 5, 10))
    t = _transaction(db_session, user, 100, date(2026, 5, 10), tx_type=TransactionType.INCOME)
    suggestions = suggest_reconciliation(db_session, user.id, [t])
    assert len(suggestions) == 0


def test_suggest_excludes_other_users_payables(db_session, user, other_user):
    _payable(db_session, other_user, 100, date(2026, 5, 10))
    t = _transaction(db_session, user, 100, date(2026, 5, 10))
    suggestions = suggest_reconciliation(db_session, user.id, [t])
    assert len(suggestions) == 0


def test_confirm_reconciliation_marks_paid(db_session, user):
    p = _payable(db_session, user, 150, date(2026, 5, 10))
    t = _transaction(db_session, user, 150, date(2026, 5, 12))

    updated = confirm_reconciliation(db_session, user.id, transaction_id=t.id, payable_id=p.id)

    assert updated.status == PayableStatus.PAID
    assert updated.payment_date == date(2026, 5, 12)
    assert updated.transaction_id == t.id


def test_confirm_reconciliation_rejects_other_users_payable(db_session, user, other_user):
    p = _payable(db_session, other_user, 150, date(2026, 5, 10))
    t = _transaction(db_session, user, 150, date(2026, 5, 12))

    try:
        confirm_reconciliation(db_session, user.id, transaction_id=t.id, payable_id=p.id)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_auto_reconcile_confirms_unique_exact_match(db_session, user):
    p = _payable(db_session, user, 100, date(2026, 5, 10))
    t = _transaction(db_session, user, 100, date(2026, 5, 10))
    suggestions = suggest_reconciliation(db_session, user.id, [t])

    confirmed = auto_reconcile_confident_matches(db_session, user.id, suggestions)

    assert confirmed == [t.id]
    db_session.refresh(p)
    assert p.status == PayableStatus.PAID


def test_auto_reconcile_skips_ambiguous_payable_match(db_session, user):
    p1 = _payable(db_session, user, 100, date(2026, 5, 10))
    p2 = _payable(db_session, user, 100, date(2026, 5, 10))
    t = _transaction(db_session, user, 100, date(2026, 5, 10))
    suggestions = suggest_reconciliation(db_session, user.id, [t])

    confirmed = auto_reconcile_confident_matches(db_session, user.id, suggestions)

    assert confirmed == []
    db_session.refresh(p1)
    db_session.refresh(p2)
    assert p1.status == PayableStatus.PENDING
    assert p2.status == PayableStatus.PENDING


def test_auto_reconcile_resolves_bill_payment_echo(db_session, user):
    """Observado em dados reais: toda fatura paga gera 2 transações no mesmo
    valor — o débito real ("FATURA PAGA X") e um eco genérico do banco
    ("Pagamento recebido"). Como isso é garantido pra faturas de cartão, deve
    confirmar sozinho o débito real sem precisar de revisão manual."""
    p = _bill_payable(db_session, user, Decimal("655.34"), date(2026, 5, 10))
    real_tx = Transaction(
        user_id=user.id, date=date(2026, 5, 10), description="FATURA PAGA CARTAO LUIZA",
        amount=Decimal("655.34"), type=TransactionType.EXPENSE,
    )
    echo_tx = Transaction(
        user_id=user.id, date=date(2026, 5, 10), description="Pagamento recebido",
        amount=Decimal("655.34"), type=TransactionType.EXPENSE,
    )
    db_session.add_all([real_tx, echo_tx])
    db_session.commit()

    suggestions = suggest_reconciliation(db_session, user.id, [real_tx, echo_tx])
    confirmed = auto_reconcile_confident_matches(db_session, user.id, suggestions)

    assert confirmed == [real_tx.id]
    db_session.refresh(p)
    assert p.status == PayableStatus.PAID
    assert p.transaction_id == real_tx.id


def test_auto_reconcile_does_not_resolve_echo_for_non_bill_payables(db_session, user):
    """A heurística de eco só vale pra payables linkados a CreditCardBill —
    pra contas normais, duas transações com a mesma descrição genérica e valor
    continuam ambíguas e exigem revisão manual."""
    p = _payable(db_session, user, Decimal("655.34"), date(2026, 5, 10))
    real_tx = Transaction(
        user_id=user.id, date=date(2026, 5, 10), description="FATURA PAGA CARTAO LUIZA",
        amount=Decimal("655.34"), type=TransactionType.EXPENSE,
    )
    echo_tx = Transaction(
        user_id=user.id, date=date(2026, 5, 10), description="Pagamento recebido",
        amount=Decimal("655.34"), type=TransactionType.EXPENSE,
    )
    db_session.add_all([real_tx, echo_tx])
    db_session.commit()

    suggestions = suggest_reconciliation(db_session, user.id, [real_tx, echo_tx])
    confirmed = auto_reconcile_confident_matches(db_session, user.id, suggestions)

    assert confirmed == []
    db_session.refresh(p)
    assert p.status == PayableStatus.PENDING


def test_auto_reconcile_does_not_resolve_echo_when_both_generic(db_session, user):
    """Se os dois candidatos forem descrições genéricas (nenhum específico
    sobra), continua ambíguo — não escolhe às cegas."""
    p = _bill_payable(db_session, user, Decimal("655.34"), date(2026, 5, 10))
    echo1 = Transaction(
        user_id=user.id, date=date(2026, 5, 10), description="Pagamento recebido",
        amount=Decimal("655.34"), type=TransactionType.EXPENSE,
    )
    echo2 = Transaction(
        user_id=user.id, date=date(2026, 5, 10), description="PAGAMENTO COM SALDO",
        amount=Decimal("655.34"), type=TransactionType.EXPENSE,
    )
    db_session.add_all([echo1, echo2])
    db_session.commit()

    suggestions = suggest_reconciliation(db_session, user.id, [echo1, echo2])
    confirmed = auto_reconcile_confident_matches(db_session, user.id, suggestions)

    assert confirmed == []
    db_session.refresh(p)
    assert p.status == PayableStatus.PENDING


# Cobertura de auto-reconciliação via CSV foi movida para o fluxo de sync da
# Pluggy — ver test_bank_accounts.py::TestSyncAccountService (import de
# extrato manual foi removido em favor de sincronização 100% automática).


def test_suggest_suppresses_approx_match_when_exact_match_exists(db_session, user):
    """Observado em dados reais: um Pix de R$ 650 pra outra pessoa coincidiu
    (dentro da tolerância de 5%) com uma fatura de R$ 655,34 que já tinha um
    candidato de valor exato — o aproximado é ruído e não deveria aparecer."""
    p = _payable(db_session, user, Decimal("655.34"), date(2026, 5, 10))
    exact_tx = _transaction(db_session, user, Decimal("655.34"), date(2026, 5, 10))
    approx_tx = _transaction(db_session, user, Decimal("650.00"), date(2026, 5, 10))

    suggestions = suggest_reconciliation(db_session, user.id, [exact_tx, approx_tx])

    assert len(suggestions) == 1
    assert suggestions[0].transaction_id == exact_tx.id
    assert suggestions[0].confidence_score == 1.0


def test_suggest_keeps_approx_match_when_no_exact_candidate(db_session, user):
    _payable(db_session, user, Decimal("655.34"), date(2026, 5, 10))
    approx_tx = _transaction(db_session, user, Decimal("650.00"), date(2026, 5, 10))

    suggestions = suggest_reconciliation(db_session, user.id, [approx_tx])

    assert len(suggestions) == 1
    assert suggestions[0].confidence_score == 0.6


def test_suggest_pending_covers_whole_unreconciled_history(db_session, user):
    """suggest_pending não depende de uma lista de transações "recém-importadas"
    de um sync específico — usado pela tela de Bancos & Faturas pra mostrar
    confirmações pendentes mesmo quando o sync rodou em background (cron
    diário) sem ninguém olhando a resposta daquele request.

    Data deslocada pra gerar confidence 0.8 em vez de 1.0 — um candidato único
    a 1.0 seria auto-confirmado (ver test_suggest_pending_auto_resolves_*) e
    não sobraria pra testar o que este teste quer verificar."""
    p = _payable(db_session, user, 100, date(2026, 5, 10))
    _transaction(db_session, user, 100, date(2026, 5, 12))

    suggestions = suggest_pending(db_session, user.id)

    assert len(suggestions) == 1
    assert suggestions[0].payable_id == p.id


def test_suggest_pending_excludes_already_reconciled_transactions(db_session, user):
    p = _payable(db_session, user, 100, date(2026, 5, 10))
    t = _transaction(db_session, user, 100, date(2026, 5, 10))
    confirm_reconciliation(db_session, user.id, transaction_id=t.id, payable_id=p.id)

    # A conciliação marca o payable como PAID, então não deveria mais aparecer
    # como pendente — mesmo que a transação continue existindo.
    suggestions = suggest_pending(db_session, user.id)

    assert suggestions == []


def test_suggest_pending_auto_resolves_old_bill_payment_echoes(db_session, user):
    """O ponto real do bug reportado: as duas transações do eco de fatura já
    existiam há meses (importadas antes desta correção), não vieram de um
    sync recém-feito — suggest_pending precisa auto-resolver esses casos
    sozinho ao ser chamado, não só o que o sync mais recente trouxe."""
    p = _bill_payable(db_session, user, Decimal("655.34"), date(2026, 5, 10))
    real_tx = Transaction(
        user_id=user.id, date=date(2026, 5, 10), description="FATURA PAGA CARTAO LUIZA",
        amount=Decimal("655.34"), type=TransactionType.EXPENSE,
    )
    echo_tx = Transaction(
        user_id=user.id, date=date(2026, 5, 10), description="Pagamento recebido",
        amount=Decimal("655.34"), type=TransactionType.EXPENSE,
    )
    db_session.add_all([real_tx, echo_tx])
    db_session.commit()

    suggestions = suggest_pending(db_session, user.id)

    assert suggestions == []
    db_session.refresh(p)
    assert p.status == PayableStatus.PAID
    assert p.transaction_id == real_tx.id
