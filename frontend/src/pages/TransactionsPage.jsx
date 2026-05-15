import { useEffect, useMemo, useState } from "react";
import api from "../services/api";
import MonthNavigator from "../components/MonthNavigator";

const fmt = (value) =>
  Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const TYPE_FILTERS = [
  { key: "all", label: "Todas" },
  { key: "INCOME", label: "Entradas" },
  { key: "EXPENSE", label: "Saídas" },
];

export default function TransactionsPage({ month, year, onMonthChange }) {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
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
    if (typeFilter !== "all") list = list.filter((t) => t.type === typeFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((t) => t.description.toLowerCase().includes(q));
    }
    return list.sort((a, b) => b.date.localeCompare(a.date));
  }, [transactions, typeFilter, search]);

  const totalIncome = useMemo(
    () => filtered.filter((t) => t.type === "INCOME").reduce((s, t) => s + Number(t.amount), 0),
    [filtered]
  );
  const totalExpense = useMemo(
    () => filtered.filter((t) => t.type === "EXPENSE").reduce((s, t) => s + Number(t.amount), 0),
    [filtered]
  );

  const formatDate = (dateStr) => {
    const [y, m, d] = dateStr.split("-");
    return `${d}/${m}/${y}`;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 py-10">

        <header className="flex flex-col gap-3">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Extrato</p>
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <h1 className="text-3xl font-semibold text-white md:text-4xl">Transações</h1>
            <MonthNavigator month={month} year={year} onChange={onMonthChange} />
          </div>
        </header>

        {/* Mini cards de resumo */}
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-5 py-4">
            <p className="text-xs text-slate-400">Total de registros</p>
            <p className="mt-1 text-xl font-semibold text-white">{filtered.length}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-5 py-4">
            <p className="text-xs text-slate-400">Entradas</p>
            <p className="mt-1 text-xl font-semibold text-emerald-400">{fmt(totalIncome)}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-5 py-4">
            <p className="text-xs text-slate-400">Saídas</p>
            <p className="mt-1 text-xl font-semibold text-rose-400">{fmt(totalExpense)}</p>
          </div>
        </section>

        {/* Filtros */}
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2">
            {TYPE_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setTypeFilter(f.key)}
                className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
                  typeFilter === f.key
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "border border-slate-700 text-slate-300 hover:bg-slate-900"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por descrição..."
            className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-emerald-500 md:w-72"
          />
        </div>

        {/* Lista */}
        {error && <p className="text-sm text-rose-400">{error}</p>}

        {loading ? (
          <div className="flex h-40 items-center justify-center text-slate-400">Carregando...</div>
        ) : filtered.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-slate-700 text-slate-400">
            Nenhuma transação encontrada.
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {filtered.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3"
              >
                <div className="flex min-w-0 flex-col gap-0.5">
                  <p className="truncate text-sm font-medium text-white">{t.description}</p>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-slate-400">{formatDate(t.date)}</p>
                    {t.source && (
                      <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400">
                        {t.source}
                      </span>
                    )}
                  </div>
                </div>
                <div className="ml-4 flex flex-shrink-0 flex-col items-end gap-1">
                  <p className={`text-sm font-semibold ${t.type === "INCOME" ? "text-emerald-400" : "text-rose-400"}`}>
                    {t.type === "INCOME" ? "+" : "-"}{fmt(Number(t.amount))}
                  </p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    t.type === "INCOME"
                      ? "bg-emerald-500/15 text-emerald-300"
                      : "bg-rose-500/15 text-rose-300"
                  }`}>
                    {t.type === "INCOME" ? "Entrada" : "Saída"}
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
