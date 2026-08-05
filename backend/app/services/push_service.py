from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from decimal import Decimal
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


def _brl(value) -> str:
    inteiro = f"{Decimal(str(value)):,.2f}"
    return "R$ " + inteiro.replace(",", "@").replace(".", ",").replace("@", ".")


def _quando(due: date, today: date) -> str:
    """Prazo em linguagem natural. "amanhã" comunica urgência melhor que
    "08/08", que exige o usuário lembrar que dia é hoje."""
    dias = (due - today).days
    if dias <= 0:
        return "hoje"
    if dias == 1:
        return "amanhã"
    return f"em {due.strftime('%d/%m')}"


def _rotulo(title: str) -> str:
    """"Fatura Nubank — 08/2026" -> "Fatura Nubank".

    A competência é ruído numa notificação sobre algo que vence agora, e come
    o espaço que o iOS reserva para a prévia.
    """
    return title.split(" — ")[0].strip() or title


def build_notification(upcoming: List[Payable], today: date) -> dict:
    """Monta título e corpo do push.

    Função pura para poder ser testada sem tocar em rede nem em banco.

    O texto anterior ("Você tem 2 conta(s) vencendo em breve: ...") não dizia
    **quanto** nem **quando** — as notificações dos próprios bancos, na mesma
    tela de bloqueio, trazem valor e data. Sem isso o usuário precisa abrir o
    app para saber se aquilo é urgente.

    O título também não repete "LifeOS": o iOS já exibe o nome do app acima da
    mensagem, então prefixá-lo aparecia duas vezes.
    """
    total = sum(Decimal(str(p.amount)) for p in upcoming)

    if len(upcoming) == 1:
        conta = upcoming[0]
        return {
            "title": f"{_rotulo(conta.title)} vence {_quando(conta.due_date, today)}",
            "body": _brl(conta.amount),
        }

    detalhes = ", ".join(
        f"{_rotulo(p.title)} ({_quando(p.due_date, today)})" for p in upcoming[:3]
    )
    if len(upcoming) > 3:
        detalhes += f" e mais {len(upcoming) - 3}"

    return {
        "title": f"{len(upcoming)} contas vencendo",
        "body": f"{_brl(total)} no total · {detalhes}",
    }


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

    payload_data = json.dumps(build_notification(upcoming, today))

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
