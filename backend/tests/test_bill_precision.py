"""Precisão da fatura de cartão por banco (issue #20).

Roda `open_bill_service.compute_open_bill_amount` contra snapshots reais/sintéticos
das respostas da Pluggy (tests/fixtures/pluggy/) e compara com o valor real da
fatura informado no `expected.yaml`.

- Pastas versionadas (`_synthetic-*`) rodam no CI como regressão.
- Capturas do banco real do dono ficam em `tests/fixtures/pluggy/_local/` (fora
  do git) e são descobertas automaticamente quando presentes.

`status: xfail` no `expected.yaml` marca uma divergência conhecida e explicada;
o teste falha de propósito ali. Se um dia passar, aparece como XPASS — sinal de
que o gap foi fechado.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from app.services.open_bill_service import compute_open_bill_amount

_FIXTURES = Path(__file__).parent / "fixtures" / "pluggy"


def _fixture_dirs() -> list[Path]:
    roots = [_FIXTURES]
    if (_FIXTURES / "_local").is_dir():
        roots.append(_FIXTURES / "_local")
    dirs: list[Path] = []
    for root in roots:
        dirs.extend(
            d for d in sorted(root.iterdir()) if d.is_dir() and (d / "expected.yaml").is_file()
        )
    return dirs


def _cases() -> list:
    params = []
    for d in _fixture_dirs():
        spec = yaml.safe_load((d / "expected.yaml").read_text())
        for competencia, c in (spec.get("competencias") or {}).items():
            marks = (
                [pytest.mark.xfail(reason=str(c.get("motivo", "")).strip(), strict=False)]
                if c.get("status") == "xfail"
                else []
            )
            params.append(pytest.param(d, competencia, c, id=f"{d.name}::{competencia}", marks=marks))
    return params


@pytest.mark.parametrize("fixture_dir, competencia, spec", _cases())
def test_precisao_fatura_aberta(fixture_dir: Path, competencia: str, spec: dict):
    transactions = json.loads((fixture_dir / "transactions.json").read_text())
    target_due = date.fromisoformat(spec["target_due_date"])
    last_closed_due = date.fromisoformat(spec["last_closed_due_date"])

    got = compute_open_bill_amount(transactions, target_due, last_closed_due)

    real = Decimal(str(spec["fatura_real"]))
    tolerance = (real * Decimal(str(spec["tolerancia_pct"])) / Decimal("100")).quantize(
        Decimal("0.01")
    )
    delta = abs(got - real)

    assert delta <= tolerance, (
        f"{fixture_dir.name} {competencia}: calculado R$ {got}, real R$ {real} "
        f"(Δ R$ {delta}, tolerância R$ {tolerance})"
    )
