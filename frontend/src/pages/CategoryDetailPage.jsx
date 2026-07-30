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

/** "Pra onde vai" no nível mais concreto: as transações de uma categoria num
 * mês, ordenadas por data. Chegou aqui a partir de um clique no dashboard
 * (barra de categoria ou card de insight). */
export default function CategoryDetailPage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { categories } = useFinance();

  const isUncategorized = id === UNCATEGORIZED_SLUG;
  const month = Number(searchParams.get("month")) || new Date().getMonth() + 1;
  const year = Number(searchParams.get("year")) || new Date().getFullYear();

  // `key` identifica a combinação categoria+mês do resultado guardado — não é
  // resetado sincronamente no efeito (o lint desaprova setState fora de um
  // callback assíncrono), então "carregando" é "o resultado guardado ainda não
  // é desta combinação", não uma flag reiniciada à parte.
  const requestKey = `${id}:${month}:${year}`;
  const [result, setResult] = useState(null);

  useEffect(() => {
    const params = {
      month,
      year,
      type: "EXPENSE", // + include_transfers=false = mesma definição de "gasto"
      include_transfers: false, // que o backend usa em CategorySummary.total_expenses
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
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-8">
        <div>
          <Link
            to="/"
            className="text-xs font-medium uppercase tracking-widest text-gray-400 hover:text-gray-600 dark:text-slate-500 dark:hover:text-slate-300"
          >
            ← Dashboard
          </Link>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <CategoryDot color={color} className="h-3.5 w-3.5" />
              <h1 className="text-2xl font-semibold text-gray-900 dark:text-slate-100">{name}</h1>
            </div>
            <MonthNavigator month={month} year={year} onChange={handleMonthChange} />
          </div>
        </div>

        <Card className="p-6">
          <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
            Total no mês
          </p>
          <p className="mt-2 text-3xl font-semibold text-gray-900 dark:text-slate-100">
            {transactions === null ? <Skeleton className="h-9 w-40" /> : fmt(total)}
          </p>
        </Card>

        <Card className="p-2">
          {transactions === null ? (
            <div className="flex flex-col gap-2 p-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : error ? (
            <EmptyState>Não foi possível carregar as transações.</EmptyState>
          ) : transactions.length === 0 ? (
            <EmptyState>Nenhuma transação nesta categoria no mês.</EmptyState>
          ) : (
            <div className="divide-y divide-gray-50 dark:divide-slate-800/60">
              {transactions.map((t) => (
                <div key={t.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-800 dark:text-slate-200">
                      {t.description}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-slate-500">{fmtDate(t.date)}</p>
                  </div>
                  <span className="flex-shrink-0 text-sm font-semibold text-gray-900 dark:text-slate-100">
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
