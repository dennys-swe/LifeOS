import { useState } from "react";
import api from "../services/api";

const INPUT_CLASS =
  "mt-2 w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-slate-700 dark:bg-slate-950 dark:text-white";

const LABEL_CLASS = "text-sm text-gray-700 dark:text-slate-300";

export default function EditPayableModal({ payable, categories = [], onClose, onSaved }) {
  const [form, setForm] = useState({
    title: payable.title ?? "",
    amount: payable.amount ?? "",
    due_date: payable.due_date ?? "",
    status: payable.status ?? "PENDING",
    payment_date: payable.payment_date ?? "",
    category_id: payable.category_id ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [makingRecurring, setMakingRecurring] = useState(false);
  const [recurringMsg, setRecurringMsg] = useState({ text: "", type: "" });

  const set = (field) => (e) => setForm((p) => ({ ...p, [field]: e.target.value }));

  const handleMakeRecurring = async () => {
    if (!form.due_date) return;
    const day = Number(form.due_date.split("-")[2]);
    setMakingRecurring(true);
    setRecurringMsg({ text: "", type: "" });
    try {
      await api.post("/recurring-payables", {
        title: form.title,
        amount: Number(form.amount),
        day_of_month: day,
        category_id: form.category_id || null,
        active: true,
      });
      setRecurringMsg({ text: "Recorrente criada com sucesso!", type: "success" });
    } catch {
      setRecurringMsg({ text: "Não foi possível criar recorrente.", type: "error" });
    } finally {
      setMakingRecurring(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.put(`/payables/${payable.id}`, {
        title: form.title,
        amount: Number(form.amount),
        due_date: form.due_date,
        status: form.status,
        payment_date: form.payment_date || null,
        category_id: form.category_id || null,
      });
      onSaved();
      onClose();
    } catch {
      setError("Não foi possível salvar. Tente novamente.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center overflow-y-auto bg-slate-950/80 px-4 py-6">
      <div className="my-auto w-full max-w-xl rounded-2xl border border-gray-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
        <div className="p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-gray-400 dark:text-slate-500">Conta a pagar</p>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Editar conta</h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              Fechar
            </button>
          </div>

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
            <label className={LABEL_CLASS}>
              Título
              <input type="text" required value={form.title} onChange={set("title")} className={INPUT_CLASS} />
            </label>

            <label className={LABEL_CLASS}>
              Valor
              <input type="number" step="0.01" required value={form.amount} onChange={set("amount")} className={INPUT_CLASS} />
            </label>

            <label className={LABEL_CLASS}>
              Vencimento
              <input type="date" required value={form.due_date} onChange={set("due_date")} className={INPUT_CLASS} />
            </label>

            <label className={LABEL_CLASS}>
              Status
              <select value={form.status} onChange={set("status")} className={INPUT_CLASS}>
                <option value="PENDING">Pendente</option>
                <option value="PAID">Pago</option>
              </select>
            </label>

            <label className={LABEL_CLASS}>
              Data de pagamento (opcional)
              <input type="date" value={form.payment_date} onChange={set("payment_date")} className={INPUT_CLASS} />
            </label>

            <label className={LABEL_CLASS}>
              Categoria
              <select value={form.category_id} onChange={set("category_id")} className={INPUT_CLASS}>
                <option value="">Sem categoria</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>

            {error && (
              <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-400">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={saving}
              className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Salvando..." : "Salvar alterações"}
            </button>

            <div className="border-t border-gray-100 pt-2 dark:border-slate-800">
              <p className="mb-2 text-xs text-gray-400 dark:text-slate-500">Repetir todo mês automaticamente</p>
              <button
                type="button"
                disabled={makingRecurring || !form.title || !form.amount || !form.due_date}
                onClick={handleMakeRecurring}
                className="w-full rounded-full border border-emerald-300 px-6 py-2.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-emerald-500/40 dark:text-emerald-400 dark:hover:bg-emerald-500/10"
              >
                {makingRecurring ? "Criando..." : "↻ Tornar recorrente"}
              </button>
              {recurringMsg.text && (
                <p className={`mt-2 text-xs ${recurringMsg.type === "success" ? "text-emerald-600 dark:text-emerald-400" : "text-rose-500 dark:text-rose-400"}`}>
                  {recurringMsg.text}
                </p>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
