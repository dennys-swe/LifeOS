import { useEffect, useMemo, useRef, useState } from "react";

import api from "../services/api";
import ConfirmModal from "../components/ConfirmModal";
import MonthNavigator from "../components/MonthNavigator";
import StatusBadge from "../components/StatusBadge";
import Toast from "../components/Toast";
import { useFinance } from "../context/FinanceContext";
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
      }
    };
  }, []);

  // FILTRO DE MÊS: Usa split para evitar bug de fuso
  const payablesThisMonth = useMemo(() => {
    return payables.filter((item) => {
      if (!item.due_date) return false;
      const [itemYear, itemMonth] = item.due_date.split('-').map(Number);
      return itemMonth === month && itemYear === year;
    });
  }, [payables, month, year]);

  const activeFilter = filter ?? FILTERS.all;

  // CONTADOR DE HOJE: Comparação direta de strings
  const dueTodayCount = useMemo(() => {
    return payablesThisMonth.filter((item) => item.due_date === todayStr).length;
  }, [payablesThisMonth, todayStr]);

  const formatCurrency = (value) => {
    return value.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
    });
  };

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
        message: "Item excluido.",
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

  const renderList = (items) => {
    if (items.length === 0) {
      return (
        <div className="rounded-xl border border-dashed border-gray-200 p-6 text-center text-gray-400 dark:border-slate-700 dark:text-slate-500">
          Nenhuma conta encontrada.
        </div>
      );
    }

    return items.map((item) => {
      const [yearPart, monthPart, dayPart] = item.due_date.split('-');
      const formattedDate = `${dayPart}/${monthPart}/${yearPart}`;
      const isDueToday = item.due_date === todayStr;
      const isOverdue = item.status === "PENDING" && item.due_date < todayStr;

      return (
        <div
          key={item.id}
          className={`flex flex-col gap-3 rounded-xl border p-4 transition-all md:flex-row md:items-center md:justify-between ${
            isDueToday
              ? "border-amber-300 bg-amber-50/50 dark:border-amber-400/50 dark:bg-amber-500/5"
              : "border-gray-100 bg-gray-50 dark:border-slate-800 dark:bg-slate-950/40"
          }`}
        >
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{item.title}</p>
            <p className="text-xs text-gray-500 dark:text-slate-400">Vence em {formattedDate}</p>
            {item.category_id && categoryMap.get(item.category_id) && (
              <span
                className="mt-2 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{
                  borderColor: `${categoryMap.get(item.category_id).color_hex}80`,
                  color: categoryMap.get(item.category_id).color_hex,
                  backgroundColor: `${categoryMap.get(item.category_id).color_hex}15`,
                }}
              >
                {categoryMap.get(item.category_id).name}
              </span>
            )}
            <StatusBadge status={item.status} isOverdue={isOverdue} isDueToday={isDueToday} />
          </div>
          <div className="flex items-center gap-3">
            <p className={`text-base font-semibold ${
              item.status === "PAID"
                ? "text-emerald-600 dark:text-emerald-400"
                : isOverdue
                ? "text-rose-600 dark:text-rose-400"
                : "text-amber-600 dark:text-amber-400"
            }`}>
              {formatCurrency(Number(item.amount) || 0)}
            </p>
            {item.status !== "PAID" && (
              <button
                type="button"
                onClick={() => handleMarkPaid(item.id)}
                className="rounded-lg border border-emerald-300 px-3 py-1 text-xs font-medium text-emerald-700 transition hover:bg-emerald-50 dark:border-emerald-500/40 dark:text-emerald-400 dark:hover:bg-emerald-500/10"
              >
                Baixa
              </button>
            )}
            <button
              type="button"
              onClick={() => handleDelete(item.id)}
              className="rounded-lg border border-gray-200 px-3 py-1 text-xs text-gray-500 transition hover:border-rose-300 hover:text-rose-600 dark:border-slate-700 dark:text-slate-400 dark:hover:border-rose-500/60 dark:hover:text-rose-400"
            >
              Excluir
            </button>
          </div>
        </div>
      );
    });
  };

  // Ordenação usando localeCompare para strings ISO
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

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <ConfirmModal
        open={confirmState.open}
        title={
          confirmState.action === "paid"
            ? "Marcar conta como paga?"
            : "Tem certeza que deseja excluir?"
        }
        description={
          confirmState.action === "paid"
            ? "Essa ação atualiza o status para PAGO."
            : "Essa ação não pode ser desfeita."
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

      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
        {/* Header */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 dark:text-slate-500">Contas a pagar</p>
            <h1 className="mt-1 text-2xl font-semibold text-gray-900 dark:text-slate-100">Contas</h1>
          </div>
          <MonthNavigator month={month} year={year} onChange={onMonthChange} />
        </header>

        {/* Tab bar */}
        <div className="flex gap-1 rounded-xl border border-gray-200 bg-white p-1 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          {[{ key: "payables", label: "Contas do mês" }, { key: "recurring", label: "Recorrentes" }].map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === key
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-gray-500 hover:text-gray-800 dark:text-slate-400 dark:hover:text-slate-200"
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
              <p className="text-sm font-medium text-amber-600 dark:text-amber-400">
                {dueTodayCount} conta{dueTodayCount > 1 ? "s" : ""} vencendo hoje
              </p>
            )}
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
                  className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                    activeFilter === chip.key
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
                      : "border border-gray-200 text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
                  }`}
                >
                  {chip.label}
                </button>
              ))}
            </div>
            {errorMessage && <p className="text-sm text-rose-500 dark:text-rose-400">{errorMessage}</p>}

            {activeFilter === FILTERS.overdue ? (
              <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <h2 className="text-base font-semibold text-gray-900 dark:text-slate-100">Atrasadas</h2>
                <div className="mt-4 flex flex-col gap-3">{renderList(overduePayables)}</div>
              </section>
            ) : (
              <>
                {(activeFilter === FILTERS.all || activeFilter === FILTERS.pending) && (
                  <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <h2 className="text-base font-semibold text-gray-900 dark:text-slate-100">Pendentes</h2>
                    <div className="mt-4 flex flex-col gap-3">{renderList(pendingPayables)}</div>
                  </section>
                )}
                {activeFilter === FILTERS.all && (
                  <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <h2 className="text-base font-semibold text-gray-900 dark:text-slate-100">Pagas</h2>
                    <div className="mt-4 flex flex-col gap-3">{renderList(paidPayables)}</div>
                  </section>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}