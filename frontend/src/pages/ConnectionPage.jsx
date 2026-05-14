import { useMemo } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import MonthNavigator from "../components/MonthNavigator";
import { useFinance } from "../context/FinanceContext";

const formatCurrency = (value) =>
  Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function ConnectionPage({ month, year, onMonthChange }) {
  const { summary, loading } = useFinance();

  const chartData = useMemo(() => {
    if (!summary) return [];
    return summary.by_category.map((c) => ({
      name: c.category_name,
      value: Number(c.total_payables),
      color: c.color_hex,
    }));
  }, [summary]);

  const budgetCategories = useMemo(() => {
    if (!summary) return [];
    return summary.by_category.filter((c) => c.budget_limit != null);
  }, [summary]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10">
        <header className="flex flex-col gap-3">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">
            Dashboard Financeiro
          </p>
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-3xl font-semibold text-white md:text-4xl">
                Controle Financeiro
              </h1>
              <p className="mt-1 text-slate-400">Visão geral do mês</p>
            </div>
            <div className="rounded-full border border-slate-800 bg-slate-900/70 px-4 py-2 text-sm text-slate-300">
              {loading ? "Carregando..." : "Conectado com sucesso"}
            </div>
          </div>
          <MonthNavigator month={month} year={year} onChange={onMonthChange} />
        </header>

        {/* Cards principais */}
        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Saldo do Mês</p>
            <p className={`mt-4 text-2xl font-semibold md:text-3xl ${Number(summary?.balance ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {formatCurrency(summary?.balance ?? 0)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Entradas - Saídas</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Entradas</p>
            <p className="mt-4 text-2xl font-semibold text-emerald-400 md:text-3xl">
              {formatCurrency(summary?.total_income ?? 0)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Transações do mês</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Total Pendente</p>
            <p className="mt-4 text-2xl font-semibold text-amber-400 md:text-3xl">
              {formatCurrency(summary?.total_pending ?? 0)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Contas a pagar no mês</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Total Pago</p>
            <p className="mt-4 text-2xl font-semibold text-emerald-400 md:text-3xl">
              {formatCurrency(summary?.total_paid ?? 0)}
            </p>
            <p className="mt-2 text-xs text-slate-500">Contas pagas no mês</p>
          </div>
        </section>

        {/* Gráfico por categoria */}
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <h2 className="text-lg font-semibold text-white">Payables por categoria</h2>
            <p className="text-sm text-slate-400">Distribuição do mês selecionado</p>
          </div>
          <div className="mt-6 h-72">
            {chartData.length === 0 ? (
              <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-700 text-slate-400">
                Nenhuma conta encontrada para este mês.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={110}
                    paddingAngle={2}
                  >
                    {chartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => formatCurrency(Number(value))}
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "12px",
                    }}
                    labelStyle={{ color: "#e2e8f0" }}
                    itemStyle={{ color: "#e2e8f0" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        {/* Orçamento por categoria */}
        {budgetCategories.length > 0 && (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
            <h2 className="mb-4 text-lg font-semibold text-white">Orçamento por Categoria</h2>
            <div className="flex flex-col gap-4">
              {budgetCategories.map((c) => {
                const pct = Math.min(c.budget_used_pct ?? 0, 100);
                const overBudget = (c.budget_used_pct ?? 0) > 100;
                return (
                  <div key={c.category_id ?? c.category_name}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="font-medium text-white">{c.category_name}</span>
                      <span className={overBudget ? "text-rose-400" : "text-slate-300"}>
                        {formatCurrency(c.total_payables)} / {formatCurrency(c.budget_limit)}
                        {overBudget && " ⚠ Estourado"}
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className={`h-2 rounded-full transition-all ${overBudget ? "bg-rose-500" : "bg-emerald-500"}`}
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
