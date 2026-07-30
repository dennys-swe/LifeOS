import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import CategoryDot from "../components/ui/CategoryDot";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import MonthNavigator from "../components/MonthNavigator";
import Skeleton from "../components/ui/Skeleton";
import { useFinance } from "../context/FinanceContext";
import { fmt, fmtDate } from "../lib/format";
import { UNCATEGORIZED_SLUG } from "../lib/routes";
import api from "../services/api";

const UNCATEGORIZED_COLOR = "#64748B";

export default function CategoryDetailPage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { categories } = useFinance();

  const isUncategorized = id === UNCATEGORIZED_SLUG;
  const month = Number(searchParams.get("month")) || new Date().getMonth() + 1;
  const year = Number(searchParams.get("year")) || new Date().getFullYear();

  const requestKey = `${id}:${month}:${year}`;
  const [result, setResult] = useState(null);

  useEffect(() => {
    const params = {
      month,
      year,
      type: "EXPENSE",
      include_transfers: false,
      limit: 500,
    };
    if (isUncategorized) {
      params.uncategorized = true;
    } else {
      params.category_id = id;
    }
    api.get("/transactions", { params })
      .then((r) => setResult({ key: requestKey, data: r.data ?? [], error: false }))
      .catch(() => setResult({ key: requestKey, data: [], error: true }));
  }, [id, isUncategorized, month, year, requestKey]);

  const loading = result?.key !== requestKey;
  const transactions = loading ? null : result.data;
  const error = !loading && result.error;

  const category = useMemo(
    () => categories.find((c) => c.id === id),
    [categories, id]
  );
  const name = isUncategorized ? "Sem categoria" : category?.name ?? "Categoria";
  const color = isUncategorized ? UNCATEGORIZED_COLOR : category?.color_hex ?? UNCATEGORIZED_COLOR;

  const total = useMemo(
    () => (transactions ?? []).reduce((s, t) => s + Number(t.amount), 0),
    [transactions]
  );

  function handleMonthChange(m, y) {
    setSearchParams({ month: String(m), year: String(y) });
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
        <div>
          <Link
            to="/"
            className="font-display text-xs font-bold uppercase tracking-widest text-slate-400 hover:text-emerald-500 transition-colors dark:text-slate-500"
          >
            ← Voltar ao Dashboard
          </Link>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <CategoryDot color={color} className="h-4 w-4" />
              <h1 className="font-display text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">{name}</h1>
            </div>
            <MonthNavigator month={month} year={year} onChange={handleMonthChange} />
          </div>
        </div>

        <Card className="p-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Total Gasto no Mês
          </p>
          <p className="mt-2 font-display text-3xl font-extrabold text-slate-900 dark:text-white">
            {transactions === null ? <Skeleton className="h-9 w-40" /> : fmt(total)}
          </p>
        </Card>

        <Card className="p-4">
          {transactions === null ? (
            <div className="flex flex-col gap-2 p-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : error ? (
            <EmptyState className="py-8">Não foi possível carregar as transações.</EmptyState>
          ) : transactions.length === 0 ? (
            <EmptyState className="py-8">Nenhuma transação nesta categoria no mês.</EmptyState>
          ) : (
            <div className="flex flex-col gap-2">
              {transactions.map((t) => (
                <div key={t.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/50 p-3.5 dark:border-slate-800/40 dark:bg-slate-900/40">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-slate-900 dark:text-white">
                      {t.description}
                    </p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">{fmtDate(t.date)}</p>
                  </div>
                  <span className="font-display text-sm font-bold text-slate-900 dark:text-white">
                    {fmt(t.amount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
