"""Ações do usuário sobre os achados da auditoria: listar, ver a prévia, aplicar, dispensar (#200).

A auditoria (`data_quality_service`) só sinaliza. Aqui o usuário decide, e **nada é alterado
sem prévia**: `preview_fix` mostra exatamente o que mudaria e `apply_fix` faz só isso. O que o
usuário confirma vira `manual_override`, travado contra reprocessamento pelo sync.

Cada achado se confere de novo na hora de aplicar: se a transação já foi corrigida por outro
caminho, a ação não muda nada e o achado é fechado, em vez de sobrescrever uma decisão nova.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.data_quality_issue import DataQualityIssue
from app.models.transaction import ClassificationSource, Transaction
from app.services import data_quality_service as dq

OPEN = "open"
RESOLVED = "resolved"
DISMISSED = "dismissed"

# Achados cuja correção é marcar a(s) linha(s) como transferência.
_TRANSFER_KINDS = {dq.SYSTEM_SAYS_TRANSFER, dq.UNMARKED_MIRROR, dq.UNLINKED_REVERSAL}


class IssueNotFoundError(Exception):
    """O achado não existe ou é de outro usuário (mesma resposta, para não vazar existência)."""


class IssueNotOpenError(Exception):
    """Só achado aberto pode ser corrigido ou dispensado."""


class FixNotAvailableError(Exception):
    """Este tipo de achado não tem correção automática (o usuário só pode dispensar)."""


class InvalidCategoryError(Exception):
    """Categoria inexistente, de outro usuário ou de direção errada para a transação."""


@dataclass(frozen=True)
class TxChange:
    transaction_id: str
    description: str
    amount: Decimal
    date: date
    type: str
    field: str  # "is_transfer" | "category_id"
    old: str
    new: str


@dataclass(frozen=True)
class FixPreview:
    issue_id: UUID
    kind: str
    fix_available: bool
    needs_category: bool
    changes: list[TxChange] = field(default_factory=list)
    income_removed: Decimal = Decimal("0.00")
    expense_removed: Decimal = Decimal("0.00")
    already_fixed: bool = False


@dataclass(frozen=True)
class IssueView:
    issue: DataQualityIssue
    transactions: list[Transaction]
    category_names: dict[str, str]
    fix_available: bool
    needs_category: bool


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fix_available(kind: str) -> bool:
    return kind in _TRANSFER_KINDS or kind == dq.UNCATEGORIZED_EXPENSE


def _get_issue(db: Session, user_id: UUID, issue_id: UUID) -> DataQualityIssue:
    issue = db.execute(
        select(DataQualityIssue).where(
            DataQualityIssue.id == issue_id, DataQualityIssue.user_id == user_id
        )
    ).scalar_one_or_none()
    if issue is None:
        raise IssueNotFoundError(str(issue_id))
    return issue


def _load_transactions(db: Session, user_id: UUID, ids: Sequence[str]) -> list[Transaction]:
    uuids = []
    for raw in ids:
        try:
            uuids.append(UUID(str(raw)))
        except ValueError:
            continue
    if not uuids:
        return []
    return list(
        db.execute(
            select(Transaction).where(Transaction.user_id == user_id, Transaction.id.in_(uuids))
        ).scalars()
    )


def _category_names(db: Session, user_id: UUID) -> dict[str, str]:
    return {
        str(c.id): c.name
        for c in db.execute(select(Category).where(Category.user_id == user_id)).scalars()
    }


# --- consulta --------------------------------------------------------------


def list_issues(
    db: Session,
    user_id: UUID,
    *,
    status: str = OPEN,
    severity: Optional[str] = None,
    limit: int = 200,
) -> list[IssueView]:
    stmt = select(DataQualityIssue).where(
        DataQualityIssue.user_id == user_id, DataQualityIssue.status == status
    )
    if severity:
        stmt = stmt.where(DataQualityIssue.severity == severity)
    issues = list(
        db.execute(stmt.order_by(DataQualityIssue.detected_at.desc()).limit(limit)).scalars()
    )

    names = _category_names(db, user_id)
    order = {"high": 0, "warn": 1, "info": 2}
    views = []
    for issue in issues:
        views.append(
            IssueView(
                issue=issue,
                transactions=_load_transactions(db, user_id, issue.transaction_ids),
                category_names=names,
                fix_available=_fix_available(issue.kind),
                needs_category=issue.kind == dq.UNCATEGORIZED_EXPENSE,
            )
        )
    views.sort(key=lambda v: (order.get(v.issue.severity, 9), -v.issue.detected_at.timestamp()))
    return views


def summarize(db: Session, user_id: UUID) -> dict:
    rows = db.execute(
        select(DataQualityIssue.severity, DataQualityIssue.kind, func.count())
        .where(DataQualityIssue.user_id == user_id, DataQualityIssue.status == OPEN)
        .group_by(DataQualityIssue.severity, DataQualityIssue.kind)
    ).all()
    by_severity = {"high": 0, "warn": 0, "info": 0}
    by_kind: dict[str, int] = {}
    for severity, kind, n in rows:
        by_severity[severity] = by_severity.get(severity, 0) + n
        by_kind[kind] = by_kind.get(kind, 0) + n
    last = db.execute(
        select(func.max(DataQualityIssue.detected_at)).where(DataQualityIssue.user_id == user_id)
    ).scalar_one_or_none()
    return {
        "open_total": sum(by_severity.values()),
        "by_severity": by_severity,
        "by_kind": by_kind,
        "last_detected_at": last,
    }


def run_now(db: Session, user_id: UUID, *, days: int = dq.DEFAULT_WINDOW_DAYS) -> dict[str, int]:
    result = dq.run_audit(db, user_id, days=days)
    stats = dq.persist_findings(db, user_id, result.findings, result.audited_ids)
    db.commit()
    return stats


# --- prévia e aplicação ----------------------------------------------------


def _validate_category(db: Session, user_id: UUID, category_id: UUID, tx: Transaction) -> Category:
    cat = db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    ).scalar_one_or_none()
    if cat is None or cat.kind.value != tx.type.value:
        raise InvalidCategoryError(str(category_id))
    return cat


def _plan(
    db: Session, user_id: UUID, issue: DataQualityIssue, category_id: Optional[UUID]
) -> tuple[FixPreview, list[tuple[Transaction, str, object]]]:
    """Calcula o que mudaria. Devolve a prévia e a lista de (transação, campo, novo valor)."""
    if not _fix_available(issue.kind):
        return FixPreview(issue.id, issue.kind, False, False), []

    txs = _load_transactions(db, user_id, issue.transaction_ids)
    names = _category_names(db, user_id)
    changes: list[TxChange] = []
    ops: list[tuple[Transaction, str, object]] = []
    income = expense = Decimal("0.00")

    if issue.kind in _TRANSFER_KINDS:
        for tx in txs:
            if tx.is_transfer:
                continue  # já corrigida por outro caminho
            changes.append(_change(tx, "is_transfer", "false", "true"))
            ops.append((tx, "is_transfer", True))
            if tx.type.value == "INCOME":
                income += Decimal(tx.amount)
            else:
                expense += Decimal(tx.amount)
    else:  # UNCATEGORIZED_EXPENSE
        for tx in txs:
            if tx.category_id is not None:
                continue
            if category_id is None:
                continue  # sem categoria escolhida ainda: só descreve que falta
            cat = _validate_category(db, user_id, category_id, tx)
            changes.append(_change(tx, "category_id", "sem categoria", names.get(str(cat.id), "")))
            ops.append((tx, "category_id", cat.id))

    # A premissa do achado já não vale (alguém corrigiu por outro caminho): nada a mudar.
    if issue.kind in _TRANSFER_KINDS:
        already_fixed = all(tx.is_transfer for tx in txs)
    else:
        already_fixed = all(tx.category_id is not None for tx in txs)

    preview = FixPreview(
        issue_id=issue.id,
        kind=issue.kind,
        fix_available=True,
        needs_category=issue.kind == dq.UNCATEGORIZED_EXPENSE,
        changes=changes,
        income_removed=income,
        expense_removed=expense,
        already_fixed=already_fixed,
    )
    return preview, ops


def _change(tx: Transaction, field_name: str, old: str, new: str) -> TxChange:
    return TxChange(
        transaction_id=str(tx.id),
        description=tx.description,
        amount=Decimal(tx.amount),
        date=tx.date,
        type=tx.type.value,
        field=field_name,
        old=old,
        new=new,
    )


def preview_fix(
    db: Session, user_id: UUID, issue_id: UUID, *, category_id: Optional[UUID] = None
) -> FixPreview:
    issue = _get_issue(db, user_id, issue_id)
    return _plan(db, user_id, issue, category_id)[0]


def apply_fix(
    db: Session, user_id: UUID, issue_id: UUID, *, category_id: Optional[UUID] = None
) -> FixPreview:
    issue = _get_issue(db, user_id, issue_id)
    if issue.status != OPEN:
        raise IssueNotOpenError(str(issue_id))
    if not _fix_available(issue.kind):
        raise FixNotAvailableError(issue.kind)

    preview, ops = _plan(db, user_id, issue, category_id)
    if preview.needs_category and category_id is None and not preview.already_fixed:
        raise InvalidCategoryError("categoria obrigatória")

    for tx, field_name, value in ops:
        setattr(tx, field_name, value)
        tx.classification_source = ClassificationSource.MANUAL_OVERRIDE
    issue.status = RESOLVED
    issue.resolved_at = _now()
    db.commit()
    return preview


def dismiss(db: Session, user_id: UUID, issue_id: UUID) -> None:
    issue = _get_issue(db, user_id, issue_id)
    if issue.status != OPEN:
        raise IssueNotOpenError(str(issue_id))
    issue.status = DISMISSED
    issue.resolved_at = _now()
    db.commit()
