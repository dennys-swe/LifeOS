# CLAUDE.md

Este arquivo orienta o Claude Code (claude.ai/code) ao trabalhar neste repositório.

## Visão Geral do Projeto

LifeOS é um SPA de gestão financeira pessoal (contas a pagar, transações, orçamento por categoria). Stack: FastAPI no backend e React + Vite + Tailwind CSS v4 no frontend. Infraestrutura de produção: PostgreSQL no Neon.tech, backend no Render, frontend na Vercel.

## Comandos

### Backend

```bash
# Servidor de desenvolvimento
uvicorn app.main:app --reload

# Rodar todos os testes
cd backend && pytest

# Rodar um arquivo de teste específico
cd backend && pytest tests/test_recurring.py

# Rodar um teste por nome
cd backend && pytest tests/test_recurring.py -k "test_generate_no_duplicate"

# Aplicar migrations
cd backend && alembic upgrade head

# Criar nova migration
cd backend && alembic revision --autogenerate -m "descricao"
```

O backend exige um arquivo `backend/.env` com `DATABASE_URL`. Testes usam SQLite em memória — sem necessidade de banco real.

Para push notifications em produção, adicionar ao `.env`:
```
VAPID_PRIVATE_KEY=<chave privada PEM>
VAPID_PUBLIC_KEY=<chave pública base64url>
VAPID_CLAIMS_EMAIL=mailto:dennysalvescontato@gmail.com
```

### Frontend

```bash
cd frontend && npm run dev    # servidor de desenvolvimento
cd frontend && npm test       # vitest
cd frontend && npm run lint   # eslint
cd frontend && npm run build  # build de produção
```

O frontend lê `VITE_API_URL` do ambiente (padrão: `http://localhost:8000`).

## Arquitetura

### Backend (`backend/`)

Camadas FastAPI seguindo o padrão: **Router → Service → SQLAlchemy ORM → PostgreSQL**.

- `app/main.py` — setup do app, CORS e registro de todos os routers. A rota raiz usa `@app.api_route` para suportar HEAD (uptime monitoring).
- `app/api/endpoints/` — handlers finos: validam, chamam o service e retornam.
- `app/services/` — lógica de negócio. Cada domínio tem seu service (`recurring_service`, `reconciliation_service`, `summary_service`, etc.).
- `app/models/` — ORM SQLAlchemy.
- `app/schemas/` — schemas Pydantic v2 (usar `model_dump`, `ConfigDict`, `from_attributes=True`).
- `app/db/database.py` — engine + session factory. SSL automático para PostgreSQL. `get_db()` é a dependency FastAPI.
- `alembic/versions/` — migrations em ordem cronológica.

**Testes** (`backend/tests/`) usam `pytest` com SQLite em memória via `conftest.py` que sobrescreve a dependency `get_db` com `TestClient`.

**Compatibilidade SQLite:** `summary_service` agrega em Python (não SQL `GROUP BY`) para funcionar nos testes. Nunca usar `func.date_trunc` ou funções PostgreSQL-only nos services.

**Ordem de registro de rotas:** endpoints com path literal (ex: `/generate`, `/upcoming`, `/notify`) devem ser registrados **antes** de `/{id}` para evitar que o FastAPI interprete strings como UUIDs.

### Frontend (`frontend/src/`)

SPA com roteamento manual via estado `activePage` em `App.jsx` (sem React Router).

- `App.jsx` — componente raiz. Gerencia `activePage`, `payablesFilter`, `selectedMonth`, `selectedYear`. Envolve as páginas com `FinanceProvider`.
- `context/FinanceContext.jsx` — estado global compartilhado. Faz 3 chamadas em paralelo (`/payables`, `/categories`, `/summary`) e expõe `payables`, `categories`, `summary`, `loading`, `refresh()`. Re-dispara quando `month`, `year` ou `refreshKey` mudam.
- `pages/PayablesPage.jsx` — lista de contas com filtros, exclusão otimista com undo via toast.
- `pages/RecurringPayablesPage.jsx` — CRUD de recorrentes + botão "Gerar para este mês".
- `pages/CategoryRulesPage.jsx` — gerenciamento de regras de categorização (keyword, categoria, prioridade).
- `pages/UploadPage.jsx` — upload de extrato CSV + UI de revisão de sugestões de conciliação.
- `pages/ConnectionPage.jsx` — dashboard com cards de saldo, barras de orçamento por categoria e gráfico.
- `components/FabModal.jsx` — FAB que abre modal para criar payable ou transação.
- `components/Navbar.jsx` — badge vermelho com contagem de contas vencendo em ≤7 dias.

**Invariante de datas:** `due_date` trafega e é armazenada como string `YYYY-MM-DD`. **Nunca** construir `new Date(due_date)` — o GMT offset desloca a data um dia. Sempre usar `.split('-')`, `localeCompare` ou comparação direta de strings.

**Exclusão com Undo:** remoção é otimista — item sai do estado imediatamente e um `setTimeout` de 5s dispara o `DELETE` real. O botão "Desfazer" no Toast cancela o timeout e restaura o item sem chamada de API.

**Estado compartilhado:** nunca buscar `/payables` ou `/categories` diretamente dentro de páginas. Usar `useFinance()` do FinanceContext. Chamar `refresh()` após qualquer mutação (create, update, delete, pay).

### Modelos e Domínios

| Modelo | Descrição |
|---|---|
| `Payable` | Conta a pagar. FKs nullable: `recurring_payable_id` (ondelete=SET NULL), `transaction_id` (ondelete=SET NULL) |
| `RecurringPayable` | Template de recorrência (title, amount, day_of_month, active) |
| `Transaction` | Transação de extrato bancário |
| `Category` | Categoria com cor (color_hex) |
| `CategoryRule` | Regra de categorização por keyword (armazenada em UPPERCASE) |
| `Budget` | Orçamento mensal por categoria. UniqueConstraint(category_id, month, year) |
| `BankAccount` | Conta bancária (estrutura base; sync retorna 501) |
| `PushSubscription` | Subscription VAPID para push notifications |

### Lógica de Negócio Crítica

**`generate_for_month` (recurring_service):** para cada `RecurringPayable` ativo, calcula `due_date = date(year, month, min(day_of_month, last_day_of_month))` e cria um `Payable` somente se ainda não existir um com mesmo `recurring_payable_id` no mês (deduplicação).

**`build_keyword_map` (category_rule_service):** retorna `dict[keyword, category_id]` ordenado por `priority DESC`. Usa first-occurrence para preservar a prioridade mais alta quando há duplicatas de keyword.

**`suggest_reconciliation` (reconciliation_service):** para cada transação EXPENSE do upload, busca payables PENDING com `amount` dentro de 5% e `due_date` dentro de ±7 dias. Confidence scoring: 1.0 (exato), 0.8 (valor exato, data ±7d), 0.6 (valor ±5%, data exata), 0.5 (ambos tolerantes).

### Endpoints da API

| Método | Path | Descrição |
|--------|------|-----------|
| `GET/HEAD` | `/` | Health check |
| `GET` | `/payables?month=&year=` | Lista payables do mês |
| `POST` | `/payables` | Cria payable |
| `PUT` | `/payables/{id}` | Atualiza payable |
| `PATCH` | `/payables/{id}/reconcile?transaction_id=` | Concilia com transação (marca como pago) |
| `DELETE` | `/payables/{id}` | Remove payable |
| `GET` | `/payables/upcoming?days=7` | Payables PENDING vencendo nos próximos N dias |
| `GET/POST/DELETE` | `/recurring-payables` | CRUD de recorrentes |
| `POST` | `/recurring-payables/generate?month=&year=` | Gera payables do mês a partir dos recorrentes |
| `POST` | `/transactions/upload` | Upload CSV; retorna `{transactions, suggestions}` |
| `GET/POST/DELETE` | `/transactions` | CRUD de transações |
| `GET/POST/DELETE` | `/categories` | CRUD de categorias |
| `GET/POST/DELETE` | `/category-rules` | CRUD de regras de categorização |
| `GET` | `/summary?month=&year=` | Totais + by_category + budget_used_pct |
| `GET/POST/DELETE` | `/budgets?month=&year=` | CRUD de orçamentos |
| `GET/POST/DELETE` | `/bank-accounts` | CRUD de contas bancárias |
| `POST` | `/bank-accounts/{id}/sync` | Sync bancário (501 — não implementado) |
| `POST` | `/push-subscriptions` | Salva subscription VAPID |
| `POST` | `/push-subscriptions/notify` | Dispara push para contas vencendo em breve |
