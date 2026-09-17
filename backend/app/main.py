import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.endpoints.bank_accounts import router as bank_accounts_router
from app.api.endpoints.budgets import router as budgets_router
from app.api.endpoints.categories import router as categories_router
from app.api.endpoints.category_rules import router as category_rules_router
from app.api.endpoints.credit_card_bills import router as credit_card_bills_router
from app.api.endpoints.jobs import router as jobs_router
from app.api.endpoints.payables import router as payables_router
from app.api.endpoints.push_subscriptions import router as push_subscriptions_router
from app.api.endpoints.recurring_payables import router as recurring_payables_router
from app.api.endpoints.insights import router as insights_router
from app.api.endpoints.summary import router as summary_router
from app.api.endpoints.transactions import router as transactions_router
from app.api.endpoints.webhooks import router as webhooks_router
from app.core.config import settings
from app.core.observability import configure_logging, init_sentry
from app.core.users import auth_backend, fastapi_users
from app.db.database import SessionLocal
from app.schemas.user import UserCreate, UserRead, UserUpdate

configure_logging()
init_sentry()

logging.getLogger(__name__).info("LifeOS API iniciando: environment=%s", settings.environment)

app = FastAPI(title="Controle Financeiro Pessoal API")

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


app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["Auth"]
)
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
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("readiness check falhou: banco indisponível")
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok"}
