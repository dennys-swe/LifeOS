import { useEffect, useMemo, useState } from "react";
import api from "../services/api";
import MonthNavigator from "../components/MonthNavigator";
import Card from "../components/ui/Card";
import CategoryDot from "../components/ui/CategoryDot";
import EmptyState from "../components/ui/EmptyState";
import { useFinance } from "../context/FinanceContext";
import { fmt } from "../lib/format";

const TYPE_FILTERS = [
  { key: "all", label: "Todas" },
  { key: "EXPENSE", label: "Saídas" },
  { key: "INCOME", label: "Entradas" },
  { key: "TRANSFERS", label: "Transferências" },
];

export default function TransactionsPage({ month, year, onMonthChange }) {
  const { categories } = useFinance() ?? {};
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [hideTransfers, setHideTransfers] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const r = await api.get("/transactions", { params: { month, year } });
        if (mounted) setTransactions(r.data ?? []);
      } catch {
        if (mounted) setError("Falha ao carregar transações.");
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, [month, year]);

  const categoryMap = useMemo(() => {
    return new Map((categories ?? []).map((c) => [c.id, c]));
  }, [categories]);

  const filtered = useMemo(() => {
    let list = transactions;

    if (typeFilter === "TRANSFERS") {
      list = list.filter((t) => t.is_transfer);
    } else if (typeFilter !== "all") {
      list = list.filter((t) => t.type === typeFilter);
      if (hideTransfers) {
        list = list.filter((t) => !t.is_transfer);
      }
    } else if (hideTransfers) {
      list = list.filter((t) => !t.is_transfer);
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((t) => t.description.toLowerCase().includes(q));
    }
    return list.sort((a, b) => b.date.localeCompare(a.date));
  }, [transactions, typeFilter, hideTransfers, search]);

  const realExpensesSum = useMemo(
    () =>
      transactions
        .filter((t) => t.type === "EXPENSE" && !t.is_transfer)
        .reduce((s, t) => s + Number(t.amount), 0),
    [transactions]
  );

  const realIncomeSum = useMemo(
    () =>
      transactions
        .filter((t) => t.type === "INCOME" && !t.is_transfer)
        .reduce((s, t) => s + Number(t.amount), 0),
    [transactions]
  );

  const transfersSum = useMemo(
    () =>
      transactions
        .filter((t) => t.is_transfer)
        .reduce((s, t) => s + Number(t.amount), 0),
    [transactions]
  );

  const formatDate = (dateStr) => {
    const [y, m, d] = dateStr.split("-");
    return `${d}/${m}/${y}`;
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-8 md:py-8">

        {/* Header */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">Histórico de Lançamentos</p>
            <h1 className="mt-1 font-display text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Extrato de Transações</h1>
          </div>
          <MonthNavigator month={month} year={year} onChange={onMonthChange} />
        </header>

        {/* Summary Stat Cards */}
        <section className="grid gap-4 sm:grid-cols-4">
          <Card className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Total Registros</p>
            <p className="mt-2 font-display text-xl font-bold text-slate-900 dark:text-white">{filtered.length}</p>
          </Card>
          <Card className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Entradas Reais</p>
            <p className="mt-2 font-display text-xl font-bold text-emerald-600 dark:text-emerald-400">{fmt(realIncomeSum)}</p>
          </Card>
          <Card className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Gastos Reais</p>
            <p className="mt-2 font-display text-xl font-bold text-rose-600 dark:text-rose-400">{fmt(realExpensesSum)}</p>
          </Card>
          <Card className="p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Transferências</p>
            <p className="mt-2 font-display text-xl font-bold text-indigo-600 dark:text-indigo-400">{fmt(transfersSum)}</p>
          </Card>
        </section>

        {/* Filter Controls */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            {TYPE_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setTypeFilter(f.key)}
                className={`rounded-full px-4 py-1.5 font-display text-xs font-bold transition ${
                  typeFilter === f.key
                    ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                    : "border border-slate-200/80 bg-white text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                }`}
              >
                {f.label}
              </button>
            ))}

            {typeFilter !== "TRANSFERS" && (
              <label className="ml-2 flex items-center gap-1.5 text-xs font-semibold text-slate-500 cursor-pointer dark:text-slate-400">
                <input
                  type="checkbox"
                  checked={hideTransfers}
                  onChange={(e) => setHideTransfers(e.target.checked)}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800"
                />
                Ocultar transferências
              </label>
            )}
          </div>

          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por descrição..."
            className="w-full rounded-2xl border border-slate-200/80 bg-white px-4 py-2 text-xs font-medium text-slate-900 placeholder-slate-400 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:placeholder-slate-500 sm:w-72"
          />
        </div>

        {/* List */}
        {error && <p className="text-xs font-bold text-rose-500">{error}</p>}

        {loading ? (
          <div className="flex h-40 items-center justify-center text-xs font-bold text-slate-400">Carregando extrato...</div>
        ) : filtered.length === 0 ? (
          <EmptyState className="h-auto py-12">Nenhuma transação encontrada para este filtro.</EmptyState>
        ) : (
          <Card className="p-4 flex flex-col gap-2">
            {filtered.map((t) => {
              const cat = t.category_id ? categoryMap.get(t.category_id) : null;
              return (
                <div
                  key={t.id}
                  className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3.5 transition-all hover:bg-slate-100/60 dark:border-slate-800/40 dark:bg-slate-900/40 dark:hover:bg-slate-800/40"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    {cat ? (
                      <CategoryDot color={cat.color_hex} />
                    ) : (
                      <span className="h-2.5 w-2.5 flex-shrink-0 rounded-full bg-slate-300 dark:bg-slate-700" />
                    )}

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-bold text-slate-900 dark:text-white">{t.description}</p>
                        {t.is_transfer && (
                          <span
                            title="Transferência entre contas / aporte — não conta no gasto do mês"
                            className="inline-flex items-center gap-1 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-bold text-indigo-600 dark:text-indigo-300"
                          >
                            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M3 7.5 7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5" />
                            </svg>
                            Transferência
                          </span>
                        )}
                      </div>

                      <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                        <span>{formatDate(t.date)}</span>
                        {cat && (
                          <span
                            className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                            style={{ color: cat.color_hex, backgroundColor: `${cat.color_hex}15` }}
                          >
                            {cat.name}
                          </span>
                        )}
                        {t.external_category && !cat && (
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                            {t.external_category}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="ml-4 flex flex-shrink-0 flex-col items-end gap-1">
                    <p className={`font-display text-sm font-bold ${
                      t.is_transfer
                        ? "text-indigo-600 dark:text-indigo-400"
                        : t.type === "INCOME"
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-rose-600 dark:text-rose-400"
                    }`}>
                      {t.type === "INCOME" ? "+" : "−"}{fmt(Number(t.amount))}
                    </p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                      t.is_transfer
                        ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-300"
                        : t.type === "INCOME"
                        ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                        : "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                    }`}>
                      {t.is_transfer ? "Transferência" : t.type === "INCOME" ? "Entrada" : "Saída"}
                    </span>
                  </div>
                </div>
              );
            })}
          </Card>
        )}

      </div>
    </div>
  );
}
