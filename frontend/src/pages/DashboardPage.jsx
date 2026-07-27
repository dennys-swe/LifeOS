import { useEffect, useMemo, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import MonthNavigator from "../components/MonthNavigator";
import { useFinance } from "../context/FinanceContext";
import api from "../services/api";

const fmt = (v) =>
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const fmtShort = (v) => {
  const n = Number(v);
  if (Math.abs(n) >= 1000) return `R$${(n / 1000).toFixed(1)}k`;
  return `R$${n.toFixed(0)}`;
};

function delta(curr, prev) {
  if (!prev || Number(prev) === 0) return null;
  return ((Number(curr) - Number(prev)) / Math.abs(Number(prev))) * 100;
}

function DeltaBadge({ pct, invertColor = false }) {
  if (pct === null) return null;
  const positive = pct > 0;
  const good = invertColor ? !positive : positive;
  const color = good
    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
    : "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400";
  return (
    <span className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>
      {positive ? "↑" : "↓"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

function StatCard({ label, value, subtitle, valueColor }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">{label}</p>
      <p className={`mt-3 text-2xl font-semibold ${valueColor ?? "text-gray-900 dark:text-slate-100"}`}>
        {fmt(value ?? 0)}
      </p>
      <p className="mt-2 text-xs text-gray-400 dark:text-slate-500">{subtitle}</p>
    </div>
  );
}

function DonutCenter({ cx, cy, total }) {
  return (
    <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle">
      <tspan x={cx} dy="-8" className="fill-gray-500 dark:fill-slate-400" fontSize={11}>Total</tspan>
      <tspan x={cx} dy="20" className="fill-gray-900 dark:fill-slate-100" fontSize={14} fontWeight={600}>
        {fmtShort(total)}
      </tspan>
    </text>
  );
}

export default function DashboardPage({ month, year, onMonthChange }) {
  const { summary, payables, loading } = useFinance();
  const [prevSummary, setPrevSummary] = useState(null);
  const [upcoming, setUpcoming] = useState([]);
  const [bills, setBills] = useState([]);

  const prevMonth = month === 1 ? 12 : month - 1;
  const prevYear = month === 1 ? year - 1 : year;

  useEffect(() => {
    api.get("/payables/upcoming?days=7")
      .then((r) => setUpcoming(r.data ?? []))
      .catch(() => setUpcoming([]));
  }, []);

  useEffect(() => {
    api.get("/credit-card-bills", { params: { month, year } })
      .then((r) => setBills(r.data ?? []))
      .catch(() => setBills([]));
  }, [month, year]);

  useEffect(() => {
    api.get("/summary", { params: { month: prevMonth, year: prevYear } })
      .then((r) => setPrevSummary(r.data ?? null))
      .catch(() => setPrevSummary(null));
  }, [prevMonth, prevYear]);

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

  const overduePayables = useMemo(
    () => payablesThisMonth.filter((p) => p.status === "PENDING" && p.due_date < todayStr),
    [payablesThisMonth, todayStr]
  );
  const overdueSum = useMemo(
    () => overduePayables.reduce((s, p) => s + Number(p.amount), 0),
    [overduePayables]
  );

  const upcomingSum = useMemo(
    () => upcoming.reduce((s, p) => s + Number(p.amount), 0),
    [upcoming]
  );

  const billsSum = useMemo(
    () => bills.reduce((s, b) => s + Number(b.total_amount), 0),
    [bills]
  );

  const donutData = useMemo(() => {
    if (!summary) return [];
    return summary.by_category
      .filter((c) => Number(c.total_payables) > 0)
      .slice(0, 8)
      .map((c) => ({
        name: c.category_name,
        value: Number(c.total_payables),
        color: c.color_hex,
      }));
  }, [summary]);

  const totalExpenses = useMemo(
    () => donutData.reduce((s, c) => s + c.value, 0),
    [donutData]
  );

  const categoryTableData = useMemo(() => {
    if (!summary) return [];
    const prevMap = new Map(
      (prevSummary?.by_category ?? []).map((c) => [c.category_name, c])
    );
    return summary.by_category
      .filter((c) => Number(c.total_payables) > 0)
      .map((c) => {
        const prev = prevMap.get(c.category_name);
        const pct = delta(c.total_payables, prev?.total_payables);
        const barPct = totalExpenses > 0 ? (Number(c.total_payables) / totalExpenses) * 100 : 0;
        return { ...c, deltaPct: pct, barPct, prevAmount: prev?.total_payables ?? null };
      })
      .sort((a, b) => Number(b.total_payables) - Number(a.total_payables));
  }, [summary, prevSummary, totalExpenses]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">

        {/* Header */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 dark:text-slate-500">
              Dashboard
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-gray-900 dark:text-slate-100">
              Contas, faturas e gastos
            </h1>
          </div>
          <div className="flex items-center gap-3">
            {overduePayables.length > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-400">
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                {overduePayables.length} vencida{overduePayables.length > 1 ? "s" : ""}
              </span>
            )}
            <MonthNavigator month={month} year={year} onChange={onMonthChange} />
          </div>
        </header>

        {/* Stat cards */}
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-28 animate-pulse rounded-2xl bg-gray-200 dark:bg-slate-800" />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="A vencer (7 dias)"
              value={upcomingSum}
              subtitle={`${upcoming.length} conta${upcoming.length === 1 ? "" : "s"}`}
              valueColor="text-amber-600 dark:text-amber-400"
            />
            <StatCard
              label="Vencidas"
              value={overdueSum}
              subtitle={`${overduePayables.length} conta${overduePayables.length === 1 ? "" : "s"}`}
              valueColor="text-rose-600 dark:text-rose-400"
            />
            <StatCard
              label="Faturas do mês"
              value={billsSum}
              subtitle={`${bills.length} fatura${bills.length === 1 ? "" : "s"}`}
            />
            <StatCard
              label="Pago no mês"
              value={summary?.total_paid}
              subtitle="mês selecionado"
              valueColor="text-emerald-600 dark:text-emerald-400"
            />
          </div>
        )}

        {/* Middle row: donut + upcoming */}
        <div className="grid gap-6 lg:grid-cols-5">

          {/* Donut + category list */}
          <div className="lg:col-span-3 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100">Gastos por categoria</h2>
              <p className="text-xs text-gray-400 dark:text-slate-500">mês selecionado</p>
            </div>
            {donutData.length === 0 ? (
              <div className="flex h-48 items-center justify-center text-sm text-gray-400 dark:text-slate-500">
                Nenhum gasto registrado.
              </div>
            ) : (
              <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
                {/* Donut */}
                <div className="flex-shrink-0 self-center">
                  <ResponsiveContainer width={180} height={180}>
                    <PieChart>
                      <Pie
                        data={donutData}
                        cx="50%"
                        cy="50%"
                        innerRadius={54}
                        outerRadius={82}
                        paddingAngle={2}
                        dataKey="value"
                        startAngle={90}
                        endAngle={-270}
                        strokeWidth={0}
                      >
                        {donutData.map((entry) => (
                          <Cell key={entry.name} fill={entry.color} />
                        ))}
                      </Pie>
                      <DonutCenter cx={90} cy={90} total={totalExpenses} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Legend list */}
                <div className="flex flex-1 flex-col gap-2 min-w-0">
                  {donutData.map((c) => (
                    <div key={c.name} className="flex items-center gap-2">
                      <span className="h-2 w-2 flex-shrink-0 rounded-full" style={{ backgroundColor: c.color }} />
                      <span className="flex-1 truncate text-sm text-gray-700 dark:text-slate-300">{c.name}</span>
                      <span className="text-sm font-medium text-gray-900 dark:text-slate-100">{fmt(c.value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Upcoming + progress */}
          <div className="flex flex-col gap-4 lg:col-span-2">
            {/* Progress */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-slate-100">Progresso do mês</h2>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-slate-400">{paidCount} de {totalCount} pagas</span>
                <span className={`font-semibold ${progressPct === 100 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                  {progressPct}%
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-slate-800">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${progressPct === 100 ? "bg-emerald-500" : "bg-amber-500"}`}
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>

            {/* Upcoming bills */}
            <div className="flex-1 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-slate-100">
                Vencendo em breve
                {upcoming.length > 0 && (
                  <span className="ml-2 rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-500/20 dark:text-amber-400">
                    {upcoming.length}
                  </span>
                )}
              </h2>
              {upcoming.length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-slate-500">Nenhuma conta vencendo nos próximos 7 dias.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {upcoming.slice(0, 5).map((p) => {
                    const [, m, d] = p.due_date.split("-");
                    const overdue = p.due_date < todayStr;
                    return (
                      <div key={p.id} className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-gray-800 dark:text-slate-200">{p.title}</p>
                          <p className={`text-xs ${overdue ? "text-rose-500 dark:text-rose-400" : "text-gray-400 dark:text-slate-500"}`}>
                            {overdue ? "Venceu " : ""}{d}/{m}
                          </p>
                        </div>
                        <span className={`flex-shrink-0 text-sm font-semibold ${overdue ? "text-rose-600 dark:text-rose-400" : "text-amber-600 dark:text-amber-400"}`}>
                          {fmt(p.amount)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Faturas de cartão */}
        {bills.length > 0 && (
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <h2 className="mb-4 text-sm font-semibold text-gray-900 dark:text-slate-100">Faturas de cartão</h2>
            <div className="flex flex-col gap-3">
              {bills.map((bill) => (
                <div key={bill.id} className="flex items-center justify-between gap-2">
                  <p className="text-sm text-gray-700 dark:text-slate-300">
                    Vence em {new Date(`${bill.due_date}T00:00:00`).toLocaleDateString("pt-BR")}
                  </p>
                  <span className="text-sm font-semibold text-gray-900 dark:text-slate-100">
                    {fmt(bill.total_amount)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Category table with delta */}
        {categoryTableData.length > 0 && (
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4 dark:border-slate-800">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100">Principais categorias</h2>
              <p className="text-xs text-gray-400 dark:text-slate-500">vs mês anterior</p>
            </div>
            <div className="divide-y divide-gray-50 dark:divide-slate-800/60">
              {categoryTableData.map((c) => (
                <div key={c.category_name} className="flex items-center gap-2 px-3 py-3 sm:gap-4 sm:px-6">
                  <span className="h-2.5 w-2.5 flex-shrink-0 rounded-full" style={{ backgroundColor: c.color_hex }} />
                  <span className="w-24 flex-shrink-0 truncate text-sm text-gray-700 dark:text-slate-300 sm:w-32">{c.category_name}</span>
                  <div className="flex flex-1 items-center gap-2 min-w-0">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-800">
                      <div
                        className="h-1.5 rounded-full transition-all"
                        style={{ width: `${c.barPct}%`, backgroundColor: c.color_hex }}
                      />
                    </div>
                  </div>
                  <span className="w-16 flex-shrink-0 text-right text-sm font-medium text-gray-900 dark:text-slate-100 sm:w-24">
                    {fmt(c.total_payables)}
                  </span>
                  <div className="hidden w-20 flex-shrink-0 text-right sm:block">
                    <DeltaBadge pct={c.deltaPct} invertColor />
                  </div>
                  <span className="hidden w-24 flex-shrink-0 text-right text-xs text-gray-400 dark:text-slate-500 sm:block">
                    {c.prevAmount !== null ? fmt(c.prevAmount) : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Budget */}
        {summary?.by_category?.filter((c) => c.budget_limit != null).length > 0 && (
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <h2 className="mb-4 text-sm font-semibold text-gray-900 dark:text-slate-100">Orçamento por categoria</h2>
            <div className="flex flex-col gap-4">
              {summary.by_category
                .filter((c) => c.budget_limit != null)
                .map((c) => {
                  const pct = Math.min(c.budget_used_pct ?? 0, 100);
                  const over = (c.budget_used_pct ?? 0) > 100;
                  return (
                    <div key={c.category_id ?? c.category_name}>
                      <div className="mb-1.5 flex items-center justify-between text-sm">
                        <span className="font-medium text-gray-800 dark:text-slate-200">{c.category_name}</span>
                        <span className={over ? "text-rose-600 dark:text-rose-400" : "text-gray-500 dark:text-slate-400"}>
                          {fmt(c.total_payables)} / {fmt(c.budget_limit)}
                          {over && " · Estourado"}
                        </span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-slate-800">
                        <div
                          className={`h-1.5 rounded-full transition-all ${over ? "bg-rose-500" : "bg-emerald-500"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
