import { useEffect, useMemo, useState } from "react";

import CategorySpendList from "../components/dashboard/CategorySpendList";
import InsightCard from "../components/dashboard/InsightCard";
import TrendChart from "../components/dashboard/TrendChart";
import MonthNavigator from "../components/MonthNavigator";
import Card, { CardHeader } from "../components/ui/Card";
import DeltaBadge from "../components/ui/DeltaBadge";
import EmptyState from "../components/ui/EmptyState";
import Skeleton, { SkeletonGrid } from "../components/ui/Skeleton";
import { useFinance } from "../context/FinanceContext";
import { fmt } from "../lib/format";
import api from "../services/api";

function pctChange(current, previous) {
  if (!previous || Number(previous) === 0) return null;
  return ((Number(current) - Number(previous)) / Math.abs(Number(previous))) * 100;
}

function prevMonthYear(month, year) {
  return month === 1 ? [12, year - 1] : [month - 1, year];
}

export default function DashboardPage({ month, year, onMonthChange }) {
  const { summary, payables, loading, refresh } = useFinance();
  const [prevSummary, setPrevSummary] = useState(null);
  const [insights, setInsights] = useState([]);
  const [history, setHistory] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [bills, setBills] = useState([]);
  const [editingBillId, setEditingBillId] = useState(null);
  const [editingAliasValue, setEditingAliasValue] = useState("");

  const handleStartEditAlias = (bill) => {
    setEditingBillId(bill.id);
    setEditingAliasValue(bill.custom_card_name || bill.card_name || "");
  };

  const handleSaveAlias = async (bill) => {
    const val = editingAliasValue.trim();
    setEditingBillId(null);
    const newCustomName = val || null;

    setBills((prev) =>
      prev.map((b) => (b.id === bill.id ? { ...b, custom_card_name: newCustomName } : b))
    );

    try {
      await api.patch(`/credit-card-bills/${bill.id}`, { custom_card_name: newCustomName });
      refresh?.();
    } catch {
      // Revert if error
      api.get("/credit-card-bills", { params: { month, year } }).then((r) => setBills(r.data ?? []));
    }
  };


  const [prevMonth, prevYear] = prevMonthYear(month, year);

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

  useEffect(() => {
    api.get("/insights", { params: { month, year } })
      .then((r) => setInsights(r.data?.insights ?? []))
      .catch(() => setInsights([]));
  }, [month, year]);

  useEffect(() => {
    api.get("/summary/history", { params: { months: 6 } })
      .then((r) => setHistory(r.data?.months ?? []))
      .catch(() => setHistory([]));
  }, [month, year]);

  const todayStr = useMemo(() => new Date().toLocaleDateString("en-CA"), []);

  const payablesThisMonth = useMemo(() => {
    if (!payables) return [];
    return payables.filter((p) => {
      if (!p.due_date) return false;
      const [y, m] = p.due_date.split("-").map(Number);
      return m === month && y === year;
    });
  }, [payables, month, year]);

  const overduePayables = useMemo(
    () => payablesThisMonth.filter((p) => p.status === "PENDING" && p.due_date < todayStr),
    [payablesThisMonth, todayStr]
  );

  const upcomingSum = useMemo(
    () => upcoming.reduce((s, p) => s + Number(p.amount), 0),
    [upcoming]
  );
  const billsSum = useMemo(
    () => bills.reduce((s, b) => s + Number(b.total_amount), 0),
    [bills]
  );

  const paidCount = payablesThisMonth.filter((p) => p.status === "PAID").length;
  const totalCount = payablesThisMonth.length;
  const progressPct = totalCount > 0 ? Math.round((paidCount / totalCount) * 100) : 0;

  const heroDeltaPct = pctChange(summary?.total_expenses, prevSummary?.total_expenses);
  const transactionCount = useMemo(
    () => (summary?.by_category ?? []).reduce((s, c) => s + (c.transaction_count ?? 0), 0),
    [summary]
  );

  const budgeted = (summary?.by_category ?? []).filter((c) => c.budget_limit != null);

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
              Pra onde vai seu dinheiro
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

        {/* Hero: gasto do mês */}
        {loading ? (
          <Skeleton className="h-32" />
        ) : (
          <Card className="p-6">
            <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
              Gasto do mês
            </p>
            <div className="mt-2 flex flex-wrap items-baseline gap-3">
              <p className="text-4xl font-semibold text-gray-900 dark:text-slate-100">
                {fmt(summary?.total_expenses)}
              </p>
              <DeltaBadge pct={heroDeltaPct} invertColor />
            </div>
            <p className="mt-2 text-sm text-gray-400 dark:text-slate-500">
              {transactionCount} lançamento{transactionCount === 1 ? "" : "s"}
              {prevSummary && ` · ${fmt(prevSummary.total_expenses)} no mês anterior`}
            </p>
          </Card>
        )}

        {/* Insights */}
        {insights.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
              O que mudou
            </p>
            <div className="-mx-6 flex gap-3 overflow-x-auto px-6 pb-2">
              {insights.map((insight, i) => (
                <InsightCard key={`${insight.kind}-${insight.category_id ?? i}`} insight={insight} month={month} year={year} />
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-5">
          {/* Gasto por categoria */}
          <Card className="p-6 lg:col-span-3">
            <CardHeader title="Gasto por categoria" subtitle="mês selecionado" />
            {loading ? (
              <SkeletonGrid count={4} itemClassName="h-10" />
            ) : (
              <CategorySpendList
                categories={summary?.by_category ?? []}
                prevCategories={prevSummary?.by_category}
                month={month}
                year={year}
              />
            )}
          </Card>

          {/* Tendência */}
          <Card className="p-6 lg:col-span-2">
            <CardHeader title="Tendência" subtitle="últimos 6 meses" />
            {history.length === 0 ? (
              <EmptyState>Sem histórico suficiente.</EmptyState>
            ) : (
              <TrendChart months={history} currentMonth={month} currentYear={year} />
            )}
          </Card>
        </div>

        {/* Compromissos — nunca somado ao gasto acima */}
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
            Compromissos · não entra no gasto do mês
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
                A vencer (7 dias)
              </p>
              <p className="mt-3 text-2xl font-semibold text-amber-600 dark:text-amber-400">
                {fmt(upcomingSum)}
              </p>
              <p className="mt-2 text-xs text-gray-400 dark:text-slate-500">
                {upcoming.length} conta{upcoming.length === 1 ? "" : "s"}
              </p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
                Vencidas
              </p>
              <p className="mt-3 text-2xl font-semibold text-rose-600 dark:text-rose-400">
                {fmt(overduePayables.reduce((s, p) => s + Number(p.amount), 0))}
              </p>
              <p className="mt-2 text-xs text-gray-400 dark:text-slate-500">
                {overduePayables.length} conta{overduePayables.length === 1 ? "" : "s"}
              </p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
                Faturas do mês
              </p>
              <p className="mt-3 text-2xl font-semibold text-gray-900 dark:text-slate-100">
                {fmt(billsSum)}
              </p>
              <p className="mt-2 text-xs text-gray-400 dark:text-slate-500">
                {bills.length} fatura{bills.length === 1 ? "" : "s"}
              </p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
                Progresso do mês
              </p>
              <p className="mt-3 text-2xl font-semibold text-gray-900 dark:text-slate-100">
                {progressPct}%
              </p>
              <p className="mt-2 text-xs text-gray-400 dark:text-slate-500">
                {paidCount} de {totalCount} pagas
              </p>
            </Card>
          </div>
        </div>

        {/* Vencendo em breve + Faturas de cartão */}
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <CardHeader
              title="Vencendo em breve"
              action={
                upcoming.length > 0 && (
                  <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-500/20 dark:text-amber-400">
                    {upcoming.length}
                  </span>
                )
              }
            />
            {upcoming.length === 0 ? (
              <EmptyState className="h-auto py-4">Nenhuma conta vencendo nos próximos 7 dias.</EmptyState>
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
          </Card>

          <Card className="p-5">
            <CardHeader title="Faturas de cartão" subtitle="clique no nome para dar um apelido" />
            {bills.length === 0 ? (
              <EmptyState className="h-auto py-4">Nenhuma fatura neste mês.</EmptyState>
            ) : (
              <div className="flex flex-col gap-3">
                {bills.map((bill) => {
                  const displayName = bill.custom_card_name || bill.card_name || "Cartão de Crédito";
                  const isEditing = editingBillId === bill.id;
                  return (
                    <div key={bill.id} className="flex items-center justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        {isEditing ? (
                          <input
                            autoFocus
                            value={editingAliasValue}
                            onChange={(e) => setEditingAliasValue(e.target.value)}
                            onBlur={() => handleSaveAlias(bill)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleSaveAlias(bill);
                              if (e.key === "Escape") setEditingBillId(null);
                            }}
                            placeholder="Apelido do cartão..."
                            maxLength={100}
                            className="w-full rounded-lg border border-gray-300 px-2 py-0.5 text-sm font-medium text-gray-900 focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                          />
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleStartEditAlias(bill)}
                            title="Clique para definir apelido"
                            className="group flex items-center gap-1.5 text-left text-sm font-medium text-gray-900 hover:underline dark:text-slate-100"
                          >
                            <span className="truncate">{displayName}</span>
                            <span className="text-xs text-gray-400 opacity-0 group-hover:opacity-100 dark:text-slate-500">✏️</span>
                          </button>
                        )}
                        <p className="text-xs text-gray-500 dark:text-slate-400">
                          Vence em {new Date(`${bill.due_date}T00:00:00`).toLocaleDateString("pt-BR")}
                        </p>
                      </div>
                      <span className="flex-shrink-0 text-sm font-semibold text-gray-900 dark:text-slate-100">
                        {fmt(bill.total_amount)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

        </div>

        {/* Orçamento — movido pelo gasto real, não payables */}
        {budgeted.length > 0 && (
          <Card className="p-6">
            <CardHeader title="Orçamento por categoria" subtitle="gasto real vs limite" />
            <div className="flex flex-col gap-4">
              {budgeted.map((c) => {
                const pct = Math.min(c.budget_used_pct ?? 0, 100);
                const over = (c.budget_used_pct ?? 0) > 100;
                return (
                  <div key={c.category_id ?? c.category_name}>
                    <div className="mb-1.5 flex items-center justify-between text-sm">
                      <span className="font-medium text-gray-800 dark:text-slate-200">{c.category_name}</span>
                      <span className={over ? "text-rose-600 dark:text-rose-400" : "text-gray-500 dark:text-slate-400"}>
                        {fmt(c.total_expenses)} / {fmt(c.budget_limit)}
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
          </Card>
        )}

      </div>
    </div>
  );
}
