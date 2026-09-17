"""Achado na revisão do PR da issue #8: POST /transactions aceita `source`
do cliente, e a nova constraint uq_transactions_user_id_source (issue #8)
faz uma duplicata virar 500 cru em vez de um erro de validação."""

from __future__ import annotations


def _payload(source=None):
    return {
        "date": "2026-07-10",
        "description": "Lançamento manual",
        "amount": "10.00",
        "type": "EXPENSE",
        "source": source,
    }


def test_duplicate_source_returns_400_not_500(client):
    first = client.post("/transactions", json=_payload("meu-source"))
    assert first.status_code == 201

    second = client.post("/transactions", json=_payload("meu-source"))
    assert second.status_code == 400


def test_multiple_manual_transactions_without_source_are_allowed(client):
    r1 = client.post("/transactions", json=_payload(None))
    r2 = client.post("/transactions", json=_payload(None))
    assert r1.status_code == 201
    assert r2.status_code == 201
