"""Mede latência real de endpoints GET contra um backend já rodando (produção
por padrão) — issue #23 P3. **Atenção**: `reconciliation-suggestions` chama
`auto_reconcile_confident_matches` internamente e pode marcar payables como
pagos — não é leitura pura (issue #126).

    cd backend
    export LIFEOS_TOKEN=<access_token de /auth/jwt/login>
    python -m scripts.perf_probe
    python -m scripts.perf_probe --base-url http://localhost:8000 --runs 5

Reporta o 1º hit (cold, útil pra ver o efeito de hibernação do Render) e
p50/p95/max das repetições seguintes por endpoint, além de decompor `p50`
em servidor vs. rede usando o header `X-Response-Time-Ms` (issue #125) —
sem essa decomposição, "está lento" não diz se o gargalo é código, banco ou
só a distância até o Render.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import date

import requests

_DEFAULT_BASE_URL = "https://lifeos-backend-sa9n.onrender.com"


def _endpoints(today: date) -> list[tuple[str, str]]:
    month_year = f"month={today.month}&year={today.year}"
    return [
        ("health", "/"),
        ("payables", f"/payables?{month_year}"),
        ("categories", "/categories"),
        ("summary", f"/summary?{month_year}"),
        ("bank-accounts", "/bank-accounts"),
        ("credit-card-bills", f"/credit-card-bills?{month_year}"),
        ("reconciliation-suggestions", "/bank-accounts/reconciliation-suggestions"),
        ("recurring-suggestions", "/recurring-payables/suggestions"),
    ]


def _timed_get(
    session: requests.Session, base_url: str, path: str
) -> tuple[float, float | None, int]:
    """Retorna (total_ms, server_ms, status). `server_ms` é `None` quando o
    backend não manda `X-Response-Time-Ms` (versão antiga, ou request que
    nem chegou a gerar resposta)."""
    start = time.perf_counter()
    response = session.get(f"{base_url}{path}", timeout=30)
    total_ms = (time.perf_counter() - start) * 1000
    server_header = response.headers.get("X-Response-Time-Ms")
    server_ms = float(server_header) if server_header is not None else None
    return total_ms, server_ms, response.status_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    parser.add_argument("--runs", type=int, default=8, help="repetições após o hit cold")
    args = parser.parse_args()

    token = os.environ.get("LIFEOS_TOKEN")
    if not token:
        print("Faltando LIFEOS_TOKEN no ambiente.", file=sys.stderr)
        print(
            "Gerar: curl -X POST '<base-url>/auth/jwt/login' "
            "-d 'username=<email>&password=<senha>' | jq -r .access_token",
            file=sys.stderr,
        )
        return 1

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"

    print(f"Base URL: {args.base_url}")
    print(f"{args.runs} repetições por endpoint, após 1 hit cold\n")

    header = (
        f"{'endpoint':<28} {'cold':>7} {'p50':>7} {'p95':>7} {'max':>7} "
        f"{'p50 srv':>9} {'p50 rede':>9}  status"
    )
    print(header)
    print("-" * len(header))

    exit_code = 0
    for name, path in _endpoints(date.today()):
        cold_total, _cold_server, cold_status = _timed_get(session, args.base_url, path)
        if cold_status >= 400:
            print(f"{name:<28} {'ERRO':>7}  status={cold_status}")
            exit_code = 1
            continue

        # (total, server) pareados por request, antes de qualquer sort — a
        # rede de um request é `total - server` *daquele mesmo* request, não
        # dá pra subtrair percentis calculados de listas ordenadas separadamente.
        records: list[tuple[float, float | None]] = []
        last_status = cold_status
        for _ in range(args.runs):
            total_ms, server_ms, status = _timed_get(session, args.base_url, path)
            records.append((total_ms, server_ms))
            last_status = status

        totals = sorted(t for t, _ in records)
        p50 = statistics.median(totals)
        p95 = totals[int(0.95 * (len(totals) - 1))]
        worst = totals[-1]

        servers = sorted(s for _, s in records if s is not None)
        networks = sorted(t - s for t, s in records if s is not None)
        if servers:
            server_col = f"{statistics.median(servers):>9.0f}"
            network_col = f"{statistics.median(networks):>9.0f}"
        else:
            server_col = f"{'n/a':>9}"
            network_col = f"{'n/a':>9}"

        print(
            f"{name:<28} {cold_total:>7.0f} {p50:>7.0f} {p95:>7.0f} {worst:>7.0f} "
            f"{server_col} {network_col}  {last_status}"
        )
        if last_status >= 400:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
