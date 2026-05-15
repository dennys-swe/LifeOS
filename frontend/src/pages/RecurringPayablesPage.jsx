import { useEffect, useState } from "react";
import api from "../services/api";
import { useFinance } from "../context/FinanceContext";

const INITIAL_FORM = {
  title: "",
  amount: "",
  day_of_month: "",
  category_id: "",
  active: true,
};

export default function RecurringPayablesPage({ month, year, embedded = false }) {
  const { categories, refresh } = useFinance();
  const [recurrings, setRecurrings] = useState([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState("");

  const loadRecurrings = async () => {
    try {
      const res = await api.get("/recurring-payables");
      setRecurrings(res.data ?? []);
    } catch {
      setMessage("Erro ao carregar recorrentes.");
    }
  };

  useEffect(() => {
    loadRecurrings();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/recurring-payables", {
        ...form,
        amount: Number(form.amount),
        day_of_month: Number(form.day_of_month),
        category_id: form.category_id || null,
      });
      setForm(INITIAL_FORM);
      setShowForm(false);
      setMessage("Recorrente criada com sucesso.");
      await loadRecurrings();
    } catch {
      setMessage("Erro ao criar recorrente.");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (rec) => {
    try {
      await api.put(`/recurring-payables/${rec.id}`, { active: !rec.active });
      await loadRecurrings();
    } catch {
      setMessage("Erro ao atualizar.");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Excluir esta recorrente?")) return;
    try {
      await api.delete(`/recurring-payables/${id}`);
      await loadRecurrings();
    } catch {
      setMessage("Erro ao excluir.");
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await api.post(`/recurring-payables/generate?month=${month}&year=${year}`);
      const count = res.data?.length ?? 0;
      setMessage(count > 0 ? `${count} conta(s) gerada(s) para ${month}/${year}.` : "Nenhuma nova conta gerada (já existem para este mês).");
      refresh();
    } catch {
      setMessage("Erro ao gerar contas do mês.");
    } finally {
      setGenerating(false);
    }
  };

  const inputCls = "mt-1.5 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";
  const labelCls = "flex flex-col text-sm font-medium text-gray-700 dark:text-slate-300";

  const content = (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {!embedded && (
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 dark:text-slate-500">Automação</p>
            <h1 className="mt-1 text-2xl font-semibold text-gray-900 dark:text-slate-100">Contas Recorrentes</h1>
          </div>
        )}
        <div className={`flex gap-2 ${embedded ? "ml-auto" : ""}`}>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-xl border border-emerald-300 px-4 py-2 text-sm font-medium text-emerald-700 transition hover:bg-emerald-50 disabled:opacity-50 dark:border-emerald-500/60 dark:text-emerald-400 dark:hover:bg-emerald-500/10"
          >
            {generating ? "Gerando..." : `Gerar ${month}/${year}`}
          </button>
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
          >
            + Nova
          </button>
        </div>
      </div>

      {message && <p className="text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}

      {showForm && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-2xl border border-gray-200 bg-gray-50 p-5 dark:border-slate-700 dark:bg-slate-800/50">
          <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-200">Nova Recorrente</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <label className={labelCls}>
              Título
              <input type="text" required value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} className={inputCls} />
            </label>
            <label className={labelCls}>
              Valor (R$)
              <input type="number" step="0.01" required value={form.amount} onChange={(e) => setForm((p) => ({ ...p, amount: e.target.value }))} className={inputCls} />
            </label>
            <label className={labelCls}>
              Dia do mês (1–31)
              <input type="number" min="1" max="31" required value={form.day_of_month} onChange={(e) => setForm((p) => ({ ...p, day_of_month: e.target.value }))} className={inputCls} />
            </label>
            <label className={labelCls}>
              Categoria
              <select value={form.category_id} onChange={(e) => setForm((p) => ({ ...p, category_id: e.target.value }))} className={inputCls}>
                <option value="">Sem categoria</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-300">
            <input type="checkbox" checked={form.active} onChange={(e) => setForm((p) => ({ ...p, active: e.target.checked }))} />
            Ativa
          </label>
          <div className="flex gap-3">
            <button type="submit" disabled={loading} className="rounded-xl bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
              {loading ? "Salvando..." : "Salvar"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="rounded-xl border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
              Cancelar
            </button>
          </div>
        </form>
      )}

      <div className="flex flex-col gap-3">
        {recurrings.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-200 p-6 text-center text-gray-400 dark:border-slate-700 dark:text-slate-500">
            Nenhuma recorrente cadastrada.
          </div>
        ) : (
          recurrings.map((rec) => (
            <div
              key={rec.id}
              className={`flex flex-col gap-3 rounded-xl border p-4 md:flex-row md:items-center md:justify-between ${
                rec.active
                  ? "border-gray-100 bg-gray-50 dark:border-slate-800 dark:bg-slate-950/40"
                  : "border-gray-100 bg-gray-50 opacity-50 dark:border-slate-800 dark:bg-slate-950/40"
              }`}
            >
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{rec.title}</p>
                <p className="text-xs text-gray-500 dark:text-slate-400">
                  Todo dia {rec.day_of_month} · R$ {Number(rec.amount).toFixed(2)}
                  {!rec.active && <span className="ml-2 text-gray-400 dark:text-slate-600">(inativa)</span>}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleToggleActive(rec)}
                  className={`rounded-lg border px-3 py-1 text-xs font-medium transition ${
                    rec.active
                      ? "border-amber-200 text-amber-700 hover:bg-amber-50 dark:border-amber-500/40 dark:text-amber-400 dark:hover:bg-amber-500/10"
                      : "border-gray-200 text-gray-500 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-900"
                  }`}
                >
                  {rec.active ? "Desativar" : "Ativar"}
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(rec.id)}
                  className="rounded-lg px-3 py-1 text-xs text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20"
                >
                  Excluir
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );

  if (embedded) return content;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-8">
        {content}
      </div>
    </div>
  );
}
