"""Grava um snapshot das respostas cruas da API da Pluggy para um item.

    cd backend
    python -m scripts.pluggy_capture <item_id> --slug nubank

Para cada conta de cartão do item, cria
`tests/fixtures/pluggy/_local/<slug>[-N]/` com:

    transactions.json   # results achatados de transactions_list (todas as páginas)
    bills.json          # results de bills_list
    capture.yaml        # metadados
    expected.yaml       # template — preencher com os valores reais de fatura

Só lê a API (não toca no banco). Depois: rodar `scripts.pluggy_scrub` e
preencher o `expected.yaml`. Ver tests/fixtures/pluggy/README.md.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pluggy_sdk

from app.services.pluggy_client import get_api_client

_OUT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "pluggy" / "_local"

_EXPECTED_TEMPLATE = """\
card: "{card}"
competencias:
  # Preencher com os valores reais de fatura confirmados. Exemplo:
  # "2026-08":
  #   target_due_date: "2026-08-08"
  #   last_closed_due_date: "2026-07-08"
  #   fatura_real: 0.00
  #   tolerancia_pct: 0.5
  #   status: exato          # exato | estimado | xfail
"""


def _all_transactions(tx_api: pluggy_sdk.TransactionApi, account_id: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        raw = tx_api.transactions_list_without_preload_content(
            account_id=account_id, page=page, page_size=500
        )
        data = json.loads(raw.data)
        results = data.get("results") or []
        out.extend(results)
        if not results or page >= (data.get("totalPages") or 1):
            break
        page += 1
    return out


def _bills(bill_api: pluggy_sdk.BillApi, account_id: str) -> list[dict]:
    try:
        raw = bill_api.bills_list_without_preload_content(account_id=account_id)
        return json.loads(raw.data).get("results") or []
    except Exception as exc:  # noqa: BLE001
        print(f"  bills indisponíveis: {type(exc).__name__}: {exc}")
        return []


def capture(item_id: str, slug: str) -> None:
    with get_api_client() as ac:
        account_api = pluggy_sdk.AccountApi(ac)
        tx_api = pluggy_sdk.TransactionApi(ac)
        bill_api = pluggy_sdk.BillApi(ac)

        accounts = account_api.accounts_list(item_id=item_id).results or []
        credit = [a for a in accounts if getattr(a, "type", None) == "CREDIT"]
        if not credit:
            print(f"item {item_id} não tem conta de cartão (type=CREDIT).")
            return

        for i, acct in enumerate(credit):
            name = (getattr(acct, "marketing_name", None) or getattr(acct, "name", None) or slug)
            out_dir = _OUT_ROOT / (slug if len(credit) == 1 else f"{slug}-{i + 1}")
            out_dir.mkdir(parents=True, exist_ok=True)

            transactions = _all_transactions(tx_api, acct.id)
            bills = _bills(bill_api, acct.id)

            (out_dir / "transactions.json").write_text(json.dumps(transactions, indent=2, default=str))
            (out_dir / "bills.json").write_text(json.dumps(bills, indent=2, default=str))
            (out_dir / "capture.yaml").write_text(
                f'card: "{name}"\n'
                f"source: real\n"
                f'captured_at: "{date.today().isoformat()}"\n'
                f'pluggy_sdk: "{pluggy_sdk.__version__}"\n'
                f"item_id_hint: (anonimizar antes de versionar)\n"
            )
            expected = out_dir / "expected.yaml"
            if not expected.exists():
                expected.write_text(_EXPECTED_TEMPLATE.format(card=name))

            print(
                f"{out_dir.relative_to(_OUT_ROOT.parents[2])}: "
                f"{len(transactions)} transações, {len(bills)} faturas"
            )

    print("\nPróximo: python -m scripts.pluggy_scrub <pasta>  e preencher expected.yaml")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("item_id")
    parser.add_argument("--slug", required=True, help="prefixo da pasta (ex: nubank)")
    args = parser.parse_args()
    capture(args.item_id, args.slug)
