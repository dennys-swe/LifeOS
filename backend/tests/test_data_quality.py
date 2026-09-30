"""Auditoria de classificação (#199, #169).

Os casos abaixo reproduzem, com dados sintéticos, os erros achados à mão em produção em
30/09/2026: compra MERCADOLIVRE tratada como transferência, `PAGAMENTO ON LINE` contado como
renda, pares de atraso/dívida sem vínculo.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from itertools import count

from app.models.category import Category
from app.models.data_quality_issue import DataQualityIssue
from app.models.transaction import ClassificationSource, Transaction, TransactionType
from app.services import data_quality_service as dq
from app.services.data_quality_service import TxView

TODAY = date(2026, 9, 30)
_ids = count(1)


def tv(
    amount, tipo, description, *, dia=date(2026, 9, 10), transfer=False, cat=None, source=None, **kw
):
    return TxView(
        id=f"t{next(_ids)}",
        date=dia,
        amount=Decimal(str(amount)),
        type=tipo,
        is_transfer=transfer,
        description=description,
        category_id=cat,
        category_name=kw.get("category_name"),
        classification_source=source,
        external_category=kw.get("external_category"),
    )


def kinds(findings):
    return sorted(f.kind for f in findings)


# ---------------------------------------------------------------------------
# system_says_transfer
# ---------------------------------------------------------------------------


def test_payment_echo_counted_as_income_is_flagged():
    """Caso real: `PAGAMENTO ON LINE` (lado do cartão) entrava como renda."""
    tx = tv(769.01, "INCOME", "PAGAMENTO ON LINE")

    (finding,) = dq.detect_system_says_transfer([tx])

    assert finding.kind == dq.SYSTEM_SAYS_TRANSFER
    assert finding.transaction_ids == (tx.id,)
    assert finding.severity == "high"


def test_already_marked_transfer_is_not_flagged():
    assert (
        dq.detect_system_says_transfer([tv(769.01, "INCOME", "PAGAMENTO ON LINE", transfer=True)])
        == []
    )


def test_manual_override_is_never_questioned():
    tx = tv(769.01, "INCOME", "PAGAMENTO ON LINE", source=ClassificationSource.MANUAL_OVERRIDE)
    assert dq.detect_system_says_transfer([tx]) == []


def test_ordinary_income_is_not_flagged():
    assert dq.detect_system_says_transfer([tv(150, "INCOME", "Pix recebido UBER DO BRASIL")]) == []


def test_self_transfer_income_uses_the_user_name():
    tx = tv(580, "INCOME", "Transferência Recebida|DENNYS ALVES SILVA")

    assert dq.detect_system_says_transfer([tx], "Dennys Alves Silva")
    assert dq.detect_system_says_transfer([tx], "Outra Pessoa") == []


def test_user_rule_disagreeing_with_pluggy_category_is_not_flagged():
    """MERCADOLIVRE vem como `Investments`; a regra do usuário o torna gasto. Não é erro."""
    tx = tv(38.24, "EXPENSE", "MERCADOLIVRE MERCADOL VARGEM", external_category="Investments")
    assert dq.detect_system_says_transfer([tx]) == []


# ---------------------------------------------------------------------------
# unlinked_reversal
# ---------------------------------------------------------------------------


def test_late_balance_and_credit_pair_is_flagged():
    saldo = tv(456.02, "EXPENSE", "Saldo em atraso")
    credito = tv(456.02, "INCOME", "Crédito de atraso")

    (finding,) = dq.detect_unlinked_reversals([saldo, credito])

    assert finding.kind == dq.UNLINKED_REVERSAL
    assert set(finding.transaction_ids) == {saldo.id, credito.id}


def test_reversal_pair_already_linked_is_not_flagged():
    saldo = tv(456.02, "EXPENSE", "Saldo em atraso", transfer=True)
    credito = tv(456.02, "INCOME", "Crédito de atraso", transfer=True)
    assert dq.detect_unlinked_reversals([saldo, credito]) == []


def test_reversal_credit_without_matching_expense_is_not_flagged():
    assert dq.detect_unlinked_reversals([tv(456.02, "INCOME", "Crédito de atraso")]) == []


def test_installment_credit_pairs_with_the_original_purchase():
    compra = tv(468.34, "EXPENSE", "Mercadolivre*Mercadol", dia=date(2026, 8, 5))
    credito = tv(468.34, "INCOME", "Crédito de parcelamento de compra", dia=date(2026, 8, 5))
    assert len(dq.detect_unlinked_reversals([compra, credito])) == 1


# ---------------------------------------------------------------------------
# unmarked_mirror
# ---------------------------------------------------------------------------


def test_mirror_with_one_side_unmarked_is_flagged():
    saida = tv(
        914.53, "EXPENSE", "Transferência enviada|Dennys", transfer=True, dia=date(2026, 8, 12)
    )
    entrada = tv(914.53, "INCOME", "PAGAMENTO ON LINE", dia=date(2026, 8, 12))

    (finding,) = dq.detect_unmarked_mirrors([saida, entrada])

    assert finding.kind == dq.UNMARKED_MIRROR
    assert finding.detail["expense_is_transfer"] is True
    assert finding.detail["income_is_transfer"] is False


def test_mirror_with_both_sides_marked_is_fine():
    saida = tv(100, "EXPENSE", "Pix enviado", transfer=True)
    entrada = tv(100, "INCOME", "Pix recebido", transfer=True)
    assert dq.detect_unmarked_mirrors([saida, entrada]) == []


def test_mirror_respects_the_two_day_window():
    saida = tv(100, "EXPENSE", "Pix enviado", dia=date(2026, 9, 10))
    perto = tv(100, "INCOME", "Pix recebido", dia=date(2026, 9, 12))
    longe = tv(100, "INCOME", "Pix recebido", dia=date(2026, 9, 13))

    assert len(dq.detect_unmarked_mirrors([saida, perto])) == 1
    assert dq.detect_unmarked_mirrors([saida, longe]) == []


def test_mirror_needs_a_transfer_like_hint_in_the_description():
    """Mesmo valor e dia sem nada que lembre movimentação entre contas é coincidência."""
    compra = tv(100, "EXPENSE", "MERCADINHO SAO LUIZ")
    venda = tv(100, "INCOME", "VENDA BALCAO")
    assert dq.detect_unmarked_mirrors([compra, venda]) == []


def test_mirror_ignores_small_amounts():
    assert (
        dq.detect_unmarked_mirrors(
            [tv(5, "EXPENSE", "Pix enviado"), tv(5, "INCOME", "Pix recebido")]
        )
        == []
    )


def test_mirror_skips_pairs_the_user_decided_manually():
    saida = tv(100, "EXPENSE", "Pix enviado")
    entrada = tv(100, "INCOME", "Pix recebido", source=ClassificationSource.MANUAL_OVERRIDE)
    assert dq.detect_unmarked_mirrors([saida, entrada]) == []


def test_each_income_pairs_with_one_expense_only():
    saidas = [tv(100, "EXPENSE", "Pix enviado"), tv(100, "EXPENSE", "Pix enviado")]
    entrada = tv(100, "INCOME", "Pix recebido")
    assert len(dq.detect_unmarked_mirrors([*saidas, entrada])) == 1


# ---------------------------------------------------------------------------
# large_unusual_income, uncategorized, detect_all
# ---------------------------------------------------------------------------


def test_large_income_far_above_the_median_is_flagged():
    base = [tv(120, "INCOME", f"Pix recebido UBER {i}") for i in range(6)]
    big = tv(2500, "INCOME", "Transferência Recebida|FULANO", category_name="Outras receitas")

    findings = dq.detect_large_unusual_income([*base, big])

    assert [f.transaction_ids for f in findings] == [(big.id,)]


def test_large_income_with_known_income_category_is_not_flagged():
    base = [tv(120, "INCOME", f"x{i}") for i in range(6)]
    salary = tv(2500, "INCOME", "SALARIO", category_name="Salário")
    assert dq.detect_large_unusual_income([*base, salary]) == []


def test_large_income_needs_enough_history():
    assert dq.detect_large_unusual_income([tv(2500, "INCOME", "X"), tv(100, "INCOME", "Y")]) == []


def test_uncategorized_expense_is_flagged_but_transfers_and_income_are_not():
    sem = tv(35, "EXPENSE", "PASTAS LTDA CRATO")
    com = tv(35, "EXPENSE", "MERCADINHO", cat="c1")
    transf = tv(35, "EXPENSE", "Pix enviado", transfer=True)
    renda = tv(35, "INCOME", "Pix recebido")

    findings = dq.detect_uncategorized_expenses([sem, com, transf, renda])

    assert [f.transaction_ids for f in findings] == [(sem.id,)]


def test_detect_all_does_not_report_a_reversal_pair_twice():
    saldo = tv(456.02, "EXPENSE", "Saldo em atraso", cat="taxas")
    credito = tv(456.02, "INCOME", "Crédito de atraso")

    # sem `unmarked_mirror`: o par já foi reportado como `unlinked_reversal`
    assert kinds(dq.detect_all([saldo, credito])) == [dq.SYSTEM_SAYS_TRANSFER, dq.UNLINKED_REVERSAL]


def test_detect_all_on_a_clean_history_reports_nothing():
    txs = [
        tv(35, "EXPENSE", "MERCADINHO", cat="c1"),
        tv(120, "INCOME", "Pix recebido UBER", category_name="Renda extra"),
    ]
    assert dq.detect_all(txs) == []


def test_fingerprint_is_stable_and_order_independent():
    a = dq.Finding(dq.UNMARKED_MIRROR, ("b", "a"))
    b = dq.Finding(dq.UNMARKED_MIRROR, ("a", "b"))
    c = dq.Finding(dq.UNLINKED_REVERSAL, ("a", "b"))
    assert a.fingerprint == b.fingerprint != c.fingerprint


# ---------------------------------------------------------------------------
# resíduo (#169)
# ---------------------------------------------------------------------------


def test_residual_report_measures_uncategorized_share_and_ranks_descriptions():
    txs = [
        tv(100, "EXPENSE", "PASTAS LTDA 123", cat=None),
        tv(50, "EXPENSE", "PASTAS LTDA 456", cat=None),
        tv(10, "EXPENSE", "OUTRO", cat=None),
        tv(
            840,
            "EXPENSE",
            "MERCADINHO",
            cat="c1",
            source="user_rule",
            external_category="Groceries",
        ),
        tv(999, "EXPENSE", "Pix enviado", transfer=True),  # transferência não conta
        tv(500, "INCOME", "Pix recebido"),  # renda não conta
    ]

    r = dq.build_residual_report(txs)

    assert (r.expenses_count, r.uncategorized_count) == (4, 3)
    assert r.uncategorized_amount == Decimal("160")
    assert r.uncategorized_pct_count == 75.0
    assert r.uncategorized_pct_amount == 16.0
    assert r.top_uncategorized[0] == ("PASTAS LTDA", 2, Decimal("150"))
    assert r.without_classification_source == 3
    assert r.without_external_category == 3


def test_residual_report_on_empty_history_does_not_divide_by_zero():
    r = dq.build_residual_report([])
    assert (r.expenses_count, r.uncategorized_pct_count, r.uncategorized_pct_amount) == (
        0,
        0.0,
        0.0,
    )


# ---------------------------------------------------------------------------
# carga do banco e persistência
# ---------------------------------------------------------------------------


def add_tx(
    db, user, amount, tipo, description, *, dia, is_transfer=False, category=None, source=None
):
    tx = Transaction(
        user_id=user.id,
        date=dia,
        description=description,
        amount=Decimal(str(amount)),
        type=TransactionType(tipo),
        is_transfer=is_transfer,
        category_id=category.id if category else None,
        classification_source=source,
    )
    db.add(tx)
    db.flush()
    return tx


def test_run_audit_only_looks_at_the_window_and_never_at_the_future(db_session, user):
    add_tx(db_session, user, 35, "EXPENSE", "NA JANELA", dia=TODAY - timedelta(days=5))
    add_tx(db_session, user, 35, "EXPENSE", "MUITO ANTIGA", dia=TODAY - timedelta(days=400))
    add_tx(db_session, user, 35, "EXPENSE", "PARCELA FUTURA", dia=TODAY + timedelta(days=30))

    result = dq.run_audit(db_session, user.id, days=120, today=TODAY)

    assert [f.detail["description"] for f in result.findings] == ["NA JANELA"]
    assert len(result.audited_ids) == 1


def test_run_audit_reads_the_user_name_for_self_transfers(db_session, user):
    user.full_name = "Dennys Alves"
    add_tx(db_session, user, 580, "INCOME", "Transferência Recebida|DENNYS ALVES SILVA", dia=TODAY)

    result = dq.run_audit(db_session, user.id, today=TODAY)

    assert dq.SYSTEM_SAYS_TRANSFER in kinds(result.findings)


def test_persist_is_idempotent(db_session, user):
    add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA", dia=TODAY)
    result = dq.run_audit(db_session, user.id, today=TODAY)

    first = dq.persist_findings(db_session, user.id, result.findings, result.audited_ids)
    second = dq.persist_findings(db_session, user.id, result.findings, result.audited_ids)

    assert first == {"new": 1, "unchanged": 0, "reopened": 0, "resolved": 0}
    assert second == {"new": 0, "unchanged": 1, "reopened": 0, "resolved": 0}
    assert db_session.query(DataQualityIssue).count() == 1


def test_issue_is_resolved_when_the_transaction_gets_fixed_and_reopened_if_it_returns(
    db_session, user
):
    cat = Category(user_id=user.id, name="Alimentação", color_hex="#fff", kind="EXPENSE")
    db_session.add(cat)
    tx = add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA", dia=TODAY)
    result = dq.run_audit(db_session, user.id, today=TODAY)
    dq.persist_findings(db_session, user.id, result.findings, result.audited_ids)

    tx.category_id = cat.id  # usuário corrigiu
    fixed = dq.run_audit(db_session, user.id, today=TODAY)
    stats = dq.persist_findings(db_session, user.id, fixed.findings, fixed.audited_ids)
    issue = db_session.query(DataQualityIssue).one()
    assert stats["resolved"] == 1 and issue.status == "resolved" and issue.resolved_at is not None

    tx.category_id = None  # voltou ao problema
    again = dq.run_audit(db_session, user.id, today=TODAY)
    stats = dq.persist_findings(db_session, user.id, again.findings, again.audited_ids)
    assert stats["reopened"] == 1
    assert db_session.query(DataQualityIssue).one().status == "open"


def test_dismissed_issue_is_never_reopened_or_resolved(db_session, user):
    add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA", dia=TODAY)
    result = dq.run_audit(db_session, user.id, today=TODAY)
    dq.persist_findings(db_session, user.id, result.findings, result.audited_ids)
    db_session.query(DataQualityIssue).one().status = "dismissed"

    stats = dq.persist_findings(db_session, user.id, result.findings, result.audited_ids)
    empty = dq.persist_findings(db_session, user.id, [], result.audited_ids)

    assert stats["unchanged"] == 1 and empty["resolved"] == 0
    assert db_session.query(DataQualityIssue).one().status == "dismissed"


def test_open_issue_outside_the_audited_window_is_not_auto_resolved(db_session, user):
    add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA", dia=TODAY)
    result = dq.run_audit(db_session, user.id, today=TODAY)
    dq.persist_findings(db_session, user.id, result.findings, result.audited_ids)

    stats = dq.persist_findings(db_session, user.id, [], frozenset())  # janela não cobre a linha

    assert stats["resolved"] == 0
    assert db_session.query(DataQualityIssue).one().status == "open"


def test_audit_is_isolated_between_users(db_session, user, other_user):
    add_tx(db_session, other_user, 35, "EXPENSE", "DO OUTRO", dia=TODAY)
    add_tx(db_session, user, 50, "EXPENSE", "MEU", dia=TODAY)

    mine = dq.run_audit(db_session, user.id, today=TODAY)
    dq.persist_findings(db_session, user.id, mine.findings, mine.audited_ids)

    assert [f.detail["description"] for f in mine.findings] == ["MEU"]
    assert db_session.query(DataQualityIssue).filter_by(user_id=other_user.id).count() == 0
