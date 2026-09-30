"""Auditoria de classificação: detecta suspeitas e mede o resíduo sem categoria (#199, #169).

Só **sinaliza**: nenhum detector altera transação. Os erros que motivaram isto foram achados à
mão em 30/09/2026 (compra MERCADOLIVRE marcada como transferência, `PAGAMENTO ON LINE` contado
como renda, pares de atraso sem vínculo). Aqui viram regras versionadas e testadas.

Os detectores (`detect_*`) são funções puras sobre `TxView`, sem acesso a banco. `run_audit`
carrega os dados; `persist_findings` grava em `data_quality_issues` de forma idempotente.

Conservador de propósito: cada regra prefere deixar passar a acusar à toa, porque alerta
falso ensina o usuário a ignorar a tela. O que o usuário corrigiu à mão
(`classification_source = manual_override`) nunca é questionado.
"""

from __future__ import annotations

import hashlib
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.data_quality_issue import DataQualityIssue
from app.models.transaction import ClassificationSource, Transaction
from app.models.user import User
from app.services.transaction_signals import is_transfer

# --- tipos de achado -------------------------------------------------------
SYSTEM_SAYS_TRANSFER = "system_says_transfer"
UNMARKED_MIRROR = "unmarked_mirror"
UNLINKED_REVERSAL = "unlinked_reversal"
LARGE_UNUSUAL_INCOME = "large_unusual_income"
UNCATEGORIZED_EXPENSE = "uncategorized_expense"

ALL_KINDS = (
    SYSTEM_SAYS_TRANSFER,
    UNMARKED_MIRROR,
    UNLINKED_REVERSAL,
    LARGE_UNUSUAL_INCOME,
    UNCATEGORIZED_EXPENSE,
)

SEVERITY = {
    SYSTEM_SAYS_TRANSFER: "high",
    UNMARKED_MIRROR: "warn",
    UNLINKED_REVERSAL: "warn",
    LARGE_UNUSUAL_INCOME: "info",
    UNCATEGORIZED_EXPENSE: "info",
}

# --- parâmetros ------------------------------------------------------------
MIRROR_MAX_DAYS = 2
# Valores pequenos coincidem à toa: na auditoria real de 30/09, 5 de 7 pares eram coincidência
# (um gasto de R$ 12 e um Pix de R$ 12 recebido de terceiro), todos abaixo de R$ 50.
MIN_MIRROR_AMOUNT = Decimal("50")
LARGE_INCOME_MIN = Decimal("500")
LARGE_INCOME_MEDIAN_FACTOR = 5
DEFAULT_WINDOW_DAYS = 120

# Descrição que sugere movimentação entre contas; sem isso um par de mesmo valor é coincidência.
_MIRROR_HINT = re.compile(
    r"pix|transfer[eê]ncia|pagamento|\bted\b|\bdoc\b|fatura|cr[eé]dito|recebid|enviad",
    re.IGNORECASE,
)
# Créditos que anulam uma cobrança anterior (não são renda).
_REVERSAL_CREDIT = re.compile(
    r"cr[eé]dito\s+de\s+atraso|encerramento\s+de\s+d[ií]vida|cr[eé]dito\s+de\s+parcelamento",
    re.IGNORECASE,
)
_NORMALIZE_RE = re.compile(r"[0-9]+|\s+")


@dataclass(frozen=True)
class TxView:
    id: str
    date: date
    amount: Decimal
    type: str  # "EXPENSE" | "INCOME"
    is_transfer: bool
    description: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    classification_source: Optional[str] = None
    external_category: Optional[str] = None


@dataclass(frozen=True)
class Finding:
    kind: str
    transaction_ids: tuple[str, ...]
    detail: dict = field(default_factory=dict, compare=False)

    @property
    def severity(self) -> str:
        return SEVERITY[self.kind]

    @property
    def fingerprint(self) -> str:
        raw = f"{self.kind}:{','.join(sorted(self.transaction_ids))}"
        return hashlib.sha1(raw.encode()).hexdigest()


def _manual(tx: TxView) -> bool:
    return tx.classification_source == ClassificationSource.MANUAL_OVERRIDE


def _pairs_same_amount(txs: Iterable[TxView], *, min_amount: Decimal = Decimal("0")):
    """Agrupa por valor: `{valor: {"EXPENSE": [...], "INCOME": [...]}}`, ordenado por data."""
    groups: dict[Decimal, dict[str, list[TxView]]] = defaultdict(
        lambda: {"EXPENSE": [], "INCOME": []}
    )
    for tx in txs:
        if tx.amount >= min_amount and tx.type in ("EXPENSE", "INCOME"):
            groups[tx.amount][tx.type].append(tx)
    for sides in groups.values():
        for lst in sides.values():
            lst.sort(key=lambda t: (t.date, t.id))
    return groups


def _closest(expense: TxView, incomes: Sequence[TxView], used: set[str]) -> Optional[TxView]:
    best: Optional[tuple[int, TxView]] = None
    for income in incomes:
        if income.id in used:
            continue
        diff = abs((expense.date - income.date).days)
        if diff <= MIRROR_MAX_DAYS and (best is None or diff < best[0]):
            best = (diff, income)
    return best[1] if best else None


def detect_system_says_transfer(
    txs: Iterable[TxView], user_full_name: Optional[str] = None
) -> list[Finding]:
    """A regra atual do sistema trataria como transferência, mas a linha não está marcada.

    Só as regras por **descrição** (pagamento de fatura, eco de pagamento, transferência
    própria): a categoria crua da Pluggy fica de fora porque uma regra do usuário pode
    legitimamente discordar dela (ex: MERCADOLIVRE vem como `Investments`).
    """
    out = []
    for tx in txs:
        if tx.is_transfer or _manual(tx):
            continue
        if is_transfer(
            None,
            tx.description,
            is_income=(tx.type == "INCOME"),
            user_full_name=user_full_name,
        ):
            out.append(
                Finding(
                    SYSTEM_SAYS_TRANSFER,
                    (tx.id,),
                    {"description": tx.description, "amount": str(tx.amount), "date": str(tx.date)},
                )
            )
    return out


def detect_unlinked_reversals(txs: Iterable[TxView]) -> list[Finding]:
    """Crédito que anula uma cobrança (`Crédito de atraso`) sem vínculo com ela."""
    txs = list(txs)
    out: list[Finding] = []
    used: set[str] = set()
    for amount, sides in _pairs_same_amount(txs).items():
        for income in sides["INCOME"]:
            if not _REVERSAL_CREDIT.search(income.description):
                continue
            if income.is_transfer or _manual(income):
                continue
            candidates = [e for e in sides["EXPENSE"] if not e.is_transfer and not _manual(e)]
            expense = _closest(income, candidates, used)
            if expense is None:
                continue
            used.update({income.id, expense.id})
            out.append(
                Finding(
                    UNLINKED_REVERSAL,
                    (expense.id, income.id),
                    {
                        "amount": str(amount),
                        "expense": expense.description,
                        "credit": income.description,
                        "date": str(income.date),
                    },
                )
            )
    return out


def detect_unmarked_mirrors(
    txs: Iterable[TxView], skip_ids: frozenset[str] = frozenset()
) -> list[Finding]:
    """A saída já é transferência, mas a entrada de mesmo valor (até 2 dias) não é.

    É o padrão que infla a renda: o sistema reconheceu o dinheiro saindo e deixou o mesmo
    dinheiro entrando como receita. O inverso (entrada marcada, saída não) **não** é acusado:
    é o caso normal de recarga por cartão e de gasto real pago com crédito liberado, que na
    auditoria real de 30/09 dava falso positivo. Pares com os dois lados marcados estão certos.
    """
    out: list[Finding] = []
    used: set[str] = set(skip_ids)
    for amount, sides in _pairs_same_amount(txs, min_amount=MIN_MIRROR_AMOUNT).items():
        for expense in sides["EXPENSE"]:
            if expense.id in used:
                continue
            income = _closest(expense, sides["INCOME"], used)
            if income is None:
                continue
            if expense.is_transfer and income.is_transfer:
                used.update({expense.id, income.id})
                continue
            if not expense.is_transfer or income.is_transfer:
                continue
            if _manual(expense) or _manual(income):
                continue
            if not (
                _MIRROR_HINT.search(expense.description) or _MIRROR_HINT.search(income.description)
            ):
                continue
            used.update({expense.id, income.id})
            out.append(
                Finding(
                    UNMARKED_MIRROR,
                    (expense.id, income.id),
                    {
                        "amount": str(amount),
                        "expense": expense.description,
                        "income": income.description,
                        "expense_is_transfer": expense.is_transfer,
                        "income_is_transfer": income.is_transfer,
                        "date": str(income.date),
                    },
                )
            )
    return out


def detect_large_unusual_income(txs: Iterable[TxView]) -> list[Finding]:
    """Entrada bem acima do padrão e sem categoria de renda reconhecida."""
    incomes = [t for t in txs if t.type == "INCOME" and not t.is_transfer]
    if len(incomes) < 5:
        return []
    median = Decimal(str(statistics.median(float(t.amount) for t in incomes)))
    threshold = max(LARGE_INCOME_MIN, median * LARGE_INCOME_MEDIAN_FACTOR)
    out = []
    for tx in incomes:
        if tx.amount < threshold or _manual(tx):
            continue
        if tx.category_name not in (None, "Outras receitas"):
            continue
        out.append(
            Finding(
                LARGE_UNUSUAL_INCOME,
                (tx.id,),
                {
                    "description": tx.description,
                    "amount": str(tx.amount),
                    "median_income": str(median.quantize(Decimal("0.01"))),
                    "date": str(tx.date),
                },
            )
        )
    return out


def detect_uncategorized_expenses(txs: Iterable[TxView]) -> list[Finding]:
    return [
        Finding(
            UNCATEGORIZED_EXPENSE,
            (tx.id,),
            {"description": tx.description, "amount": str(tx.amount), "date": str(tx.date)},
        )
        for tx in txs
        if tx.type == "EXPENSE"
        and not tx.is_transfer
        and tx.category_id is None
        and not _manual(tx)
    ]


def detect_all(txs: Sequence[TxView], user_full_name: Optional[str] = None) -> list[Finding]:
    reversals = detect_unlinked_reversals(txs)
    already = frozenset(i for f in reversals for i in f.transaction_ids)
    findings = [
        *detect_system_says_transfer(txs, user_full_name),
        *reversals,
        *detect_unmarked_mirrors(txs, skip_ids=already),
        *detect_large_unusual_income(txs),
        *detect_uncategorized_expenses(txs),
    ]
    # Uma linha que a regra do sistema já condena não precisa aparecer de novo como suspeita
    # mais fraca (espelho); a de maior severidade vence.
    flagged_high = {
        i for f in findings if f.kind == SYSTEM_SAYS_TRANSFER for i in f.transaction_ids
    }
    return [
        f
        for f in findings
        if f.kind == SYSTEM_SAYS_TRANSFER
        or not (
            f.kind in (UNMARKED_MIRROR, LARGE_UNUSUAL_INCOME)
            and flagged_high.intersection(f.transaction_ids)
        )
    ]


# --- resíduo sem classificação (#169) --------------------------------------


@dataclass(frozen=True)
class ResidualReport:
    expenses_count: int
    expenses_amount: Decimal
    uncategorized_count: int
    uncategorized_amount: Decimal
    uncategorized_pct_count: float
    uncategorized_pct_amount: float
    without_classification_source: int
    without_external_category: int
    top_uncategorized: list[tuple[str, int, Decimal]]


def _normalize(description: str) -> str:
    return _NORMALIZE_RE.sub(" ", description.upper()).strip()


def build_residual_report(txs: Iterable[TxView], top: int = 10) -> ResidualReport:
    expenses = [t for t in txs if t.type == "EXPENSE" and not t.is_transfer]
    uncategorized = [t for t in expenses if t.category_id is None]
    total_amount = sum((t.amount for t in expenses), Decimal("0"))
    unc_amount = sum((t.amount for t in uncategorized), Decimal("0"))

    grouped: dict[str, list[Decimal]] = defaultdict(list)
    for t in uncategorized:
        grouped[_normalize(t.description)].append(t.amount)
    ranked = sorted(grouped.items(), key=lambda kv: (-sum(kv[1]), kv[0]))[:top]

    def pct(part, whole):
        return round(float(part) / float(whole) * 100, 1) if whole else 0.0

    return ResidualReport(
        expenses_count=len(expenses),
        expenses_amount=total_amount,
        uncategorized_count=len(uncategorized),
        uncategorized_amount=unc_amount,
        uncategorized_pct_count=pct(len(uncategorized), len(expenses)),
        uncategorized_pct_amount=pct(unc_amount, total_amount),
        without_classification_source=sum(1 for t in expenses if t.classification_source is None),
        without_external_category=sum(1 for t in expenses if t.external_category is None),
        top_uncategorized=[(k, len(v), sum(v, Decimal("0"))) for k, v in ranked],
    )


# --- carga e persistência --------------------------------------------------


def load_tx_views(
    db: Session, user_id: UUID, *, days: int = DEFAULT_WINDOW_DAYS, today: Optional[date] = None
) -> list[TxView]:
    """Transações já ocorridas na janela (parcelas futuras ficam de fora)."""
    today = today or date.today()
    names = {
        str(c.id): c.name
        for c in db.execute(select(Category).where(Category.user_id == user_id)).scalars()
    }
    rows = db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.date >= today - timedelta(days=days),
            Transaction.date <= today,
        )
    ).scalars()
    return [
        TxView(
            id=str(t.id),
            date=t.date,
            amount=Decimal(t.amount),
            type=t.type.value,
            is_transfer=t.is_transfer,
            description=t.description,
            category_id=str(t.category_id) if t.category_id else None,
            category_name=names.get(str(t.category_id)) if t.category_id else None,
            classification_source=t.classification_source,
            external_category=t.external_category,
        )
        for t in rows
    ]


@dataclass(frozen=True)
class AuditResult:
    findings: list[Finding]
    residual: ResidualReport
    audited_ids: frozenset[str]


def run_audit(
    db: Session, user_id: UUID, *, days: int = DEFAULT_WINDOW_DAYS, today: Optional[date] = None
) -> AuditResult:
    txs = load_tx_views(db, user_id, days=days, today=today)
    full_name = db.execute(select(User.full_name).where(User.id == user_id)).scalar_one_or_none()
    return AuditResult(
        findings=detect_all(txs, full_name),
        residual=build_residual_report(txs),
        audited_ids=frozenset(t.id for t in txs),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def persist_findings(
    db: Session,
    user_id: UUID,
    findings: Sequence[Finding],
    audited_ids: frozenset[str],
    *,
    now: Optional[datetime] = None,
) -> dict[str, int]:
    """Grava os achados de forma idempotente e fecha os que sumiram.

    - achado novo vira `open`; o mesmo achado de novo não duplica;
    - `resolved` que reaparece volta a `open`; `dismissed` nunca é reaberto;
    - `open` que a auditoria não encontra mais vira `resolved`, **só** se todas as suas
      transações estavam na janela auditada (fora dela não dá para afirmar que foi corrigido).
    """
    now = now or _now()
    existing = {
        i.fingerprint: i
        for i in db.execute(
            select(DataQualityIssue).where(
                DataQualityIssue.user_id == user_id, DataQualityIssue.kind.in_(ALL_KINDS)
            )
        ).scalars()
    }
    stats = {"new": 0, "unchanged": 0, "reopened": 0, "resolved": 0}
    current = set()
    for f in findings:
        current.add(f.fingerprint)
        issue = existing.get(f.fingerprint)
        if issue is None:
            db.add(
                DataQualityIssue(
                    user_id=user_id,
                    kind=f.kind,
                    severity=f.severity,
                    status="open",
                    fingerprint=f.fingerprint,
                    transaction_ids=list(f.transaction_ids),
                    detail=f.detail,
                    detected_at=now,
                )
            )
            stats["new"] += 1
        elif issue.status == "resolved":
            issue.status, issue.resolved_at, issue.detail = "open", None, f.detail
            stats["reopened"] += 1
        else:
            stats["unchanged"] += 1
    for fp, issue in existing.items():
        if fp in current or issue.status != "open":
            continue
        if all(tid in audited_ids for tid in issue.transaction_ids):
            issue.status, issue.resolved_at = "resolved", now
            stats["resolved"] += 1
    db.flush()
    return stats
