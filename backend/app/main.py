import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.endpoints.bank_accounts import router as bank_accounts_router
from app.api.endpoints.budgets import router as budgets_router
from app.api.endpoints.categories import router as categories_router
from app.api.endpoints.category_rules import router as category_rules_router
from app.api.endpoints.credit_card_bills import router as credit_card_bills_router
from app.api.endpoints.insights import router as insights_router
from app.api.endpoints.jobs import router as jobs_router
from app.api.endpoints.payables import router as payables_router
from app.api.endpoints.push_subscriptions import router as push_subscriptions_router
from app.api.endpoints.recurring_payables import router as recurring_payables_router
from app.api.endpoints.summary import router as summary_router
from app.api.endpoints.transactions import router as transactions_router
from app.api.endpoints.webhooks import router as webhooks_router
from app.core.config import settings
from app.core.observability import configure_logging, init_sentry
from app.core.rate_limit import RateLimitMiddleware
from app.core.users import auth_backend, fastapi_users
from app.db.database import SessionLocal
from app.schemas.user import UserCreate, UserRead, UserUpdate

configure_logging()
init_sentry()

logging.getLogger(__name__).info("LifeOS API iniciando: environment=%s", settings.environment)

app = FastAPI(title="Controle Financeiro Pessoal API")

# Adicionado antes do CORS: o CORS precisa envolver o rate limit (ordem de
# execução no Starlette é LIFO por ordem de `add_middleware`) pra uma
# resposta 429 ainda sair com os headers de CORS — senão o frontend não
# consegue nem ler o corpo do erro.
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    # Só os verbos e headers que o frontend de fato usa (era "*"/"*").
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    # CSP fica de fora de /docs e /redoc: a UI do Swagger precisa de script
    # inline/CDN para renderizar. No resto (só JSON), "default-src 'none'"
    # não quebra nada e fecha a superfície pra quem abrir a API no navegador.
    if request.url.path not in ("/docs", "/redoc"):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


_timing_logger = logging.getLogger("app.timing")


@app.middleware("http")
async def request_timing(request: Request, call_next):
    """Loga duração de cada request — issue #23 P3 (perfil de latência com
    dado real). Registrado por último (= middleware mais externo, ver
    comentário do RateLimitMiddleware acima) pra medir o tempo total
    observado pelo cliente, CORS/rate limit/rota inclusos.
    """
    start = time.perf_counter()
    status_code = "ERR"
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        # `finally` em vez de só depois do `await`: uma exceção não tratada
        # que escapa de `call_next` (timeout, crash) não pode sumir do log
        # de timing — são justamente os requests mais lentos que o perfil
        # de latência precisa capturar.
        duration_ms = (time.perf_counter() - start) * 1000
        level = (
            logging.WARNING if duration_ms >= settings.slow_request_threshold_ms else logging.INFO
        )
        _timing_logger.log(
            level,
            "%s %s -> %s %.0fms",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )


app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["Auth"])
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["Auth"]
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["Users"]
)

app.include_router(payables_router)
app.include_router(recurring_payables_router)
app.include_router(transactions_router)
app.include_router(categories_router)
app.include_router(category_rules_router)
app.include_router(summary_router)
app.include_router(insights_router)
app.include_router(budgets_router)
app.include_router(bank_accounts_router)
app.include_router(credit_card_bills_router)
app.include_router(push_subscriptions_router)
app.include_router(jobs_router)
app.include_router(webhooks_router)


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    """Readiness check: testa o banco, não só o processo. Uptime monitoring
    (HEAD) e humano (GET) usam a mesma rota."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        # Amplo de propósito: qualquer falha aqui (timeout, connection reset,
        # erro de driver) significa a mesma coisa — "não está pronto" — e
        # nenhuma delas deve virar 500 não tratado num health check.
        logging.getLogger(__name__).exception("readiness check falhou: banco indisponível")
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}
