import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";

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

function IconCreditCard({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.753 3h16.5a1.5 1.5 0 0 0 1.5-1.5V6.75a1.5 1.5 0 0 0-1.5-1.5H3.753a1.5 1.5 0 0 0-1.5 1.5v10.5a1.5 1.5 0 0 0 1.5 1.5Z" />
    </svg>
  );
}

function IconPencil({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" />
    </svg>
  );
}

// Cores dos cartões reais são fortes e saturadas; o padrão (null) mantém o
// visual grafite de antes.
const CARD_COLORS = [
  { hex: null, label: "Padrão" },
  { hex: "#7c3aed", label: "Roxo" },
  { hex: "#e11d48", label: "Vermelho" },
  { hex: "#ea580c", label: "Laranja" },
  { hex: "#f59e0b", label: "Âmbar" },
  { hex: "#059669", label: "Verde" },
  { hex: "#0284c7", label: "Azul" },
  { hex: "#db2777", label: "Rosa" },
];

function CardColorPicker({ current, onPick, onClose }) {
  return (
    <>
      {/* Clique fora fecha — sem isso o popover só sairia ao escolher uma cor. */}
      <button
        type="button"
        aria-label="Fechar seletor de cor"
        className="fixed inset-0 z-40 cursor-default"
        onClick={onClose}
      />
      <div className="absolute left-0 top-12 z-50 flex w-max gap-1.5 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
        {CARD_COLORS.map(({ hex, label }) => {
          const isActive = (current || null) === hex;
          return (
            <button
              key={label}
              type="button"
              title={label}
              onClick={() => onPick(hex)}
              style={hex ? { backgroundColor: hex } : undefined}
              className={`h-7 w-7 rounded-lg transition ${
                hex ? "" : "bg-slate-900 dark:bg-slate-700"
              } ${
                isActive
                  ? "ring-2 ring-emerald-500 ring-offset-2 ring-offset-white dark:ring-offset-slate-900"
                  : "hover:scale-110"
              }`}
            />
          );
        })}
      </div>
    </>
  );
}

function BillStatusBadge({ status }) {
  const isOpen = status === "OPEN";
  return (
    <span
      title={
        isOpen
          ? "O banco ainda não fechou esta fatura — valor reconstruído dos lançamentos do ciclo e sujeito a mudar"
          : "Fatura fechada pelo banco — valor definitivo"
      }
      className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
        isOpen
          ? "border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
          : "border border-slate-400/30 bg-slate-500/10 text-slate-600 dark:text-slate-400"
      }`}
    >
      {isOpen ? "Aberta" : "Fechada"}
    </span>
  );
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
  const [colorPickerBillId, setColorPickerBillId] = useState(null);

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
      api.get("/credit-card-bills", { params: { month, year } }).then((r) => setBills(r.data ?? []));
    }
  };

  const handlePickColor = async (bill, color) => {
    setColorPickerBillId(null);
    // A cor é do cartão, não da fatura — todas as faturas do mesmo cartão
    // mudam juntas, igual ao backend faz.
    setBills((prev) =>
      prev.map((b) =>
        b.pluggy_account_id === bill.pluggy_account_id ? { ...b, custom_color_hex: color } : b
      )
    );

    try {
      await api.patch(`/credit-card-bills/${bill.id}`, { custom_color_hex: color });
    } catch {
      api.get("/credit-card-bills", { params: { month, year } }).then((r) => setBills(r.data ?? []));
    }
  };

  const [prevMonth, prevYear] = prevMonthYear(month, year);

  useEffect(() => {
    api.get("/payables/upcoming?days=7")
      .then((r) => setUpcoming(r.data ?? []))
      .catch(() => setUpcoming([]));
  }, [refresh]);

  useEffect(() => {
    api.get("/credit-card-bills", { params: { month, year } })
      .then((r) => setBills(r.data ?? []))
      .catch(() => setBills([]));
  }, [month, year, refresh]);

  useEffect(() => {
    api.get("/summary", { params: { month: prevMonth, year: prevYear } })
      .then((r) => setPrevSummary(r.data ?? null))
      .catch(() => setPrevSummary(null));
  }, [prevMonth, prevYear]);

  useEffect(() => {
    api.get("/insights", { params: { month, year } })
      .then((r) => setInsights(r.data?.insights ?? []))
      .catch(() => setInsights([]));
  }, [month, year, refresh]);

  useEffect(() => {
    api.get("/summary/history", { params: { months: 6 } })
      .then((r) => setHistory(r.data?.months ?? []))
      .catch(() => setHistory([]));
  }, [month, year, refresh]);

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
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-8 md:py-8">

        {/* Header */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Dashboard Geral
              </p>
            </div>
            <h1 className="mt-1 font-display text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
              Pra onde vai seu dinheiro
            </h1>
          </div>
          <div className="flex items-center gap-3">
            {overduePayables.length > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs font-bold text-rose-600 dark:text-rose-400 shadow-sm animate-pulse">
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                {overduePayables.length} vencida{overduePayables.length > 1 ? "s" : ""}
              </span>
            )}
            <MonthNavigator month={month} year={year} onChange={onMonthChange} />
          </div>
        </header>

        {/* Master Hero Banner: Gasto do Mês + Tendência Integrada no Espaço Central */}
        {loading ? (
          <Skeleton className="h-44 rounded-3xl" />
        ) : (
          <div className="relative overflow-hidden rounded-3xl border border-slate-200/80 bg-gradient-to-br from-white via-emerald-50/20 to-teal-50/40 p-6 md:p-8 shadow-sm backdrop-blur-xl dark:border-slate-800/80 dark:from-slate-900/90 dark:via-slate-900/60 dark:to-emerald-950/20">
            <div className="absolute top-0 right-0 -mt-8 -mr-8 h-48 w-48 rounded-full bg-emerald-500/10 blur-3xl" />
            <div className="relative flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
              
              {/* Esquerda: Métricas Principais */}
              <div className="flex-shrink-0">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                  Resumo do Período
                </span>
                <p className="mt-3 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Gasto Total no Mês
                </p>
                <div className="mt-1 flex flex-wrap items-baseline gap-3">
                  <p className="font-display text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white">
                    {fmt(summary?.total_expenses)}
                  </p>
                  <DeltaBadge pct={heroDeltaPct} invertColor />
                </div>
                <p className="mt-2 text-xs font-medium text-slate-400 dark:text-slate-500">
                  {transactionCount} lançamento{transactionCount === 1 ? "" : "s"} consolidados
                  {prevSummary && ` · ${fmt(prevSummary.total_expenses)} anterior`}
                </p>
              </div>

              {/* Centro: Gráfico de Tendência Integrado no Hero Card */}
              {history.length > 0 && (
                <div className="flex-1 max-w-lg w-full rounded-2xl border border-slate-200/60 bg-white/60 p-3.5 backdrop-blur-md dark:border-slate-800/60 dark:bg-slate-900/50">
                  <div className="mb-1.5 flex items-center justify-between px-1">
                    <p className="font-display text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                      Tendência · Últimos 6 Meses
                    </p>
                  </div>
                  <TrendChart months={history} currentMonth={month} currentYear={year} height={115} />
                </div>
              )}

              {/* Direita: Botão Ver Extrato */}
              <div className="flex-shrink-0 flex items-center">
                <Link
                  to="/transactions"
                  className="rounded-2xl bg-emerald-600 px-5 py-3 text-xs font-bold text-white shadow-lg shadow-emerald-500/20 transition hover:bg-emerald-500 hover:scale-105"
                >
                  Ver Extrato →
                </Link>
              </div>

            </div>
          </div>
        )}

        {/* Insights Horizontal Carousel */}
        {insights.length > 0 && (
          <div>
            <div className="mb-3 flex items-center justify-between">
              <p className="font-display text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Insights Automáticos do Período
              </p>
            </div>
            <div className="-mx-4 flex items-stretch gap-3 overflow-x-auto px-4 pb-2 scrollbar-none md:mx-0 md:px-0">
              {insights.map((insight, i) => (
                <InsightCard key={`${insight.kind}-${insight.category_id ?? i}`} insight={insight} month={month} year={year} />
              ))}
            </div>
          </div>
        )}

        {/* Super Efficient Grid: Gasto por Categoria + Faturas de Cartão */}
        <div className="grid gap-6 lg:grid-cols-5 items-start">
          {/* Gasto por Categoria */}
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

          {/* Faturas de Cartão de Crédito */}
          <Card className="p-6 lg:col-span-2">
            <CardHeader title="Faturas de cartão" subtitle="clique no nome para definir apelido" />
            {bills.length === 0 ? (
              <EmptyState className="h-auto py-6">Nenhuma fatura neste mês.</EmptyState>
            ) : (
              <div className="flex flex-col gap-3">
                {bills.map((bill) => {
                  const displayName = bill.custom_card_name || bill.card_name || "Cartão de Crédito";
                  const isEditing = editingBillId === bill.id;
                  return (
                    <div
                      key={bill.id}
                      className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200/60 bg-gradient-to-r from-slate-50 to-white p-4 transition-all hover:border-slate-300 dark:border-slate-800/60 dark:from-slate-900/80 dark:to-slate-900/40"
                    >
                      <div className="flex items-center gap-3.5 min-w-0 flex-1">
                        <div className="relative flex-shrink-0">
                          <button
                            type="button"
                            title="Clique para escolher a cor do cartão"
                            onClick={() =>
                              setColorPickerBillId(colorPickerBillId === bill.id ? null : bill.id)
                            }
                            style={
                              bill.custom_color_hex
                                ? { backgroundColor: bill.custom_color_hex }
                                : undefined
                            }
                            className={`flex h-10 w-10 items-center justify-center rounded-xl text-white shadow-sm transition hover:brightness-110 ${
                              bill.custom_color_hex
                                ? ""
                                : "bg-slate-900 dark:bg-slate-800 dark:text-emerald-400"
                            }`}
                          >
                            <IconCreditCard className="h-5 w-5" />
                          </button>
                          {colorPickerBillId === bill.id && (
                            <CardColorPicker
                              current={bill.custom_color_hex}
                              onPick={(hex) => handlePickColor(bill, hex)}
                              onClose={() => setColorPickerBillId(null)}
                            />
                          )}
                        </div>

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
                              className="w-full rounded-lg border border-emerald-500 bg-white px-2 py-1 text-xs font-semibold text-slate-900 outline-none dark:bg-slate-800 dark:text-slate-100"
                            />
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleStartEditAlias(bill)}
                              title="Clique para editar o apelido do cartão"
                              className="group flex items-center gap-1.5 text-left text-sm font-semibold text-slate-900 hover:text-emerald-600 dark:text-slate-100 dark:hover:text-emerald-400"
                            >
                              <span className="truncate">{displayName}</span>
                              <IconPencil className="h-3.5 w-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </button>
                          )}
                          <div className="flex items-center gap-2">
                            <p className="text-xs text-slate-400 dark:text-slate-500">
                              Vence em {new Date(`${bill.due_date}T00:00:00`).toLocaleDateString("pt-BR")}
                            </p>
                            <BillStatusBadge status={bill.status} />
                          </div>
                        </div>
                      </div>

                      <span className="font-display flex-shrink-0 text-base font-bold text-slate-900 dark:text-white">
                        {fmt(bill.total_amount)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        {/* Compromissos Section */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <p className="font-display text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              Compromissos Financeiros · Não somado aos lançamentos
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                A vencer (7 dias)
              </p>
              <p className="mt-3 font-display text-2xl font-bold text-amber-600 dark:text-amber-400">
                {fmt(upcomingSum)}
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                {upcoming.length} conta{upcoming.length === 1 ? "" : "s"} pendente{upcoming.length === 1 ? "" : "s"}
              </p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Atrasadas
              </p>
              <p className="mt-3 font-display text-2xl font-bold text-rose-600 dark:text-rose-400">
                {fmt(overduePayables.reduce((s, p) => s + Number(p.amount), 0))}
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                {overduePayables.length} conta{overduePayables.length === 1 ? "" : "s"} vencida{overduePayables.length === 1 ? "" : "s"}
              </p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Faturas do Mês
              </p>
              <p className="mt-3 font-display text-2xl font-bold text-slate-900 dark:text-white">
                {fmt(billsSum)}
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                {bills.length} fatura{bills.length === 1 ? "" : "s"} sincronizada{bills.length === 1 ? "" : "s"}
              </p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Progresso de Baixas
              </p>
              <p className="mt-3 font-display text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {progressPct}%
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                {paidCount} de {totalCount} pagas
              </p>
            </Card>
          </div>
        </div>

        {/* Grid: Upcoming Payables & Budget Limit Progress */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Vencendo em breve */}
          <Card className="p-6">
            <CardHeader
              title="Vencendo em breve"
              action={
                upcoming.length > 0 && (
                  <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 text-xs font-bold text-amber-600 dark:text-amber-400">
                    {upcoming.length}
                  </span>
                )
              }
            />
            {upcoming.length === 0 ? (
              <EmptyState className="h-auto py-6">Nenhuma conta vencendo nos próximos 7 dias.</EmptyState>
            ) : (
              <div className="flex flex-col gap-3">
                {upcoming.slice(0, 5).map((p) => {
                  const [, m, d] = p.due_date.split("-");
                  const overdue = p.due_date < todayStr;
                  return (
                    <div key={p.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/50 px-4 py-3 dark:border-slate-800/60 dark:bg-slate-900/40">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{p.title}</p>
                        <p className={`text-xs ${overdue ? "text-rose-500 font-semibold" : "text-slate-400 dark:text-slate-500"}`}>
                          {overdue ? "Venceu em " : "Vence em "}{d}/{m}
                        </p>
                      </div>
                      <span className={`font-display text-sm font-bold ${overdue ? "text-rose-600 dark:text-rose-400" : "text-amber-600 dark:text-amber-400"}`}>
                        {fmt(p.amount)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Orçamento por Categoria */}
          {budgeted.length > 0 ? (
            <Card className="p-6">
              <CardHeader title="Orçamento por categoria" subtitle="gasto real vs limite estabelecido" />
              <div className="flex flex-col gap-4">
                {budgeted.map((c) => {
                  const pct = Math.min(c.budget_used_pct ?? 0, 100);
                  const over = (c.budget_used_pct ?? 0) > 100;
                  return (
                    <div key={c.category_id ?? c.category_name}>
                      <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="font-semibold text-slate-800 dark:text-slate-200">{c.category_name}</span>
                        <span className={`text-xs font-semibold ${over ? "text-rose-600 dark:text-rose-400" : "text-slate-500 dark:text-slate-400"}`}>
                          {fmt(c.total_expenses)} / {fmt(c.budget_limit)}
                          {over && " · Limite Excedido"}
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                        <div
                          className={`h-2 rounded-full transition-all duration-500 ${over ? "bg-rose-500" : "bg-emerald-500"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          ) : (
            <Card className="p-6">
              <CardHeader title="Dica de Orçamento" subtitle="controle limites de gastos" />
              <div className="flex flex-col items-center justify-center py-6 text-center">
                <p className="text-xs font-medium text-slate-400 dark:text-slate-500">
                  Você ainda não definiu limites de orçamento por categoria. Defina orçamentos na aba Configurações.
                </p>
                <Link
                  to="/settings"
                  className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs font-bold text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400"
                >
                  Configurar Orçamentos
                </Link>
              </div>
            </Card>
          )}
        </div>

      </div>
    </div>
  );
}
