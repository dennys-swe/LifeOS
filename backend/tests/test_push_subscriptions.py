from __future__ import annotations

from unittest.mock import patch

from app.services import push_service
from app.schemas.push_subscription import PushSubscriptionCreate


def test_vapid_public_key_endpoint(client):
    with patch("app.api.endpoints.push_subscriptions.settings.vapid_public_key", "test-public-key"):
        response = client.get("/push-subscriptions/vapid-public-key")
    assert response.status_code == 200
    assert response.json() == {"public_key": "test-public-key"}


def test_vapid_public_key_endpoint_503_when_unconfigured(client):
    with patch("app.api.endpoints.push_subscriptions.settings.vapid_public_key", None):
        response = client.get("/push-subscriptions/vapid-public-key")
    assert response.status_code == 503


def test_subscribe_via_api(client):
    response = client.post(
        "/push-subscriptions",
        json={"endpoint": "https://push.example.com/1", "p256dh": "key", "auth": "auth"},
    )
    assert response.status_code == 201
    assert response.json()["endpoint"] == "https://push.example.com/1"


def test_save_subscription_reassigns_endpoint_to_new_user(db_session, user, other_user):
    payload = PushSubscriptionCreate(endpoint="https://push.example.com/2", p256dh="key", auth="auth")
    first = push_service.save_subscription(db_session, user.id, payload)
    assert first.user_id == user.id

    second = push_service.save_subscription(db_session, other_user.id, payload)
    assert second.id == first.id
    assert second.user_id == other_user.id


def test_send_upcoming_notifications_only_notifies_owner(db_session, user, other_user, monkeypatch):
    from datetime import date, timedelta
    from app.models.payable import Payable, PayableStatus

    # other_user não tem nada a vencer, então nenhum webpush é disparado — mas a
    # função exige VAPID configurado antes de chegar a essa conclusão. Damos um
    # valor de teste para não depender do .env local (falhava em CI sem ele).
    monkeypatch.setattr(push_service.settings, "vapid_private_key", "test-vapid-key")

    db_session.add(
        Payable(
            user_id=user.id,
            title="Conta",
            amount=50,
            due_date=date.today() + timedelta(days=1),
            status=PayableStatus.PENDING,
        )
    )
    db_session.commit()

    sent = push_service.send_upcoming_notifications(db_session, other_user.id, days=3)
    assert sent == 0
