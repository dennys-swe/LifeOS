from __future__ import annotations

import os
import time

import pluggy_sdk

_api_key: str | None = None
_expires_at: float = 0


def get_api_client() -> pluggy_sdk.ApiClient:
    global _api_key, _expires_at

    if _api_key is None or time.time() >= _expires_at:
        client_id = os.getenv("PLUGGY_CLIENT_ID")
        client_secret = os.getenv("PLUGGY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError("PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET não configurados")

        config = pluggy_sdk.Configuration(host="https://api.pluggy.ai")
        with pluggy_sdk.ApiClient(config) as ac:
            resp = pluggy_sdk.AuthApi(ac).auth_create(
                pluggy_sdk.AuthRequest(clientId=client_id, clientSecret=client_secret)
            )
        _api_key = resp.api_key
        _expires_at = time.time() + 90 * 60  # API key dura 2h; renova com 30min de folga

    config = pluggy_sdk.Configuration(
        host="https://api.pluggy.ai",
        api_key={"X-API-KEY": _api_key},
    )
    client = pluggy_sdk.ApiClient(config)
    client.default_headers["X-API-KEY"] = _api_key
    return client
