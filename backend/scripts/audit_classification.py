"""Auditoria de classificação, somente leitura por padrão (#199, #169).

    cd backend
    python -m scripts.audit_classification                      # todos os usuários ativos
    python -m scripts.audit_classification --user dono@x.com    # e-mail ou UUID
    python -m scripts.audit_classification --days 180
    python -m scripts.audit_classification --apply              # grava em data_quality_issues

Sem `--apply` não escreve nada: só imprime o que a auditoria acharia e o resíduo sem
categoria. Com `--apply`, grava/atualiza `data_quality_issues` (idempotente). **Nunca altera
transações.** Contra produção é preciso `ALLOW_PROD_DB=1` (guard de `app/db/database.py`) e
confirmar antes o host com o `DATABASE_URL` do Render.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from uuid import UUID

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.user import User
from app.services import data_quality_service as dq

_LABELS = {
    dq.SYSTEM_SAYS_TRANSFER: "Regra do sistema diria transferência, mas não está marcada",
    dq.UNLINKED_REVERSAL: "Crédito que anula cobrança, sem vínculo",
    dq.UNMARKED_MIRROR: "Par entrada/saída de mesmo valor sem marcação completa",
    dq.LARGE_UNUSUAL_INCOME: "Entrada grande fora do padrão e sem categoria de renda",
    dq.UNCATEGORIZED_EXPENSE: "Despesa sem categoria",
}


def _resolve_users(db, ident: str | None) -> list[User]:
    if ident is None:
        return list(db.execute(select(User).where(User.is_active.is_(True))).scalars())
    try:
        stmt = select(User).where(User.id == UUID(ident))
    except ValueError:
        stmt = select(User).where(User.email == ident)
    user = db.execute(stmt).scalar_one_or_none()
    if user is None:
        sys.exit(f"usuário não encontrado: {ident}")
    return [user]


def _print_user(user: User, result: dq.AuditResult, days: int) -> None:
    r = result.residual
    print(f"\n=== {user.email} (últimos {days} dias, {len(result.audited_ids)} transações) ===")
    print(
        f"Resíduo: {r.uncategorized_count} de {r.expenses_count} despesas sem categoria "
        f"({r.uncategorized_pct_count}% das linhas, {r.uncategorized_pct_amount}% do valor)"
    )
    print(
        f"Sem classification_source: {r.without_classification_source} · "
        f"sem external_category: {r.without_external_category}"
    )
    for desc, n, amount in r.top_uncategorized[:5]:
        print(f"   · {desc[:40]:<40} {n:>3}x  R$ {amount}")

    counts = Counter(f.kind for f in result.findings)
    if not counts:
        print("Nenhuma suspeita de classificação.")
        return
    for kind in dq.ALL_KINDS:
        if counts[kind] == 0:
            continue
        print(f"\n[{dq.SEVERITY[kind].upper()}] {_LABELS[kind]}: {counts[kind]}")
        for f in [x for x in result.findings if x.kind == kind][:8]:
            d = f.detail
            label = d.get("description") or d.get("expense") or d.get("credit") or ""
            print(f"   {d.get('date', '')}  R$ {d.get('amount', ''):>9}  {str(label)[:45]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--user", help="e-mail ou UUID (padrão: todos os ativos)")
    parser.add_argument("--days", type=int, default=dq.DEFAULT_WINDOW_DAYS)
    parser.add_argument("--apply", action="store_true", help="grava em data_quality_issues")
    args = parser.parse_args()

    with SessionLocal() as db:
        for user in _resolve_users(db, args.user):
            result = dq.run_audit(db, user.id, days=args.days)
            _print_user(user, result, args.days)
            if args.apply:
                stats = dq.persist_findings(db, user.id, result.findings, result.audited_ids)
                db.commit()
                print(f"\nGravado: {stats}")
        if not args.apply:
            print("\n(dry-run: nada foi gravado; use --apply para gravar os achados)")


if __name__ == "__main__":
    main()
