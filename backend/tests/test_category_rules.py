import uuid

from app.models.category import Category
from app.schemas.category_rule import CategoryRuleCreate
from app.services.category_rule_service import (
    apply_rule_to_existing,
    build_keyword_map,
    create_rule,
    list_rules,
)


def _make_category(db_session, user, name="Mercado", color="#00FF00"):
    cat = Category(id=uuid.uuid4(), user_id=user.id, name=name, color_hex=color)
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


def test_create_rule_normalizes_keyword(db_session, user):
    cat = _make_category(db_session, user)
    rule = create_rule(db_session, user.id, CategoryRuleCreate(keyword="supermercado", category_id=cat.id))
    assert rule.keyword == "SUPERMERCADO"
    assert rule.user_id == user.id


def test_create_rule_strips_whitespace(db_session, user):
    cat = _make_category(db_session, user)
    rule = create_rule(db_session, user.id, CategoryRuleCreate(keyword="  padaria  ", category_id=cat.id))
    assert rule.keyword == "PADARIA"


def test_build_keyword_map_correct_dict(db_session, user):
    cat = _make_category(db_session, user, "Alimentação")
    create_rule(db_session, user.id, CategoryRuleCreate(keyword="restaurante", category_id=cat.id))
    kmap = build_keyword_map(db_session, user.id)
    assert "RESTAURANTE" in kmap
    assert kmap["RESTAURANTE"] == str(cat.id)


def test_build_keyword_map_respects_priority(db_session, user):
    cat_low = _make_category(db_session, user, "Low", "#111111")
    cat_high = _make_category(db_session, user, "High", "#222222")
    create_rule(db_session, user.id, CategoryRuleCreate(keyword="comum", category_id=cat_low.id, priority=0))
    create_rule(db_session, user.id, CategoryRuleCreate(keyword="comum", category_id=cat_high.id, priority=10))
    kmap = build_keyword_map(db_session, user.id)
    # Higher priority wins — dict insertion order preserves ORDER BY priority DESC
    assert kmap["COMUM"] == str(cat_high.id)


def test_build_keyword_map_excludes_other_users(db_session, user, other_user):
    cat = _make_category(db_session, other_user, "Alimentação")
    create_rule(db_session, other_user.id, CategoryRuleCreate(keyword="restaurante", category_id=cat.id))
    kmap = build_keyword_map(db_session, user.id)
    assert kmap == {}


def test_create_rule_via_api(client, db_session, user):
    cat = _make_category(db_session, user, "Transporte")
    response = client.post("/category-rules", json={
        "keyword": "uber",
        "category_id": str(cat.id),
        "priority": 0,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["keyword"] == "UBER"
    assert data["id"]


def test_list_rules(client, db_session, user):
    cat = _make_category(db_session, user)
    client.post("/category-rules", json={"keyword": "ifood", "category_id": str(cat.id)})
    client.post("/category-rules", json={"keyword": "rappi", "category_id": str(cat.id)})
    response = client.get("/category-rules")
    assert response.status_code == 200
    keywords = [r["keyword"] for r in response.json()]
    assert "IFOOD" in keywords
    assert "RAPPI" in keywords


def test_delete_rule(client, db_session, user):
    cat = _make_category(db_session, user)
    create_resp = client.post("/category-rules", json={"keyword": "farmacia", "category_id": str(cat.id)})
    rule_id = create_resp.json()["id"]
    del_resp = client.delete(f"/category-rules/{rule_id}")
    assert del_resp.status_code == 204
    list_resp = client.get("/category-rules")
    ids = [r["id"] for r in list_resp.json()]
    assert rule_id not in ids


def test_delete_rule_not_found(client):
    response = client.delete("/category-rules/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# Cobertura de categorização automática por keyword foi movida para
# test_bank_accounts.py::TestSyncAccountService::test_sync_categorizes_by_keyword_rule
# (import de extrato manual foi removido em favor de sincronização via Pluggy).


def _tx(db_session, user, description, tx_type=None, category_id=None):
    from datetime import date
    from decimal import Decimal

    from app.models.transaction import Transaction, TransactionType

    tx = Transaction(
        user_id=user.id,
        date=date(2026, 8, 1),
        description=description,
        amount=Decimal("12.50"),
        type=tx_type or TransactionType.EXPENSE,
        category_id=category_id,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


def _cat(db_session, user, name, kind=None):
    from app.models.category import Category, CategoryKind

    cat = Category(
        user_id=user.id, name=name, color_hex="#84CC16", kind=kind or CategoryKind.EXPENSE
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


def test_new_rule_reclassifies_existing_transactions(client, db_session, user):
    """O sync pula transação já importada, então sem aplicar ao histórico a
    regra não mudava nada na tela e parecia quebrada."""
    transporte = _cat(db_session, user, "Transporte")
    mercado = _cat(db_session, user, "Mercado")
    t1 = _tx(db_session, user, "CONVENIENCIA POSTO CAS CRATO", category_id=transporte.id)
    t2 = _tx(db_session, user, "Compra débito CONVENIENCIA POSTO CAS", category_id=transporte.id)
    outra = _tx(db_session, user, "PAO NOBRE", category_id=transporte.id)

    response = client.post(
        "/category-rules",
        json={"keyword": "CONVENIENCIA", "category_id": str(mercado.id), "priority": 0},
    )

    assert response.status_code == 201
    assert response.json()["applied_count"] == 2
    for t in (t1, t2):
        db_session.refresh(t)
        assert t.category_id == mercado.id
    db_session.refresh(outra)
    assert outra.category_id == transporte.id


def test_rule_matches_regardless_of_case(db_session, user):
    """As descrições vêm em caixas diferentes do mesmo estabelecimento."""
    mercado = _cat(db_session, user, "Mercado")
    minuscula = _tx(db_session, user, "Conveniencia Posto Cas")

    rule = create_rule(
        db_session, user.id,
        CategoryRuleCreate(keyword="conveniencia", category_id=mercado.id, priority=0),
    )
    applied = apply_rule_to_existing(db_session, user.id, rule)

    assert applied == 1
    db_session.refresh(minuscula)
    assert minuscula.category_id == mercado.id


def test_rule_also_fills_uncategorized(db_session, user):
    """`!=` em SQL não pega NULL — sem cuidado, o sem categoria ficaria de fora."""
    mercado = _cat(db_session, user, "Mercado")
    sem_categoria = _tx(db_session, user, "CONVENIENCIA POSTO")

    rule = create_rule(
        db_session, user.id,
        CategoryRuleCreate(keyword="CONVENIENCIA", category_id=mercado.id, priority=0),
    )

    assert apply_rule_to_existing(db_session, user.id, rule) == 1
    db_session.refresh(sem_categoria)
    assert sem_categoria.category_id == mercado.id


def test_income_rule_does_not_touch_expenses(db_session, user):
    """Regra `UBER -> Renda extra` não pode marcar uma corrida paga como receita."""
    from app.models.category import CategoryKind
    from app.models.transaction import TransactionType

    renda = _cat(db_session, user, "Renda extra", kind=CategoryKind.INCOME)
    recebido = _tx(db_session, user, "Pix recebido UBER DO BRASIL", tx_type=TransactionType.INCOME)
    pago = _tx(db_session, user, "UBER DO BRASIL corrida", tx_type=TransactionType.EXPENSE)

    rule = create_rule(
        db_session, user.id,
        CategoryRuleCreate(keyword="UBER DO BRASIL", category_id=renda.id, priority=10),
    )

    assert apply_rule_to_existing(db_session, user.id, rule) == 1
    db_session.refresh(recebido)
    db_session.refresh(pago)
    assert recebido.category_id == renda.id
    assert pago.category_id is None


def test_rule_does_not_touch_other_users_transactions(db_session, user, other_user):
    mercado = _cat(db_session, user, "Mercado")
    alheia = _tx(db_session, other_user, "CONVENIENCIA POSTO CAS")

    rule = create_rule(
        db_session, user.id,
        CategoryRuleCreate(keyword="CONVENIENCIA", category_id=mercado.id, priority=0),
    )

    assert apply_rule_to_existing(db_session, user.id, rule) == 0
    db_session.refresh(alheia)
    assert alheia.category_id is None
