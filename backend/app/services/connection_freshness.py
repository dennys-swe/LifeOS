"""Idade real do dado de uma conexão bancária (#214).

Funções puras. `BankAccount.last_sync_at` diz quando o LifeOS leu a Pluggy; o que importa
para confiar no número é quando a **Pluggy leu o banco** (`item_last_updated_at`) e se ela
vai voltar a ler sozinha (`item_next_auto_sync_at`). Caso real (30/09/2026): o item do Inter
estava com 13 dias sem atualizar e `nextAutoSyncAt` nulo, sem erro e com `last_sync_at` de
hoje; Itaú e Nubank tinham atualização agendada para o dia seguinte.

Devolve códigos, não textos: a redação fica no frontend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# Sem atualização há mais que isto e sem nova leitura agendada: a conexão parou.
STALE_AFTER = timedelta(hours=48)
# Avisar a autorização (consentimento) que vence em até este prazo.
CONSENT_WARN_DAYS = 30

# Estados do item em que o banco precisa de ação do usuário (reconectar/reautorizar).
ATTENTION_STATUSES = {"LOGIN_ERROR", "OUTDATED", "WAITING_USER_INPUT", "WAITING_USER_ACTION"}

FRESH = "fresh"
STALE = "stale"
ATTENTION = "attention"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConnectionFreshness:
    state: str  # fresh | stale | attention | unknown
    reason: str  # ok | no_auto_sync | auto_sync_overdue | needs_attention | not_checked
    data_age_hours: Optional[float]
    auto_sync_scheduled: bool
    consent_days_left: Optional[int]
    consent_expiring: bool


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def assess_connection_freshness(
    *,
    item_checked_at: Optional[datetime],
    item_status: Optional[str],
    item_user_action: Optional[str],
    item_last_updated_at: Optional[datetime],
    item_next_auto_sync_at: Optional[datetime],
    consent_expires_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> ConnectionFreshness:
    now = now or _now()

    consent_days_left = None
    consent_expiring = False
    if consent_expires_at is not None:
        consent_days_left = (consent_expires_at - now).days
        consent_expiring = consent_days_left <= CONSENT_WARN_DAYS

    age_hours = None
    if item_last_updated_at is not None:
        age_hours = round(max((now - item_last_updated_at).total_seconds(), 0) / 3600, 1)
    scheduled = item_next_auto_sync_at is not None and item_next_auto_sync_at > now

    def result(state: str, reason: str) -> ConnectionFreshness:
        return ConnectionFreshness(
            state=state,
            reason=reason,
            data_age_hours=age_hours,
            auto_sync_scheduled=scheduled,
            consent_days_left=consent_days_left,
            consent_expiring=consent_expiring,
        )

    if item_checked_at is None:
        return result(UNKNOWN, "not_checked")
    if item_status in ATTENTION_STATUSES or item_user_action:
        return result(ATTENTION, "needs_attention")
    if item_last_updated_at is None:
        return result(UNKNOWN, "not_checked")
    if now - item_last_updated_at > STALE_AFTER and not scheduled:
        reason = "no_auto_sync" if item_next_auto_sync_at is None else "auto_sync_overdue"
        return result(STALE, reason)
    return result(FRESH, "ok")


def parse_pluggy_datetime(value: Any) -> Optional[datetime]:
    """ISO 8601 da Pluggy ('2026-09-17T12:32:52.971Z') para UTC sem tzinfo, como o schema."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed
