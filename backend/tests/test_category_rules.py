import io
import uuid

from app.models.category import Category
from app.schemas.category_rule import CategoryRuleCreate
from app.services.category_rule_service import build_keyword_map, create_rule, list_rules


def _make_category(db_session, name="Mercado", color="#00FF00"):
    cat = Category(id=uuid.uuid4(), name=name, color_hex=color)
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


def test_create_rule_normalizes_keyword(db_session):
    cat = _make_category(db_session)
    rule = create_rule(db_session, CategoryRuleCreate(keyword="supermercado", category_id=cat.id))
    assert rule.keyword == "SUPERMERCADO"


def test_create_rule_strips_whitespace(db_session):
    cat = _make_category(db_session)
    rule = create_rule(db_session, CategoryRuleCreate(keyword="  padaria  ", category_id=cat.id))
    assert rule.keyword == "PADARIA"


def test_build_keyword_map_correct_dict(db_session):
    cat = _make_category(db_session, "Alimentação")
    create_rule(db_session, CategoryRuleCreate(keyword="restaurante", category_id=cat.id))
    kmap = build_keyword_map(db_session)
    assert "RESTAURANTE" in kmap
    assert kmap["RESTAURANTE"] == str(cat.id)


def test_build_keyword_map_respects_priority(db_session):
    cat_low = _make_category(db_session, "Low", "#111111")
    cat_high = _make_category(db_session, "High", "#222222")
    create_rule(db_session, CategoryRuleCreate(keyword="comum", category_id=cat_low.id, priority=0))
    create_rule(db_session, CategoryRuleCreate(keyword="comum", category_id=cat_high.id, priority=10))
    kmap = build_keyword_map(db_session)
    # Higher priority wins — dict insertion order preserves ORDER BY priority DESC
    assert kmap["COMUM"] == str(cat_high.id)


def test_create_rule_via_api(client, db_session):
    cat = _make_category(db_session, "Transporte")
    response = client.post("/category-rules", json={
        "keyword": "uber",
        "category_id": str(cat.id),
        "priority": 0,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["keyword"] == "UBER"
    assert data["id"]


def test_list_rules(client, db_session):
    cat = _make_category(db_session)
    client.post("/category-rules", json={"keyword": "ifood", "category_id": str(cat.id)})
    client.post("/category-rules", json={"keyword": "rappi", "category_id": str(cat.id)})
    response = client.get("/category-rules")
    assert response.status_code == 200
    keywords = [r["keyword"] for r in response.json()]
    assert "IFOOD" in keywords
    assert "RAPPI" in keywords


def test_delete_rule(client, db_session):
    cat = _make_category(db_session)
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


def test_upload_uses_db_rules(client, db_session):
    cat = _make_category(db_session, "Supermercado")
    create_rule(db_session, CategoryRuleCreate(keyword="pao de acucar", category_id=cat.id))

    csv_content = "Data,Descricao,Valor\n10/05/2026,Pao de Acucar Compra,-150.00\n"
    csv_bytes = csv_content.encode()

    response = client.post(
        "/transactions/upload",
        files={"file": ("extrato.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["category_id"] == str(cat.id)
