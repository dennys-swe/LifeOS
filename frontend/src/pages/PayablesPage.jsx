import { useEffect, useMemo, useRef, useState } from "react";

import api from "../services/api";
import ConfirmModal from "../components/ConfirmModal";
import MonthNavigator from "../components/MonthNavigator";
import StatusBadge from "../components/StatusBadge";
import Toast from "../components/Toast";

const FILTERS = {
  all: "all",
  pending: "pending",
  overdue: "overdue",
};

export default function PayablesPage({
  refreshKey,
  filter,
  onFilterChange,
  month,
  year,
  onMonthChange,
}) {
  const [payables, setPayables] = useState([]);
  const [categories, setCategories] = useState([]);
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");
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

  useEffect(() => {
    let mounted = true;

    const loadData = async () => {
      setStatus("loading");
      try {
        const [payablesResponse, categoriesResponse] = await Promise.all([
          api.get("/payables", { params: { month, year } }),
          api.get("/categories"),
        ]);
        if (!mounted) return;
        setPayables(payablesResponse.data ?? []);
        setCategories(categoriesResponse.data ?? []);
        setStatus("success");
        setMessage("");
      } catch (error) {
        if (!mounted) return;
        setStatus("error");
        setMessage("Falha ao carregar contas.");
      }
    };

    loadData();

    return () => {
      mounted = false;
    };
  }, [refreshKey, month, year]);

  useEffect(() => {
    return () => {
      if (pendingDeleteRef.current) {
        clearTimeout(pendingDeleteRef.current.timer);
      }
    };
  }, []);

  const payablesThisMonth = useMemo(() => {
    return payables.filter((item) => {
      const dueDate = new Date(item.due_date);
      if (Number.isNaN(dueDate.getTime())) return false;
      return dueDate.getMonth() + 1 === month && dueDate.getFullYear() === year;
    });
  }, [payables, month, year]);

  const activeFilter = filter ?? FILTERS.all;

  const dueTodayCount = useMemo(() => {
    const today = new Date();
    if (today.getMonth() + 1 !== month || today.getFullYear() !== year) {
      return 0;
    }
    return payablesThisMonth.filter((item) => {
      const dueDate = new Date(item.due_date);
      return (
        dueDate.getDate() === today.getDate() &&
        dueDate.getMonth() === today.getMonth() &&
        dueDate.getFullYear() === today.getFullYear()
      );
    }).length;
  }, [payablesThisMonth, month, year]);

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
    } catch (error) {
      setStatus("error");
      setMessage("Falha ao excluir conta.");
    }
  };

  const confirmAction = async () => {
    if (!confirmState.payableId) return;

    if (confirmState.action === "delete") {
      await finalizePendingDelete();
      const deleted = payables.find((item) => item.id === confirmState.payableId);
      setPayables((prev) =>
        prev.filter((item) => item.id !== confirmState.payableId)
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
        setPayables((prev) =>
          prev.map((item) =>
            item.id === confirmState.payableId
              ? { ...item, status: "PAID", payment_date: today }
              : item
          )
        );
      } catch (error) {
        setStatus("error");
        setMessage("Falha ao marcar como pago.");
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
      setPayables((prev) => [item, ...prev]);
    }
    setToastState({ open: false, message: "", actionLabel: "" });
  };

  const renderList = (items) => {
    if (items.length === 0) {
      return (
        <div className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-slate-400">
          Nenhuma conta encontrada.
        </div>
      );
    }

    return items.map((item) => {
      const dueDate = new Date(item.due_date);
      const today = new Date();
      const dueDateOnly = new Date(
        dueDate.getFullYear(),
        dueDate.getMonth(),
        dueDate.getDate()
      );
      const todayOnly = new Date(
        today.getFullYear(),
        today.getMonth(),
        today.getDate()
      );
      const isDueToday =
        dueDate.getDate() === today.getDate() &&
        dueDate.getMonth() === today.getMonth() &&
        dueDate.getFullYear() === today.getFullYear();
      const isOverdue = item.status === "PENDING" && dueDateOnly < todayOnly;

      return (
        <div
          key={item.id}
          className={`flex flex-col gap-3 rounded-xl border bg-slate-950/40 p-4 transition-all md:flex-row md:items-center md:justify-between ${
            isDueToday ? "border-amber-400/70" : "border-slate-800"
          }`}
        >
          <div>
            <p className="text-sm font-medium text-white">{item.title}</p>
            <p className="text-xs text-slate-400">
              Vence em {new Date(item.due_date).toLocaleDateString("pt-BR")}
            </p>
            {item.category_id && categoryMap.get(item.category_id) && (
              <span
                className="mt-2 inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide"
                style={{
                  borderColor: `${categoryMap.get(item.category_id).color_hex}80`,
                  color: categoryMap.get(item.category_id).color_hex,
                  backgroundColor: `${categoryMap.get(item.category_id).color_hex}20`,
                }}
              >
                {categoryMap.get(item.category_id).name}
              </span>
            )}
            <StatusBadge
              status={item.status}
              isOverdue={isOverdue}
              isDueToday={isDueToday}
            />
          </div>
          <div className="flex items-center gap-4">
            <p
              className={`text-base font-semibold ${
                item.status === "PAID"
                  ? "text-emerald-400"
                  : isOverdue
                  ? "text-rose-500"
                  : "text-amber-400"
              }`}
            >
              {formatCurrency(Number(item.amount) || 0)}
            </p>
            {item.status !== "PAID" && (
              <button
                type="button"
                onClick={() => handleMarkPaid(item.id)}
                className="rounded-full border border-emerald-500/40 px-3 py-1 text-xs text-emerald-300 transition hover:border-emerald-400 hover:bg-emerald-500/10"
                title="Marcar como pago"
              >
                Baixa
              </button>
            )}
            <button
              type="button"
              onClick={() => handleDelete(item.id)}
              className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-rose-500/60 hover:text-rose-300"
            >
              Excluir
            </button>
          </div>
        </div>
      );
    });
  };

  const pendingPayables = useMemo(() => {
    return payablesThisMonth
      .filter((item) => item.status === "PENDING")
      .sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
  }, [payablesThisMonth]);

  const paidPayables = useMemo(() => {
    return payablesThisMonth
      .filter((item) => item.status === "PAID")
      .sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
  }, [payablesThisMonth]);

  const overduePayables = useMemo(() => {
    const today = new Date();
    const todayOnly = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate()
    );
    return pendingPayables.filter((item) => {
      const dueDate = new Date(item.due_date);
      const dueDateOnly = new Date(
        dueDate.getFullYear(),
        dueDate.getMonth(),
        dueDate.getDate()
      );
      return dueDateOnly < todayOnly;
    });
  }, [pendingPayables]);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 py-10">
      <ConfirmModal
        open={confirmState.open}
        title={
          confirmState.action === "paid"
            ? "Marcar conta como paga?"
            : "Tem certeza que deseja excluir?"
        }
        description={
          confirmState.action === "paid"
            ? "Essa acao atualiza o status para PAGO."
            : "Essa acao nao pode ser desfeita."
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
      <header className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.4em] text-slate-500">
          Contas a pagar
        </p>
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <h1 className="text-3xl font-semibold text-white md:text-4xl">
            Contas do mes selecionado
          </h1>
          <MonthNavigator month={month} year={year} onChange={onMonthChange} />
        </div>
        <p className="text-sm text-amber-300">
          {dueTodayCount} contas vencendo hoje
        </p>
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
              className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
                activeFilter === chip.key
                  ? "bg-emerald-500/20 text-emerald-300"
                  : "border border-slate-700 text-slate-300 hover:bg-slate-900"
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>
        {status === "error" && (
          <p className="text-sm text-rose-400">{message}</p>
        )}
      </header>

      {activeFilter === FILTERS.overdue ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
          <h2 className="text-lg font-semibold text-white">Atrasadas</h2>
          <div className="mt-4 flex flex-col gap-3">
            {renderList(overduePayables)}
          </div>
        </section>
      ) : (
        <>
          {(activeFilter === FILTERS.all || activeFilter === FILTERS.pending) && (
            <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
              <h2 className="text-lg font-semibold text-white">Pendentes</h2>
              <div className="mt-4 flex flex-col gap-3">
                {renderList(pendingPayables)}
              </div>
            </section>
          )}
          {activeFilter === FILTERS.all && (
            <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
              <h2 className="text-lg font-semibold text-white">Pagas</h2>
              <div className="mt-4 flex flex-col gap-3">
                {renderList(paidPayables)}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
