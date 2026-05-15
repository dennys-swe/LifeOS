import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import MonthNavigator from "../components/MonthNavigator";
import { useFinance } from "../context/FinanceContext";
import api from "../services/api";

const fmt = (value) =>
  Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const MONTH_LABELS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

export default function ConnectionPage({ month, year, onMonthChange }) {
  const { summary, payables, loading } = useFinance();
  const [upcoming, setUpcoming] = useState([]);
  const [history, setHistory] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);

  useEffect(() => {
    api.get("/payables/upcoming?days=7")
      .then((r) => setUpcoming(r.data ?? []))
      .catch(() => setUpcoming([]));

    api.get("/summary/history?months=6")
      .then((r) => setHistory(r.data?.months ?? []))
      .catch(() => setHistory([]));

    api.get("/bank-accounts")
      .then((r) => setBankAccounts(r.data ?? []))
      .catch(() => setBankAccounts([]));
  }, []);

  const todayStr = useMemo(() => new Date().toLocaleDateString("en-CA"), []);

  const payablesThisMonth = useMemo(() => {
    if (!payables) return [];
    return payables.filter((p) => {
      if (!p.due_date) return false;
      const [y, m] = p.due_date.split("-").map(Number);
      return m === month && y === year;
    });
  }, [payables, month, year]);

  const paidCount = useMemo(
    () => payablesThisMonth.filter((p) => p.status === "PAID").length,
    [payablesThisMonth]
  );
  const totalCount = payablesThisMonth.length;
  const progressPct = totalCount > 0 ? Math.round((paidCount / totalCount) * 100) : 0;

  const categoryChartData = useMemo(() => {
    if (!summary) return [];
    return summary.by_category
      .filter((c) => Number(c.total_payables) > 0)
      .slice(0, 8)
      .map((c) => ({
        name: c.category_name.length > 14 ? c.category_name.slice(0, 13) + "…" : c.category_name,
        fullName: c.category_name,
        value: Number(c.total_payables),
        color: c.color_hex,
      }));
  }, [summary]);

  const historyChartData = useMemo(() =>
    history.map((m) => ({
      label: `${MONTH_LABELS[m.month - 1]}/${String(m.year).slice(2)}`,
      Entradas: Number(m.total_income),
      Despesas: Number(m.total_expenses),
    })),
    [history]
  );

  const overdueItems = useMemo(
    () => upcoming.filter((p) => p.due_date < todayStr),
    [upcoming, todayStr]
  );

  const formatDueDate = (dateStr) => {
    const [y, m, d] = dateStr.split("-");
    return `${d}/${m}/${y}`;
  };

  const customBarLabel = ({ x, y, width, value }) => {
    if (!value) return null;
    return (
      <text x={x + width + 6} y={y + 11} fill="#94a3b8" fontSize={11}>
        {fmt(value)}
      </text>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10">

        {/* Header */}
        <header className="flex flex-col gap-3">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Dashboard Financeiro</p>
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <h1 className="text-3xl font-semibold text-white md:text-4xl">Controle Financeiro</h1>
            {overdueItems.length > 0 && (
              <div className="flex items-center gap-2 rounded-full border border-rose-500/40 bg-rose-900/20 px-4 py-2 text-sm text-rose-300">
                <span className="h-2 w-2 rounded-full bg-rose-400" />
                {overdueItems.length} conta{overdueItems.length > 1 ? "s" : ""} vencida{overdueItems.length > 1 ? "s" : ""}
              </div>
            )}
          </div>
          <MonthNavigator month={month} year={year} onChange={onMonthChange} />
        </header>

        {/* Cards de resumo */}
        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Saldo</p>
            <p className={`mt-4 text-2xl font-semibold md:text-3xl ${Number(summary?.balance ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {fmt(summary?.balance ?? 0)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Entradas − Saídas</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Entradas</p>
            <p className="mt-4 text-2xl font-semibold text-emerald-400 md:text-3xl">
              {fmt(summary?.total_income ?? 0)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Transações do mês</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Pendente</p>
            <p className="mt-4 text-2xl font-semibold text-amber-400 md:text-3xl">
              {fmt(summary?.total_pending ?? 0)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Contas a pagar</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Pago</p>
            <p className="mt-4 text-2xl font-semibold text-emerald-400 md:text-3xl">
              {fmt(summary?.total_paid ?? 0)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Contas pagas</p>
          </div>
        </section>

        {/* Progresso do mês + Contas bancárias */}
        <section className="grid gap-4 md:grid-cols-2">
          {/* Progresso */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
            <h2 className="mb-4 text-base font-semibold text-white">Progresso do mês</h2>
            {loading ? (
              <p className="text-sm text-slate-400">Carregando...</p>
            ) : (
              <>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-slate-300">{paidCount} de {totalCount} contas pagas</span>
                  <span className={`font-semibold ${progressPct === 100 ? "text-emerald-400" : "text-amber-400"}`}>
                    {progressPct}%
                  </span>
                </div>
                <div className="h-3 w-full overflow-hidden rounded-full bg-slate-800">
                  <div
                    className={`h-3 rounded-full transition-all duration-500 ${progressPct === 100 ? "bg-emerald-500" : "bg-amber-500"}`}
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                {totalCount === 0 && (
                  <p className="mt-3 text-xs text-slate-500">Nenhuma conta neste mês.</p>
                )}
              </>
            )}
          </div>

          {/* Contas bancárias */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
            <h2 className="mb-4 text-base font-semibold text-white">Contas bancárias</h2>
            {bankAccounts.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhuma conta conectada.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {bankAccounts.map((acct) => (
                  <li key={acct.id} className="flex items-center justify-between text-sm">
                    <span className="text-slate-300">{acct.name}</span>
                    <span className="text-xs text-slate-500">{acct.bank_name}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* Contas vencendo em breve */}
        {upcoming.length > 0 && (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
            <h2 className="mb-4 text-base font-semibold text-white">
              Vencendo nos próximos 7 dias
              <span className="ml-2 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-300">
                {upcoming.length}
              </span>
            </h2>
            <div className="flex flex-col gap-2">
              {upcoming.slice(0, 6).map((p) => {
                const isOverdue = p.due_date < todayStr;
                return (
                  <div key={p.id} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-white">{p.title}</p>
                      <p className={`text-xs ${isOverdue ? "text-rose-400" : "text-slate-400"}`}>
                        {isOverdue ? "Venceu em " : "Vence em "}{formatDueDate(p.due_date)}
                      </p>
                    </div>
                    <p className={`text-sm font-semibold ${isOverdue ? "text-rose-400" : "text-amber-400"}`}>
                      {fmt(Number(p.amount))}
                    </p>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Histórico 6 meses */}
        {historyChartData.length > 0 && (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
            <h2 className="mb-1 text-lg font-semibold text-white">Histórico dos últimos 6 meses</h2>
            <p className="mb-6 text-sm text-slate-400">Entradas vs Despesas</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={historyChartData} barGap={4}>
                  <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`} tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
                  <Tooltip
                    formatter={(v, name) => [fmt(v), name]}
                    contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "12px" }}
                    labelStyle={{ color: "#e2e8f0" }}
                    itemStyle={{ color: "#e2e8f0" }}
                  />
                  <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 13 }} />
                  <Bar dataKey="Entradas" fill="#34d399" radius={[4, 4, 0, 0]} maxBarSize={32} />
                  <Bar dataKey="Despesas" fill="#f87171" radius={[4, 4, 0, 0]} maxBarSize={32} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {/* Gastos por categoria — BarChart horizontal */}
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
          <div className="mb-6 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <h2 className="text-lg font-semibold text-white">Gastos por categoria</h2>
            <p className="text-sm text-slate-400">Contas do mês selecionado</p>
          </div>
          {categoryChartData.length === 0 ? (
            <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-slate-700 text-slate-400">
              Nenhuma conta encontrada para este mês.
            </div>
          ) : (
            <div style={{ height: Math.max(180, categoryChartData.length * 44) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryChartData} layout="vertical" margin={{ left: 8, right: 90, top: 0, bottom: 0 }}>
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fill: "#cbd5e1", fontSize: 13 }}
                    axisLine={false}
                    tickLine={false}
                    width={110}
                  />
                  <Tooltip
                    formatter={(v, _name, props) => [fmt(v), props.payload.fullName]}
                    contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "12px" }}
                    labelStyle={{ color: "#e2e8f0" }}
                    itemStyle={{ color: "#e2e8f0" }}
                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                  />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={28} label={customBarLabel}>
                    {categoryChartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        {/* Orçamento por categoria */}
        {summary?.by_category?.filter((c) => c.budget_limit != null).length > 0 && (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
            <h2 className="mb-4 text-lg font-semibold text-white">Orçamento por Categoria</h2>
            <div className="flex flex-col gap-4">
              {summary.by_category
                .filter((c) => c.budget_limit != null)
                .map((c) => {
                  const pct = Math.min(c.budget_used_pct ?? 0, 100);
                  const over = (c.budget_used_pct ?? 0) > 100;
                  return (
                    <div key={c.category_id ?? c.category_name}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="font-medium text-white">{c.category_name}</span>
                        <span className={over ? "text-rose-400" : "text-slate-300"}>
                          {fmt(c.total_payables)} / {fmt(c.budget_limit)}
                          {over && " ⚠ Estourado"}
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                          className={`h-2 rounded-full transition-all ${over ? "bg-rose-500" : "bg-emerald-500"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </section>
        )}

      </div>
    </div>
  );
}
