"""Logging e Sentry — configurados uma vez, nos dois pontos de entrada.

`app.main` (servidor) e `app.jobs.daily_sync` (CLI) chamam `configure_logging()`
e `init_sentry()` no import/startup. Ambos são idempotentes e no-op quando não
há o que configurar, então a suíte de testes roda sem tocar em nada disso.
"""

from __future__ import annotations

import logging

from app.core.config import settings

_logging_configured = False
_sentry_configured = False


def configure_logging() -> None:
    """Configura o handler e o nível do logger raiz. Idempotente."""
    global _logging_configured
    if _logging_configured:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Adiciona o nosso handler só se ninguém já pôs um (uvicorn, pytest) —
    # `basicConfig` seria no-op nesse caso e o nível não pegaria.
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        root.addHandler(handler)

    _logging_configured = True


def init_sentry() -> None:
    """Inicializa o Sentry só quando `SENTRY_DSN` está setado.

    Sem DSN é no-op: desenvolvimento local e o CI não precisam de conta no
    Sentry. Com a integração de logging padrão do SDK, todo `logger.error` /
    `logger.exception` do backend vira um evento no Sentry sem chamada
    explícita de `capture_exception`.
    """
    global _sentry_configured
    if _sentry_configured or not settings.sentry_dsn:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        # Só rastreio de erros por enquanto — sem performance tracing.
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
    _sentry_configured = True
