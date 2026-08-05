import { useEffect, useMemo, useRef, useState } from "react";

import api from "../services/api";
import ConfirmModal from "../components/ConfirmModal";
import EditPayableModal from "../components/EditPayableModal";
import MonthNavigator from "../components/MonthNavigator";
import StatusBadge from "../components/StatusBadge";
import Toast from "../components/Toast";
import Card from "../components/ui/Card";
import CategoryDot from "../components/ui/CategoryDot";
import EmptyState from "../components/ui/EmptyState";
import BillStatusBadge from "../components/ui/BillStatusBadge";
import { useFinance } from "../context/FinanceContext";
import { fmt } from "../lib/format";
import RecurringPayablesPage from "./RecurringPayablesPage";

const FILTERS = {
  all: "all",
  pending: "pending",
  overdue: "overdue",
};

export default function PayablesPage({
  filter,
  onFilterChange,
  month,
  year,
  onMonthChange,
}) {
  const [activeTab, setActiveTab] = useState("payables");
  const { payables: allPayables, categories, refresh } = useFinance();
  const [editingPayable, setEditingPayable] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [confirmState, setConfirmState] = useState({
    open: false,
    payableId: null,
    action: null,
  });
  const [toastState, setToastState] = useState({
    open: false,
    message: "",
    actionLabel: "",
  });
  const pendingDeleteRef = useRef(null);
  const [optimisticPayables, setOptimisticPayables] = useState(null);

  const payables = optimisticPayables ?? allPayables;
  const todayStr = useMemo(() => new Date().toLocaleDateString("en-CA"), []);

  useEffect(() => {
    return () => {
      if (pendingDeleteRef.current) {
        clearTimeout(pendingDeleteRef.current.timer);
        api.delete(`/payables/${pendingDeleteRef.current.id}`).catch(() => {});
      }
    };
  }, []);

  useEffect(() => {
    api.post(`/recurring-payables/generate?month=${month}&year=${year}`)
      .then(() => refresh())
      .catch(() => {});
  }, [month, year, refresh]);

  const payablesThisMonth = useMemo(() => {
    return payables.filter((item) => {
      if (!item.due_date) return false;
      const [itemYear, itemMonth] = item.due_date.split('-').map(Number);
      return itemMonth === month && itemYear === year;
    });
  }, [payables, month, year]);

  const activeFilter = filter ?? FILTERS.all;

  const dueTodayCount = useMemo(() => {
    return payablesThisMonth.filter((item) => item.due_date === todayStr && item.status === "PENDING").length;
  }, [payablesThisMonth, todayStr]);

  const categoryMap = useMemo(() => {
    return new Map(categories.map((category) => [category.id, category]));
  }, [categories]);

  const handleDelete = async (id) => {
    setConfirmState({ open: true, payableId: id, action: "delete" });
  };

  const handleMarkPaid = async (id) => {
    setConfirmState({ open: true, payableId: id, action: "paid" });
  };

  const finalizePendingDelete = async () => {
    if (!pendingDeleteRef.current) return;
    const { id, timer } = pendingDeleteRef.current;
    clearTimeout(timer);
    pendingDeleteRef.current = null;
    try {
      await api.delete(`/payables/${id}`);
      setOptimisticPayables(null);
      refresh();
    } catch {
      setErrorMessage("Falha ao excluir conta.");
    }
  };

  const confirmAction = async () => {
    if (!confirmState.payableId) return;

    if (confirmState.action === "delete") {
      await finalizePendingDelete();
      const deleted = payables.find((item) => item.id === confirmState.payableId);
      setOptimisticPayables((prev) =>
        (prev ?? allPayables).filter((item) => item.id !== confirmState.payableId)
      );
      const timer = setTimeout(() => {
        finalizePendingDelete();
        setToastState({ open: false, message: "", actionLabel: "" });
      }, 5000);
      pendingDeleteRef.current = {
        id: confirmState.payableId,
        item: deleted,
        timer,
      };
      setToastState({
        open: true,
        message: "Conta removida temporariamente.",
        actionLabel: "Desfazer",
      });
    }

    if (confirmState.action === "paid") {
      try {
        const today = new Date().toISOString().slice(0, 10);
        await api.put(`/payables/${confirmState.payableId}`, {
          status: "PAID",
          payment_date: today,
        });
        refresh();
      } catch {
        setErrorMessage("Falha ao marcar como pago.");
      }
    }

    setConfirmState({ open: false, payableId: null, action: null });
  };

  const handleUndoDelete = () => {
    if (!pendingDeleteRef.current) return;
    const { item, timer } = pendingDeleteRef.current;
    clearTimeout(timer);
    pendingDeleteRef.current = null;
    if (item) {
      setOptimisticPayables((prev) => [item, ...(prev ?? allPayables)]);
    }
    setToastState({ open: false, message: "", actionLabel: "" });
  };

  const pendingPayables = useMemo(() => {
    return payablesThisMonth
      .filter((item) => item.status === "PENDING")
      .sort((a, b) => a.due_date.localeCompare(b.due_date));
  }, [payablesThisMonth]);

  const paidPayables = useMemo(() => {
    return payablesThisMonth
      .filter((item) => item.status === "PAID")
      .sort((a, b) => a.due_date.localeCompare(b.due_date));
  }, [payablesThisMonth]);

  const overduePayables = useMemo(() => {
    return pendingPayables.filter((item) => item.due_date < todayStr);
  }, [pendingPayables, todayStr]);

  // Fatura de cartão tem natureza diferente do resto: valor vem do banco, não
  // se edita, e some do bloco quando é paga. Misturá-la com água/energia/
  // aluguel deixava a lista sem hierarquia nenhuma.
  const splitBills = (items) => [
    items.filter((i) => i.origin === "BILL"),
    items.filter((i) => i.origin !== "BILL"),
  ];
  const [pendingBills, pendingOthers] = splitBills(pendingPayables);
  const [paidBills, paidOthers] = splitBills(paidPayables);

  const renderList = (items) => {
    if (items.length === 0) {
      return <EmptyState className="h-auto py-8">Nenhuma conta encontrada nesta seção.</EmptyState>;
    }

    return items.map((item) => {
      const [yearPart, monthPart, dayPart] = item.due_date.split('-');
      const formattedDate = `${dayPart}/${monthPart}/${yearPart}`;
      const isDueToday = item.due_date === todayStr && item.status === "PENDING";
      const isOverdue = item.status === "PENDING" && item.due_date < todayStr;
      const cat = item.category_id ? categoryMap.get(item.category_id) : null;
      const isBill = item.origin === "BILL";
      const isAuto = isBill || item.origin === "RECURRING";
      // Fatura tem valor e vencimento vindos do banco: o sync sobrescreve os
      // dois a cada rodada, então editar não se sustenta. Recorrente é o
      // oposto — `generate_for_month` só cria se ainda não existe e nunca
      // sobrescreve, e água/energia mudam de valor todo mês.
      const canEdit = !isBill;
      // Excluir só faz sentido no que é do usuário: fatura o sync recria, e
      // recorrente é regerada ao abrir o mês de novo.
      const canDelete = item.origin === "MANUAL";

      return (
        <div
          key={item.id}
          className={`flex flex-col gap-3 rounded-2xl border p-4 transition-all hover:shadow-sm md:flex-row md:items-center md:justify-between ${
            isDueToday
              ? "border-amber-400/60 bg-amber-500/10 dark:border-amber-400/40 dark:bg-amber-500/10"
              : isOverdue
              ? "border-rose-300/60 bg-rose-500/5 dark:border-rose-500/30 dark:bg-rose-500/10"
              : "border-slate-200/60 bg-white dark:border-slate-800/60 dark:bg-slate-900/60"
          }`}
        >
          <div className="flex items-start gap-3.5 min-w-0">
            {cat ? (
              <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-xl" style={{ backgroundColor: `${cat.color_hex}18` }}>
                <CategoryDot color={cat.color_hex} />
              </div>
            ) : (
              <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800">
                <span className="h-2 w-2 rounded-full bg-slate-400" />
              </div>
            )}

            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-slate-900 dark:text-white">{item.title}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-slate-400 dark:text-slate-500">
                  Vencimento: {formattedDate}
                </span>
                {isBill ? (
                  // Mesmo rótulo do dashboard: é a mesma fatura nas duas telas.
                  <BillStatusBadge status={item.is_estimated ? "OPEN" : "CLOSED"} />
                ) : (
                  isAuto && (
                    <span
                      title="Gerada automaticamente a partir de uma conta recorrente"
                      className="inline-flex rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sky-600 dark:text-sky-400"
                    >
                      Automática
                    </span>
                  )
                )}
                {cat && (
                  <span
                    className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                    style={{
                      color: cat.color_hex,
                      backgroundColor: `${cat.color_hex}18`,
                    }}
                  >
                    {cat.name}
                  </span>
                )}
                <StatusBadge status={item.status} isOverdue={isOverdue} isDueToday={isDueToday} />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between md:justify-end gap-3 pt-2 border-t border-slate-100 dark:border-slate-800/40 md:pt-0 md:border-t-0">
            <p className={`font-display text-base font-bold ${
              item.status === "PAID"
                ? "text-emerald-600 dark:text-emerald-400"
                : isOverdue
                ? "text-rose-600 dark:text-rose-400"
                : "text-amber-600 dark:text-amber-400"
            }`}>
              {fmt(Number(item.amount) || 0)}
            </p>

            <div className="flex items-center gap-1.5">
              {item.status !== "PAID" && (
                <button
                  type="button"
                  onClick={() => handleMarkPaid(item.id)}
                  className="rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-500"
                >
                  Baixa
                </button>
              )}
              {canEdit && (
                <button
                  type="button"
                  onClick={() => setEditingPayable(item)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Editar
                </button>
              )}
              {canDelete && (
                <button
                  type="button"
                  onClick={() => handleDelete(item.id)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-500 transition hover:bg-rose-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-rose-500/10"
                >
                  Excluir
                </button>
              )}
            </div>
          </div>
        </div>
      );
    });
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {editingPayable && (
        <EditPayableModal
          payable={editingPayable}
          categories={categories}
          onClose={() => setEditingPayable(null)}
          onSaved={() => { refresh(); setEditingPayable(null); }}
        />
      )}
      <ConfirmModal
        open={confirmState.open}
        title={
          confirmState.action === "paid"
            ? "Marcar conta como paga?"
            : "Tem certeza que deseja excluir?"
        }
        description={
          confirmState.action === "paid"
            ? "O status da obrigação será atualizado para PAGO."
            : "Essa ação removerá a conta da lista."
        }
        confirmLabel="Confirmar"
        variant={confirmState.action === "paid" ? "success" : "danger"}
        onCancel={() => setConfirmState({ open: false, payableId: null, action: null })}
        onConfirm={confirmAction}
      />
      <Toast
        open={toastState.open}
        message={toastState.message}
        actionLabel={toastState.actionLabel}
        onAction={handleUndoDelete}
        onClose={() => setToastState({ open: false, message: "", actionLabel: "" })}
      />

      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
        {/* Header */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">Gestão de Obrigações</p>
            <h1 className="mt-1 font-display text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Contas a Pagar</h1>
          </div>
          <MonthNavigator month={month} year={year} onChange={onMonthChange} />
        </header>

        {/* Tab Navigation */}
        <div className="flex rounded-2xl border border-slate-200/80 bg-slate-100 p-1.5 shadow-inner dark:border-slate-800/80 dark:bg-slate-900/60">
          {[
            { key: "payables", label: "Contas do Mês" },
            { key: "recurring", label: "Recorrentes Automáticas" },
          ].map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              className={`flex-1 rounded-xl px-4 py-2.5 font-display text-xs font-bold transition-all duration-200 ${
                activeTab === key
                  ? "bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white"
                  : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {activeTab === "recurring" ? (
          <RecurringPayablesPage month={month} year={year} embedded />
        ) : (
          <>
            {dueTodayCount > 0 && (
              <div className="flex items-center gap-2 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs font-bold text-amber-700 dark:text-amber-300 shadow-sm animate-pulse">
                <svg className="h-4 w-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                </svg>
                <span>{dueTodayCount} conta{dueTodayCount > 1 ? "s" : ""} vencendo hoje no mês!</span>
              </div>
            )}

            {/* Summary Stat Cards */}
            <section className="grid gap-4 sm:grid-cols-4">
              <Card className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Total do Mês</p>
                <p className="mt-2 font-display text-xl font-bold text-slate-900 dark:text-white">
                  {fmt(payablesThisMonth.reduce((s, p) => s + Number(p.amount), 0))}
                </p>
              </Card>
              <Card className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">A Vencer</p>
                <p className="mt-2 font-display text-xl font-bold text-amber-600 dark:text-amber-400">
                  {fmt(pendingPayables.filter((p) => p.due_date >= todayStr).reduce((s, p) => s + Number(p.amount), 0))}
                </p>
              </Card>
              <Card className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Atrasadas</p>
                <p className="mt-2 font-display text-xl font-bold text-rose-600 dark:text-rose-400">
                  {fmt(overduePayables.reduce((s, p) => s + Number(p.amount), 0))}
                </p>
              </Card>
              <Card className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Pagas</p>
                <p className="mt-2 font-display text-xl font-bold text-emerald-600 dark:text-emerald-400">
                  {fmt(paidPayables.reduce((s, p) => s + Number(p.amount), 0))}
                </p>
              </Card>
            </section>

            {/* Filter Pills */}
            <div className="flex flex-wrap gap-2">
              {[
                { key: FILTERS.all, label: "Todas" },
                { key: FILTERS.pending, label: "Pendentes" },
                { key: FILTERS.overdue, label: "Atrasadas" },
              ].map((chip) => (
                <button
                  key={chip.key}
                  type="button"
                  onClick={() => onFilterChange?.(chip.key)}
                  className={`rounded-full px-4 py-1.5 font-display text-xs font-bold transition ${
                    activeFilter === chip.key
                      ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                      : "border border-slate-200/80 bg-white text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                  }`}
                >
                  {chip.label}
                </button>
              ))}
            </div>
            {errorMessage && <p className="text-xs font-bold text-rose-500">{errorMessage}</p>}

            {/* Content Cards */}
            {activeFilter === FILTERS.overdue ? (
              <Card className="p-6">
                <h2 className="font-display text-base font-bold text-slate-900 dark:text-white">Contas Atrasadas</h2>
                <div className="mt-4 flex flex-col gap-3">{renderList(overduePayables)}</div>
              </Card>
            ) : (
              <>
                {(activeFilter === FILTERS.all || activeFilter === FILTERS.pending) && (
                  // Duas colunas: fatura e conta comum têm naturezas distintas
                  // (uma o banco mantém, a outra o usuário edita), e lado a lado
                  // dá para bater o olho nas duas sem rolar a página.
                  <div className="grid gap-6 lg:grid-cols-2 items-start">
                    <div className="flex flex-col gap-4">
                      <Card className="p-6">
                        <div className="flex items-baseline justify-between gap-3">
                          <h2 className="font-display text-base font-bold text-slate-900 dark:text-white">Faturas de cartão</h2>
                          <span className="font-display text-sm font-bold text-slate-500 dark:text-slate-400">
                            {fmt(pendingBills.reduce((s, p) => s + Number(p.amount), 0))}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                          Sincronizadas do banco — valor e vencimento são mantidos automaticamente
                        </p>
                        <div className="mt-4 flex flex-col gap-3">{renderList(pendingBills)}</div>

                        {activeFilter === FILTERS.all && paidBills.length > 0 && (
                          <div className="mt-5 border-t border-slate-100 pt-4 dark:border-slate-800/60">
                            <div className="flex items-baseline justify-between gap-3">
                              <p className="font-display text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                                Pagas ({paidBills.length})
                              </p>
                              <span className="font-display text-xs font-bold text-slate-400 dark:text-slate-500">
                                {fmt(paidBills.reduce((s, p) => s + Number(p.amount), 0))}
                              </span>
                            </div>
                            <div className="mt-3 flex flex-col gap-3">{renderList(paidBills)}</div>
                          </div>
                        )}
                      </Card>
                    </div>

                    <div className="flex flex-col gap-4">
                      <Card className="p-6">
                        <div className="flex items-baseline justify-between gap-3">
                          <h2 className="font-display text-base font-bold text-slate-900 dark:text-white">Outras contas</h2>
                          <span className="font-display text-sm font-bold text-slate-500 dark:text-slate-400">
                            {fmt(pendingOthers.reduce((s, p) => s + Number(p.amount), 0))}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                          Contas de valor variável (água, energia) podem ser editadas a cada mês
                        </p>
                        <div className="mt-4 flex flex-col gap-3">{renderList(pendingOthers)}</div>

                        {activeFilter === FILTERS.all && paidOthers.length > 0 && (
                          <div className="mt-5 border-t border-slate-100 pt-4 dark:border-slate-800/60">
                            <div className="flex items-baseline justify-between gap-3">
                              <p className="font-display text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                                Pagas ({paidOthers.length})
                              </p>
                              <span className="font-display text-xs font-bold text-slate-400 dark:text-slate-500">
                                {fmt(paidOthers.reduce((s, p) => s + Number(p.amount), 0))}
                              </span>
                            </div>
                            <div className="mt-3 flex flex-col gap-3">{renderList(paidOthers)}</div>
                          </div>
                        )}
                      </Card>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}