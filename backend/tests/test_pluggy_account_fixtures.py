"""Semântica de saldo e limite da Pluggy (issue #196).

Trava o que foi confirmado contra a API real em 30/09/2026 (Inter, Itaú,
Nubank; ver `tests/fixtures/pluggy/README.md`), usando as fixtures sintéticas.
É a base das features de snapshot de saldo (#197) e de limite consolidado
(#204): se a Pluggy mudar o formato, estes testes são o primeiro aviso.
"""

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent / "fixtures" / "pluggy"
_FIXTURES = sorted(_ROOT.glob("_synthetic-*/accounts.json"))


def _accounts(path: Path, kind: str) -> list[dict]:
    return [a for a in json.loads(path.read_text()) if a["type"] == kind]


def test_fixtures_present():
    assert len(_FIXTURES) == 3


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.parent.name)
def test_credit_balance_is_used_limit(path):
    """`balance` de cartão é limite consumido: limite - disponível, em todos os bancos testados."""
    for acct in _accounts(path, "CREDIT"):
        data = acct["creditData"]
        used = round(data["creditLimit"] - data["availableCreditLimit"], 2)
        assert acct["balance"] == pytest.approx(used, abs=0.01)


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.parent.name)
def test_close_date_is_not_provided_by_accounts(path):
    """`balanceCloseDate` veio nulo nos 4 cartões reais: o fechamento não vem de `accounts`."""
    for acct in _accounts(path, "CREDIT"):
        assert acct["creditData"]["balanceCloseDate"] is None


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.parent.name)
def test_bank_balance_matches_closing_balance(path):
    for acct in _accounts(path, "BANK"):
        assert acct["balance"] == acct["bankData"]["closingBalance"]


def test_disaggregated_limits_repeat_per_card_and_must_not_be_summed():
    """Cartões da mesma conta compartilham o limite: `disaggregatedCreditLimits` repete
    o mesmo valor por final de cartão. Somar isso inflaria o limite; vale o `creditLimit`
    de topo, somado por conta (não por cartão)."""
    shared = [
        a
        for path in _FIXTURES
        for a in _accounts(path, "CREDIT")
        if len(a["creditData"]["additionalCards"]) >= 1
    ]
    assert shared, "a fixture precisa ter ao menos uma conta com mais de um cartão"
    for acct in shared:
        data = acct["creditData"]
        total_lines = [
            line
            for line in data["disaggregatedCreditLimits"]
            if line["creditLineLimitType"] == "LIMITE_CREDITO_TOTAL"
        ]
        assert sum(line["limitAmount"] for line in total_lines) > data["creditLimit"]
        assert {line["limitAmount"] for line in total_lines} == {data["creditLimit"]}
