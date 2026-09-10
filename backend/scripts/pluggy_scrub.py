"""Anonimiza um snapshot da Pluggy antes de (eventualmente) versionar.

    cd backend
    python -m scripts.pluggy_scrub tests/fixtures/pluggy/_local/nubank
    python -m scripts.pluggy_scrub tests/fixtures/pluggy/_local/nubank --dry-run

O que é trocado:
  - todo `id` / `billId` / `accountId` / `itemId` → id fake determinístico
  - nome de contraparte em PIX/TED/DOC/transferência → "PESSOA NN"

O que é preservado (a lógica de fatura depende):
  - amount, amountInAccountCurrency, date, type, status, category, categoryId
  - creditCardMetadata (billForecastDate, installmentNumber/totalInstallments,
    cardNumber, payeeMCC), dueDate, totalAmount

Revise o resultado à mão antes de mover para fora de `_local/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_ID_KEYS = {"id", "billId", "accountId", "itemId", "bill_id", "account_id", "item_id"}

# "PIX ENVIADO FULANO DE TAL", "TED RECEBIDA MARIA", "TRANSFERENCIA PARA JOAO"
_COUNTERPARTY = re.compile(
    r"\b(PIX|TED|DOC|TRANSFERENCIA|TRANSFERÊNCIA)\b[\s\-]*"
    r"(ENVIAD[OA]|RECEBID[OA]|PARA|DE)?[\s\-]*(.+)",
    re.IGNORECASE,
)


class Scrubber:
    def __init__(self) -> None:
        self._ids: dict[str, str] = {}
        self._people: dict[str, str] = {}
        self.changes = 0

    def fake_id(self, value: str) -> str:
        if value not in self._ids:
            digest = hashlib.sha1(value.encode()).hexdigest()[:12]
            self._ids[value] = f"anon-{digest}"
            self.changes += 1
        return self._ids[value]

    def scrub_description(self, text: str) -> str:
        m = _COUNTERPARTY.match(text.strip())
        if not m or not m.group(3):
            return text
        person = m.group(3).strip()
        if person not in self._people:
            self._people[person] = f"PESSOA {len(self._people) + 1:02d}"
            self.changes += 1
        prefix = " ".join(p for p in (m.group(1), m.group(2)) if p)
        return f"{prefix} {self._people[person]}".strip()

    def walk(self, node):
        if isinstance(node, dict):
            return {
                k: (
                    self.fake_id(v)
                    if k in _ID_KEYS and isinstance(v, str) and v
                    else self.scrub_description(v)
                    if k in ("description", "descriptionRaw") and isinstance(v, str)
                    else self.walk(v)
                )
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [self.walk(item) for item in node]
        return node


def scrub_dir(path: Path, dry_run: bool) -> None:
    scrubber = Scrubber()
    for name in ("transactions.json", "bills.json"):
        f = path / name
        if not f.is_file():
            continue
        cleaned = scrubber.walk(json.loads(f.read_text()))
        if not dry_run:
            f.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False))
    verb = "trocaria" if dry_run else "trocou"
    print(f"{path.name}: {verb} {scrubber.changes} valores "
          f"({len(scrubber._ids)} ids, {len(scrubber._people)} nomes).")
    if scrubber._people:
        print("  nomes → " + ", ".join(f"{k!r}→{v}" for k, v in scrubber._people.items()))
    print("  Revise transactions.json à mão: valores monetários NÃO são alterados.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not (args.path / "transactions.json").is_file():
        sys.exit(f"{args.path}: não parece uma pasta de fixture (sem transactions.json)")
    scrub_dir(args.path, args.dry_run)
