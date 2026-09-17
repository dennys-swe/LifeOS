from __future__ import annotations

import time

from fastapi import Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

# Login/registro levam um limite agressivo (alvo: brute force e criação de
# contas em massa); o resto das rotas leva um limite brando só pra conter
# abuso grosseiro. Webhook e job de sync já são protegidos por segredo
# próprio (path secret / X-Cron-Secret) e o health check é batido por
# monitoramento de uptime — nenhum dos três entra no limite brando.
_AUTH_PATHS = {("/auth/jwt/login", "POST"), ("/auth/register", "POST")}
_EXEMPT_PREFIXES = ("/webhooks", "/jobs", "/docs", "/redoc", "/openapi.json")

AUTH_LIMIT = parse("5/minute")
DEFAULT_LIMIT = parse("100/minute")

storage = MemoryStorage()
limiter = MovingWindowRateLimiter(storage)


def get_client_ip(request: Request) -> str:
    """IP real do cliente atrás do proxy do Render.

    `request.client.host` é o IP do proxy reverso, não do cliente — o real
    vem em `X-Forwarded-For` (primeiro da lista). Sem o header (dev local,
    ou teste), cai no host da conexão direta.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ENVIRONMENT=test é o valor fixado por tests/conftest.py antes de
        # importar app.* — desliga o limite pra não poluir o resto da suíte
        # (mesma IP sintética do TestClient em centenas de requests). O
        # próprio teste do rate limit religa via monkeypatch.
        if settings.environment == "test":
            return await call_next(request)
        if request.url.path == "/" or request.url.path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        ip = get_client_ip(request)
        is_auth = (request.url.path, request.method) in _AUTH_PATHS
        limit = AUTH_LIMIT if is_auth else DEFAULT_LIMIT
        # Bucket por path pra login e registro não brigarem pela mesma cota.
        key = f"auth:{request.url.path}:{ip}" if is_auth else f"default:{ip}"

        if not limiter.hit(limit, key):
            stats = limiter.get_window_stats(limit, key)
            retry_after = max(1, int(stats.reset_time - time.time()))
            return JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
