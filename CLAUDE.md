# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LifeOS is a personal finance management SPA (Contas a Pagar / payables tracker). It is a fullstack app with a FastAPI backend and a React + Vite + Tailwind CSS v4 frontend. Production infrastructure: PostgreSQL on Neon.tech, backend on Render, frontend on Vercel.

## Commands

### Backend

```bash
# Run the dev server (from the backend/ directory)
uvicorn app.main:app --reload

# Run all tests
cd backend && pytest

# Run a single test file
cd backend && pytest tests/test_api_payables.py

# Run a single test by name
cd backend && pytest tests/test_api_payables.py -k "test_create_payable"

# Apply database migrations
cd backend && alembic upgrade head

# Create a new migration
cd backend && alembic revision --autogenerate -m "description"
```

The backend requires a `.env` file at `backend/.env` with `DATABASE_URL`. Tests use an in-memory SQLite database — no real DB connection needed.

### Frontend

```bash
# Run the dev server (from the frontend/ directory)
cd frontend && npm run dev

# Run tests
cd frontend && npm test

# Lint
cd frontend && npm run lint

# Build for production
cd frontend && npm run build
```

Frontend reads `VITE_API_URL` from the environment (defaults to `http://localhost:8000`).

## Architecture

### Backend (`backend/`)

Layered FastAPI app following the pattern: **Router → Service → SQLAlchemy ORM → PostgreSQL**.

- `app/main.py` — FastAPI app setup, CORS, and router registration. The root `GET/HEAD /` route uses `@app.api_route` to support HEAD requests for uptime monitoring.
- `app/api/endpoints/` — Route handlers for `payables`, `transactions`, and `categories`. Handlers are thin: they validate, call a service function, and return.
- `app/services/` — Business logic. `payable_service.py` contains filtering, CRUD, and status helpers. `statement_parser.py` parses CSV bank statements.
- `app/models/` — SQLAlchemy ORM models (`Payable`, `Transaction`, `Category`).
- `app/schemas/` — Pydantic v2 schemas for request/response validation.
- `app/db/database.py` — Engine + session factory. Auto-requires SSL for PostgreSQL. `get_db()` is the FastAPI dependency.
- `alembic/` — Database migrations. The `versions/` directory has two migrations: initial schema and adding categories.

**Tests** (`backend/tests/`) use `pytest` with SQLite in-memory via `conftest.py` fixtures that override the `get_db` dependency with a `TestClient`.

### Frontend (`frontend/src/`)

Single-page app with manual client-side routing via `activePage` state in `App.jsx` (no React Router).

- `App.jsx` — Root component. Owns global state: `activePage`, `refreshKey`, `payablesFilter`, `selectedMonth`, `selectedYear`. Passes these down as props.
- `pages/PayablesPage.jsx` — Main view. Fetches payables and categories on mount. All date comparisons are done on ISO strings (e.g., `item.due_date.split('-')`, `localeCompare`) to avoid timezone-shifting bugs.
- `pages/UploadPage.jsx` — CSV bank statement upload flow.
- `pages/ConnectionPage.jsx` — Dashboard view.
- `components/FabModal.jsx` — Floating action button that opens a modal to create new payables.
- `services/api.js` — Axios instance; single source of truth for `VITE_API_URL`.

**Key invariant — date handling:** `due_date` is stored and transported as a plain `YYYY-MM-DD` string. Never construct a `Date` object from it; always use string operations (`.split('-')`, `localeCompare`, direct string comparison) to avoid GMT offset shifting dates by one day.

**Delete with Undo:** deletion is optimistic — the item is removed from state immediately and a `setTimeout` (5s) fires the real `DELETE` API call. The Toast's "Desfazer" button cancels the timeout and restores the item to local state without any API call.

### API Endpoints Summary

| Method | Path | Description |
|--------|------|-------------|
| `GET/HEAD` | `/` | Health check |
| `GET` | `/payables?month=&year=` | List payables, filtered by month/year |
| `POST` | `/payables` | Create payable |
| `PUT` | `/payables/{id}` | Update payable |
| `PATCH` | `/payables/{id}/pay` | Mark as paid (sets `status=PAID`, `payment_date=today`) |
| `DELETE` | `/payables/{id}` | Delete payable |
| `POST` | `/transactions/upload` | Upload CSV bank statement |
| `GET/POST/DELETE` | `/transactions` | Transaction CRUD |
| `GET/POST/DELETE` | `/categories` | Category CRUD |
