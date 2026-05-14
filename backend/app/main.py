from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints.bank_accounts import router as bank_accounts_router
from app.api.endpoints.budgets import router as budgets_router
from app.api.endpoints.categories import router as categories_router
from app.api.endpoints.category_rules import router as category_rules_router
from app.api.endpoints.payables import router as payables_router
from app.api.endpoints.push_subscriptions import router as push_subscriptions_router
from app.api.endpoints.recurring_payables import router as recurring_payables_router
from app.api.endpoints.summary import router as summary_router
from app.api.endpoints.transactions import router as transactions_router

app = FastAPI(title="Controle Financeiro Pessoal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payables_router)
app.include_router(recurring_payables_router)
app.include_router(transactions_router)
app.include_router(categories_router)
app.include_router(category_rules_router)
app.include_router(summary_router)
app.include_router(budgets_router)
app.include_router(bank_accounts_router)
app.include_router(push_subscriptions_router)


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "ok"}
