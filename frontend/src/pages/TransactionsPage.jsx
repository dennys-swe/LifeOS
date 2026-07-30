import { useEffect, useMemo, useState } from "react";
import api from "../services/api";
import MonthNavigator from "../components/MonthNavigator";
import { fmt } from "../lib/format";

const TYPE_FILTERS = [
  { key: "all", label: "Todas" },
  { key: "EXPENSE", label: "Saídas" },
  { key: "INCOME", label: "Entradas" },
  { key: "TRANSFERS", label: "Transferências" },
];

export default function TransactionsPage({ month, year, onMonthChange }) {
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
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">

        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 dark:text-slate-500">Extrato</p>
            <h1 className="mt-1 text-2xl font-semibold text-gray-900 dark:text-slate-100">Transações</h1>
          </div>
          <MonthNavigator month={month} year={year} onChange={onMonthChange} />
        </header>

        {/* Summary cards */}
        <section className="grid gap-4 sm:grid-cols-4">
          <div className="rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xs text-gray-500 dark:text-slate-400">Total de registros</p>
            <p className="mt-1 text-xl font-semibold text-gray-900 dark:text-slate-100">{filtered.length}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xs text-gray-500 dark:text-slate-400">Entradas reais</p>
            <p className="mt-1 text-xl font-semibold text-emerald-600 dark:text-emerald-400">{fmt(realIncomeSum)}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xs text-gray-500 dark:text-slate-400">Gastos reais</p>
            <p className="mt-1 text-xl font-semibold text-rose-600 dark:text-rose-400">{fmt(realExpensesSum)}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xs text-gray-500 dark:text-slate-400">Transferências</p>
            <p className="mt-1 text-xl font-semibold text-indigo-600 dark:text-indigo-400">{fmt(transfersSum)}</p>
          </div>
        </section>

        {/* Filters */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            {TYPE_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setTypeFilter(f.key)}
                className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                  typeFilter === f.key
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
                    : "border border-gray-200 text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
                }`}
              >
                {f.label}
              </button>
            ))}

            {typeFilter !== "TRANSFERS" && (
              <label className="ml-2 flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer dark:text-slate-400">
                <input
                  type="checkbox"
                  checked={hideTransfers}
                  onChange={(e) => setHideTransfers(e.target.checked)}
                  className="rounded border-gray-300 text-emerald-600 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800"
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
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder-slate-500 sm:w-72"
          />
        </div>

        {/* List */}
        {error && <p className="text-sm text-rose-500 dark:text-rose-400">{error}</p>}

        {loading ? (
          <div className="flex h-40 items-center justify-center text-gray-400 dark:text-slate-400">Carregando...</div>
        ) : filtered.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-gray-200 text-gray-400 dark:border-slate-700 dark:text-slate-500">
            Nenhuma transação encontrada.
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {filtered.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between rounded-xl border border-gray-100 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900/60"
              >
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-medium text-gray-900 dark:text-slate-100">{t.description}</p>
                    {t.is_transfer && (
                      <span
                        title="Transferência entre contas / aporte — não conta no gasto do mês"
                        className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                      >
                        🔄 Transferência
                      </span>
                    )}
                  </div>
                  <div className="flex min-w-0 items-center gap-2">
                    <p className="flex-shrink-0 text-xs text-gray-400 dark:text-slate-500">{formatDate(t.date)}</p>
                    {t.external_category && (
                      <span className="max-w-[8rem] truncate rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500 dark:bg-slate-800 dark:text-slate-400">
                        {t.external_category}
                      </span>
                    )}
                  </div>
                </div>
                <div className="ml-4 flex flex-shrink-0 flex-col items-end gap-1">
                  <p className={`text-sm font-semibold ${
                    t.is_transfer
                      ? "text-indigo-600 dark:text-indigo-400"
                      : t.type === "INCOME"
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-rose-600 dark:text-rose-400"
                  }`}>
                    {t.type === "INCOME" ? "+" : "−"}{fmt(Number(t.amount))}
                  </p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    t.is_transfer
                      ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                      : t.type === "INCOME"
                      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                      : "bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300"
                  }`}>
                    {t.is_transfer ? "Transferência" : t.type === "INCOME" ? "Entrada" : "Saída"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}

