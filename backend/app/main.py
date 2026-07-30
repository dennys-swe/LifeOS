from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.core.users import auth_backend, fastapi_users
from app.schemas.user import UserCreate, UserRead, UserUpdate

app = FastAPI(title="Controle Financeiro Pessoal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok"}
