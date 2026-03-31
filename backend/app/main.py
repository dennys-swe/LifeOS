from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints.categories import router as categories_router
from app.api.endpoints.payables import router as payables_router
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
app.include_router(transactions_router)
app.include_router(categories_router)


@app.get("/", methods=["GET", "HEAD"])
def root():
    return {"status": "ok"}
