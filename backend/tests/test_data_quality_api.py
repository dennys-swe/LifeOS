"""API da tela Saúde dos dados (#200): listar, prévia, aplicar, dispensar."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models.category import Category, CategoryKind
from app.models.data_quality_issue import DataQualityIssue
from app.models.transaction import ClassificationSource, Transaction, TransactionType

TODAY = date.today()


def add_tx(db, user, amount, tipo, description, *, dia=None, is_transfer=False, category=None):
    tx = Transaction(
        user_id=user.id,
        date=dia or TODAY - timedelta(days=3),
        description=description,
        amount=Decimal(str(amount)),
        type=TransactionType(tipo),
        is_transfer=is_transfer,
        category_id=category.id if category else None,
    )
    db.add(tx)
    db.flush()
    return tx


def add_category(db, user, name, kind="EXPENSE"):
    cat = Category(user_id=user.id, name=name, color_hex="#abc", kind=CategoryKind(kind))
    db.add(cat)
    db.flush()
    return cat


def run(client):
    assert client.post("/data-quality/run").status_code == 200


def only_issue(db, user, kind=None):
    q = db.query(DataQualityIssue).filter_by(user_id=user.id)
    if kind:
        q = q.filter_by(kind=kind)
    return q.one()


# --- executar e listar -----------------------------------------------------


def test_run_then_list_shows_issue_with_its_transactions(client, db_session, user):
    add_tx(db_session, user, 769.01, "INCOME", "PAGAMENTO ON LINE")
    db_session.commit()

    assert client.post("/data-quality/run").json()["new"] >= 1
    issues = client.get("/data-quality/issues").json()

    echo = next(i for i in issues if i["kind"] == "system_says_transfer")
    assert echo["severity"] == "high" and echo["status"] == "open"
    assert echo["fix_available"] is True and echo["needs_category"] is False
    assert echo["transactions"][0]["description"] == "PAGAMENTO ON LINE"
    assert Decimal(echo["transactions"][0]["amount"]) == Decimal("769.01")


def test_list_orders_by_severity(client, db_session, user):
    add_tx(db_session, user, 35, "EXPENSE", "SEM CATEGORIA")  # info
    add_tx(db_session, user, 769.01, "INCOME", "PAGAMENTO ON LINE")  # high
    db_session.commit()
    run(client)

    severities = [i["severity"] for i in client.get("/data-quality/issues").json()]

    assert severities == sorted(severities, key=["high", "warn", "info"].index)
    assert severities[0] == "high"


def test_run_twice_does_not_duplicate(client, db_session, user):
    add_tx(db_session, user, 769.01, "INCOME", "PAGAMENTO ON LINE")
    db_session.commit()

    run(client)
    second = client.post("/data-quality/run").json()

    assert second["new"] == 0 and second["unchanged"] >= 1


def test_summary_counts_open_issues_by_severity_and_kind(client, db_session, user):
    add_tx(db_session, user, 769.01, "INCOME", "PAGAMENTO ON LINE")
    add_tx(db_session, user, 35, "EXPENSE", "SEM CATEGORIA")
    db_session.commit()
    run(client)

    body = client.get("/data-quality/summary").json()

    assert body["open_total"] == 2
    assert body["by_severity"]["high"] == 1 and body["by_severity"]["info"] == 1
    assert body["by_kind"]["uncategorized_expense"] == 1
    assert body["last_detected_at"] is not None


def test_summary_is_empty_for_a_clean_account(client):
    body = client.get("/data-quality/summary").json()
    assert body["open_total"] == 0 and body["last_detected_at"] is None


# --- prévia e aplicar (transferência) ---------------------------------------


def test_preview_shows_changes_and_income_removed_without_touching_data(client, db_session, user):
    tx = add_tx(db_session, user, 769.01, "INCOME", "PAGAMENTO ON LINE")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "system_says_transfer")

    body = client.get(f"/data-quality/issues/{issue.id}/preview").json()

    assert [c["field"] for c in body["changes"]] == ["is_transfer"]
    assert body["changes"][0]["new"] == "true"
    assert Decimal(body["income_removed"]) == Decimal("769.01")
    assert Decimal(body["expense_removed"]) == Decimal("0")
    db_session.refresh(tx)
    assert tx.is_transfer is False  # prévia nunca grava
    assert db_session.get(DataQualityIssue, issue.id).status == "open"


def test_apply_marks_transfer_locks_it_and_resolves_the_issue(client, db_session, user):
    tx = add_tx(db_session, user, 769.01, "INCOME", "PAGAMENTO ON LINE")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "system_says_transfer")

    resp = client.post(f"/data-quality/issues/{issue.id}/apply", json={})

    assert resp.status_code == 200
    db_session.refresh(tx)
    db_session.refresh(issue)
    assert tx.is_transfer is True
    assert tx.classification_source == ClassificationSource.MANUAL_OVERRIDE
    assert issue.status == "resolved" and issue.resolved_at is not None
    assert client.get("/data-quality/issues").json() == [] or all(
        i["id"] != str(issue.id) for i in client.get("/data-quality/issues").json()
    )


def test_apply_to_a_mirror_marks_only_the_unmarked_side(client, db_session, user):
    saida = add_tx(
        db_session, user, 914.53, "EXPENSE", "Transferência enviada|Maria", is_transfer=True
    )
    entrada = add_tx(db_session, user, 914.53, "INCOME", "PIX RECEBIDO")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "unmarked_mirror")

    preview = client.get(f"/data-quality/issues/{issue.id}/preview").json()
    assert [c["transaction_id"] for c in preview["changes"]] == [str(entrada.id)]

    client.post(f"/data-quality/issues/{issue.id}/apply", json={})
    db_session.refresh(entrada)
    db_session.refresh(saida)
    assert entrada.is_transfer is True and saida.is_transfer is True
    assert saida.classification_source is None  # a que já estava certa não foi tocada


def test_apply_links_both_sides_of_a_reversal_pair(client, db_session, user):
    cat = add_category(db_session, user, "Taxas")
    saldo = add_tx(db_session, user, 456.02, "EXPENSE", "Saldo em atraso", category=cat)
    credito = add_tx(db_session, user, 456.02, "INCOME", "Crédito de atraso")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "unlinked_reversal")

    client.post(f"/data-quality/issues/{issue.id}/apply", json={})
    db_session.refresh(saldo)
    db_session.refresh(credito)

    assert saldo.is_transfer is True and credito.is_transfer is True


def test_apply_when_already_fixed_changes_nothing_and_closes_the_issue(client, db_session, user):
    tx = add_tx(db_session, user, 769.01, "INCOME", "PAGAMENTO ON LINE")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "system_says_transfer")
    tx.is_transfer = True  # corrigida por outro caminho depois da detecção
    db_session.commit()

    body = client.post(f"/data-quality/issues/{issue.id}/apply", json={}).json()

    assert body["already_fixed"] is True and body["changes"] == []
    db_session.refresh(issue)
    db_session.refresh(tx)
    assert issue.status == "resolved"
    assert tx.classification_source is None  # não sobrescreveu a decisão nova


# --- sem categoria -----------------------------------------------------------


def test_uncategorized_needs_a_category_to_apply(client, db_session, user):
    add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "uncategorized_expense")

    listed = client.get("/data-quality/issues").json()[0]
    assert listed["needs_category"] is True
    assert client.post(f"/data-quality/issues/{issue.id}/apply", json={}).status_code == 422


def test_uncategorized_apply_sets_category_and_locks_it(client, db_session, user):
    food = add_category(db_session, user, "Alimentação")
    tx = add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "uncategorized_expense")

    preview = client.get(
        f"/data-quality/issues/{issue.id}/preview", params={"category_id": str(food.id)}
    ).json()
    assert preview["changes"][0]["new"] == "Alimentação"

    resp = client.post(f"/data-quality/issues/{issue.id}/apply", json={"category_id": str(food.id)})

    assert resp.status_code == 200
    db_session.refresh(tx)
    assert tx.category_id == food.id
    assert tx.classification_source == ClassificationSource.MANUAL_OVERRIDE


def test_category_of_wrong_direction_is_rejected(client, db_session, user):
    income_cat = add_category(db_session, user, "Salário", kind="INCOME")
    add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "uncategorized_expense")

    resp = client.post(
        f"/data-quality/issues/{issue.id}/apply", json={"category_id": str(income_cat.id)}
    )

    assert resp.status_code == 422


def test_other_users_category_is_rejected(client, db_session, user, other_user):
    theirs = add_category(db_session, other_user, "Deles")
    add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "uncategorized_expense")

    resp = client.post(
        f"/data-quality/issues/{issue.id}/apply", json={"category_id": str(theirs.id)}
    )

    assert resp.status_code == 422


# --- sem correção automática, dispensar, estados ------------------------------


def test_large_income_has_no_automatic_fix_but_can_be_dismissed(client, db_session, user):
    for i in range(6):
        add_tx(
            db_session,
            user,
            120,
            "INCOME",
            f"Pix recebido UBER {i}",
            dia=TODAY - timedelta(days=10 + i),
        )
    big = add_tx(db_session, user, 3376.82, "INCOME", "Transferência Recebida|Fulano")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "large_unusual_income")

    listed = next(
        i for i in client.get("/data-quality/issues").json() if i["kind"] == "large_unusual_income"
    )
    assert listed["fix_available"] is False
    assert client.post(f"/data-quality/issues/{issue.id}/apply", json={}).status_code == 409

    assert client.post(f"/data-quality/issues/{issue.id}/dismiss").status_code == 204
    db_session.refresh(big)
    db_session.refresh(issue)
    assert issue.status == "dismissed" and big.is_transfer is False


def test_dismissed_issue_stays_dismissed_after_a_new_run(client, db_session, user):
    add_tx(db_session, user, 35, "EXPENSE", "PASTAS LTDA")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "uncategorized_expense")
    client.post(f"/data-quality/issues/{issue.id}/dismiss")

    run(client)

    db_session.refresh(issue)
    assert issue.status == "dismissed"
    assert client.get("/data-quality/issues").json() == []
    assert len(client.get("/data-quality/issues", params={"status": "dismissed"}).json()) == 1


def test_cannot_apply_or_dismiss_an_issue_twice(client, db_session, user):
    add_tx(db_session, user, 769.01, "INCOME", "PAGAMENTO ON LINE")
    db_session.commit()
    run(client)
    issue = only_issue(db_session, user, "system_says_transfer")
    client.post(f"/data-quality/issues/{issue.id}/apply", json={})

    assert client.post(f"/data-quality/issues/{issue.id}/apply", json={}).status_code == 409
    assert client.post(f"/data-quality/issues/{issue.id}/dismiss").status_code == 409


def test_invalid_filters_are_rejected(client):
    assert client.get("/data-quality/issues", params={"status": "qualquer"}).status_code == 422
    assert client.get("/data-quality/issues", params={"severity": "x"}).status_code == 422
    assert client.post("/data-quality/run", params={"days": 1}).status_code == 422


# --- isolamento -------------------------------------------------------------


def test_user_cannot_see_preview_apply_or_dismiss_another_users_issue(
    client, db_session, user, other_user
):
    add_tx(db_session, other_user, 769.01, "INCOME", "PAGAMENTO ON LINE")
    db_session.commit()
    from app.services import data_quality_actions as actions

    actions.run_now(db_session, other_user.id)
    theirs = only_issue(db_session, other_user, "system_says_transfer")

    assert client.get("/data-quality/issues").json() == []
    assert client.get(f"/data-quality/issues/{theirs.id}/preview").status_code == 404
    assert client.post(f"/data-quality/issues/{theirs.id}/apply", json={}).status_code == 404
    assert client.post(f"/data-quality/issues/{theirs.id}/dismiss").status_code == 404
    db_session.refresh(theirs)
    assert theirs.status == "open"
