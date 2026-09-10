#!/usr/bin/env bash
# Prepara o ambiente de desenvolvimento local do zero.
#
#   docker compose up -d db      # (na raiz do repo) sobe o Postgres de dev
#   cd backend && ./scripts/dev_bootstrap.sh
#
# Espera o banco, aplica as migrations e popula com dados de dev.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "backend/.env não existe. Copie de .env.example e ajuste." >&2
  exit 1
fi

echo "==> aguardando o Postgres de dev..."
for i in $(seq 1 30); do
  if docker compose -f ../docker-compose.yml exec -T db pg_isready -U lifeos -d lifeos_dev >/dev/null 2>&1; then
    break
  fi
  sleep 1
  [ "$i" = 30 ] && { echo "banco não respondeu — 'docker compose up -d db' rodou?" >&2; exit 1; }
done

echo "==> alembic upgrade head"
alembic upgrade head

echo "==> seed"
python -m scripts.seed_dev "$@"

echo "==> pronto. uvicorn app.main:app --reload"
