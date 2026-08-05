from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payable import Payable, PayableStatus
from app.models.push_subscription import PushSubscription
from app.schemas.push_subscription import PushSubscriptionCreate


def _log(message: str) -> None:
    print(f"[push] {message}", file=sys.stderr)


def _vapid_key(raw: str):
    """Normaliza a chave VAPID para o formato que o `pywebpush` aceita.

    `webpush(vapid_private_key=...)` trata uma string de três formas: instância
    `Vapid01`, caminho de arquivo existente, ou **base64** — nessa ordem. O
    conteúdo de um PEM cai no último caso e estoura em
    `Could not deserialize key data ... ASN.1 parsing error`, porque ele tenta
    decodificar os cabeçalhos `-----BEGIN-----` como base64.

    Era por isso que nenhuma notificação chegava: a exceção acontecia antes de
    qualquer requisição sair, então a subscription nunca era rejeitada e nada
    indicava falha do lado do navegador.
    """
    if "BEGIN" in raw:
        from py_vapid import Vapid01

        return Vapid01.from_pem(raw.encode())
    return raw


def save_subscription(
    db: Session, user_id: UUID, payload: PushSubscriptionCreate
) -> PushSubscription:
    existing = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    ).scalar_one_or_none()

    if existing:
        existing.user_id = user_id
        existing.p256dh = payload.p256dh
        existing.auth = payload.auth
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    sub = PushSubscription(user_id=user_id, **payload.model_dump())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def send_upcoming_notifications(db: Session, user_id: UUID, days: int = 3) -> int:
    """
    Sends push notifications for upcoming payables.
    Requires VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIMS_EMAIL env vars.
    Returns the number of notifications sent.
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        raise RuntimeError("pywebpush not installed. Add it to requirements.txt.")

    vapid_private = settings.vapid_private_key
    vapid_claims_email = settings.vapid_claims_email or "mailto:admin@example.com"

    if not vapid_private:
        raise RuntimeError("VAPID_PRIVATE_KEY environment variable not set.")

    today = date.today()
    until = today + timedelta(days=days)
    upcoming = db.execute(
        select(Payable).where(
            Payable.user_id == user_id,
            Payable.status == PayableStatus.PENDING,
            Payable.due_date >= today,
            Payable.due_date <= until,
        )
    ).scalars().all()

    if not upcoming:
        return 0

    subscriptions: List[PushSubscription] = db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    ).scalars().all()

    titles = [p.title for p in upcoming[:3]]
    body = f"Você tem {len(upcoming)} conta(s) vencendo em breve: {', '.join(titles)}"
    payload_data = json.dumps({"title": "LifeOS — Contas Vencendo", "body": body})

    if not subscriptions:
        _log(f"nenhum device inscrito para o usuário {user_id} — push não enviado")
        return 0

    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload_data,
                vapid_private_key=_vapid_key(vapid_private),
                vapid_claims={"sub": vapid_claims_email},
            )
            sent += 1
        except WebPushException as exc:
            # 404/410 = subscription morta (app desinstalado, permissão revogada,
            # endpoint rotacionado pelo navegador). Removê-la evita tentar de
            # novo todo dia contra um device que não existe mais.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                _log(f"subscription expirada (HTTP {status}), removendo: {sub.endpoint[:60]}")
                db.delete(sub)
            else:
                _log(f"falha ao enviar push (HTTP {status}): {exc}")
        except Exception as exc:  # noqa: BLE001
            # Engolir toda exceção em silêncio deixava o push falhar sem deixar
            # rastro: o job retornava 0 enviados e não havia como distinguir
            # "ninguém inscrito" de "chave errada" ou "serviço fora do ar".
            _log(f"erro inesperado ao enviar push: {type(exc).__name__}: {exc}")

    db.commit()
    _log(f"push: {sent}/{len(subscriptions)} enviados para o usuário {user_id}")
    return sent
