from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.data_quality import (
    ApplyFixRequest,
    DataQualityIssueResponse,
    DataQualitySummaryResponse,
    FixPreviewResponse,
    IssueTransaction,
    RunAuditResponse,
)
from app.services import data_quality_actions as actions
from app.services.data_quality_service import DEFAULT_WINDOW_DAYS

router = APIRouter(prefix="/data-quality", tags=["Data Quality"])


def _to_response(view: actions.IssueView) -> DataQualityIssueResponse:
    issue = view.issue
    by_id = {str(t.id): t for t in view.transactions}
    # Mantém a ordem em que o achado lista as transações (ex: saída antes da entrada).
    ordered = [by_id[i] for i in issue.transaction_ids if i in by_id]
    return DataQualityIssueResponse(
        id=issue.id,
        kind=issue.kind,
        severity=issue.severity,
        status=issue.status,
        detected_at=issue.detected_at,
        detail=issue.detail or {},
        transactions=[
            IssueTransaction(
                id=t.id,
                date=t.date,
                description=t.description,
                amount=t.amount,
                type=t.type.value,
                is_transfer=t.is_transfer,
                category_name=view.category_names.get(str(t.category_id))
                if t.category_id
                else None,
            )
            for t in ordered
        ],
        fix_available=view.fix_available,
        needs_category=view.needs_category,
    )


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, actions.IssueNotFoundError):
        return HTTPException(status_code=404, detail="Achado não encontrado")
    if isinstance(exc, actions.IssueNotOpenError):
        return HTTPException(status_code=409, detail="Este achado já foi tratado")
    if isinstance(exc, actions.FixNotAvailableError):
        return HTTPException(status_code=409, detail="Este achado não tem correção automática")
    if isinstance(exc, actions.InvalidCategoryError):
        return HTTPException(
            status_code=422, detail="Escolha uma categoria válida para esta transação"
        )
    raise exc


# Paths literais antes de `/issues/{id}/...` (ver nota de ordem de rotas no CLAUDE.md).
@router.get("/summary", response_model=DataQualitySummaryResponse)
def get_summary(db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    return actions.summarize(db, user.id)


@router.post("/run", response_model=RunAuditResponse)
def run_audit_now(
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=7, le=400),
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Roda a auditoria agora para o usuário e grava os achados (idempotente)."""
    return actions.run_now(db, user.id, days=days)


@router.get("/issues", response_model=List[DataQualityIssueResponse])
def list_issues(
    status: str = Query(default=actions.OPEN, pattern="^(open|resolved|dismissed)$"),
    severity: Optional[str] = Query(default=None, pattern="^(high|warn|info)$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return [
        _to_response(v) for v in actions.list_issues(db, user.id, status=status, severity=severity)
    ]


@router.get("/issues/{issue_id}/preview", response_model=FixPreviewResponse)
def preview_fix(
    issue_id: UUID,
    category_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    try:
        return actions.preview_fix(db, user.id, issue_id, category_id=category_id)
    except (actions.IssueNotFoundError, actions.InvalidCategoryError) as exc:
        raise _http(exc) from exc


@router.post("/issues/{issue_id}/apply", response_model=FixPreviewResponse)
def apply_fix(
    issue_id: UUID,
    payload: ApplyFixRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    try:
        return actions.apply_fix(db, user.id, issue_id, category_id=payload.category_id)
    except (
        actions.IssueNotFoundError,
        actions.IssueNotOpenError,
        actions.FixNotAvailableError,
        actions.InvalidCategoryError,
    ) as exc:
        raise _http(exc) from exc


@router.post("/issues/{issue_id}/dismiss", status_code=204)
def dismiss_issue(
    issue_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    try:
        actions.dismiss(db, user.id, issue_id)
    except (actions.IssueNotFoundError, actions.IssueNotOpenError) as exc:
        raise _http(exc) from exc
