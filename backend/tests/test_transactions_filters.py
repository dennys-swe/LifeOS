"""Filtros de GET /transactions que sustentam o drill-down do dashboard."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models.category import Category
from app.models.transaction import Transaction, TransactionType


def _cat(db, user, nome):
    c = Category(user_id=user.id, name=nome, color_hex="#84CC16")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _tx(db, user, amount, *, cat=None, dia=10, transfer=False, desc="Compra"):
    t = Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        date=date(2026, 7, dia),
        description=desc,
        amount=Decimal(str(amount)),
        type=TransactionType.EXPENSE,
        category_id=cat.id if cat else None,
        is_transfer=transfer,
    )
    db.add(t)
    db.commit()
    return t


def test_filter_by_category(client, db_session, user):
    mercado = _cat(db_session, user, "Mercado")
    outra = _cat(db_session, user, "Lazer")
    _tx(db_session, user, 100, cat=mercado, desc="No mercado")
    _tx(db_session, user, 200, cat=outra, desc="No lazer")

    data = client.get(f"/transactions?month=7&year=2026&category_id={mercado.id}").json()

    assert [t["description"] for t in data] == ["No mercado"]


def test_filter_uncategorized(client, db_session, user):
    """A linha "Sem categoria" do dashboard não tem UUID para passar no filtro."""
    mercado = _cat(db_session, user, "Mercado")
    _tx(db_session, user, 100, cat=mercado)
    _tx(db_session, user, 200, cat=None, desc="Sem categoria nenhuma")

    data = client.get("/transactions?month=7&year=2026&uncategorized=true").json()

    assert [t["description"] for t in data] == ["Sem categoria nenhuma"]


def test_exclude_transfers_matches_summary_definition(client, db_session, user):
    _tx(db_session, user, 100, desc="Gasto real")
    _tx(db_session, user, 900, transfer=True, desc="Entre contas")

    todas = client.get("/transactions?month=7&year=2026").json()
    sem_transf = client.get("/transactions?month=7&year=2026&include_transfers=false").json()

    assert len(todas) == 2
    assert [t["description"] for t in sem_transf] == ["Gasto real"]


def test_response_exposes_transfer_flag_and_external_category(client, db_session, user):
    t = _tx(db_session, user, 100, transfer=True)
    t.external_category = "Same person transfer"
    db_session.add(t)
    db_session.commit()

    item = client.get("/transactions?month=7&year=2026").json()[0]

    assert item["is_transfer"] is True
    assert item["external_category"] == "Same person transfer"


def test_pagination(client, db_session, user):
    for i in range(1, 6):
        _tx(db_session, user, 10 * i, dia=i, desc=f"tx{i}")

    pagina1 = client.get("/transactions?month=7&year=2026&limit=2").json()
    pagina2 = client.get("/transactions?month=7&year=2026&limit=2&offset=2").json()

    assert len(pagina1) == 2
    assert len(pagina2) == 2
    # Ordem é data desc, então tx5 vem primeiro e não há sobreposição entre páginas.
    assert pagina1[0]["description"] == "tx5"
    assert not {t["id"] for t in pagina1} & {t["id"] for t in pagina2}


def test_pagination_is_stable_for_same_day(client, db_session, user):
    """Sem desempate por id, transações do mesmo dia podem trocar de lugar entre
    páginas e alguma desaparecer da listagem."""
    for i in range(6):
        _tx(db_session, user, 10, dia=10, desc=f"mesmo-dia-{i}")

    vistos = []
    for offset in (0, 2, 4):
        vistos += [
            t["id"]
            for t in client.get(
                f"/transactions?month=7&year=2026&limit=2&offset={offset}"
            ).json()
        ]

    assert len(vistos) == len(set(vistos)) == 6


def test_filters_still_isolate_users(client, db_session, user, other_user):
    dele = _cat(db_session, other_user, "Dele")
    _tx(db_session, other_user, 5000, cat=dele)

    data = client.get(f"/transactions?month=7&year=2026&category_id={dele.id}").json()

    assert data == []
