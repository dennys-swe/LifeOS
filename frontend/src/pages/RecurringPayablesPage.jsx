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

export default function RecurringPayablesPage({ month, year }) {
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

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Automação</p>
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <h1 className="text-3xl font-semibold text-white">Contas Recorrentes</h1>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating}
              className="rounded-full border border-emerald-500/60 px-4 py-2 text-sm font-semibold text-emerald-300 transition hover:bg-emerald-500/10 disabled:opacity-50"
            >
              {generating ? "Gerando..." : `Gerar ${month}/${year}`}
            </button>
            <button
              type="button"
              onClick={() => setShowForm((v) => !v)}
              className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400"
            >
              + Nova Recorrente
            </button>
          </div>
        </div>
        {message && <p className="text-sm text-emerald-400">{message}</p>}
      </header>

      {showForm && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
          <h2 className="text-base font-semibold text-white">Nova Recorrente</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm text-slate-300">
              Título
              <input type="text" required value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
            </label>
            <label className="text-sm text-slate-300">
              Valor (R$)
              <input type="number" step="0.01" required value={form.amount} onChange={(e) => setForm((p) => ({ ...p, amount: e.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
            </label>
            <label className="text-sm text-slate-300">
              Dia do mês (1-31)
              <input type="number" min="1" max="31" required value={form.day_of_month} onChange={(e) => setForm((p) => ({ ...p, day_of_month: e.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
            </label>
            <label className="text-sm text-slate-300">
              Categoria
              <select value={form.category_id} onChange={(e) => setForm((p) => ({ ...p, category_id: e.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white">
                <option value="">Sem categoria</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={form.active} onChange={(e) => setForm((p) => ({ ...p, active: e.target.checked }))} />
              Ativa
            </label>
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={loading}
              className="rounded-full bg-emerald-500 px-6 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:opacity-50">
              {loading ? "Salvando..." : "Salvar"}
            </button>
            <button type="button" onClick={() => setShowForm(false)}
              className="rounded-full border border-slate-700 px-6 py-2 text-sm text-slate-300 hover:bg-slate-900">
              Cancelar
            </button>
          </div>
        </form>
      )}

      <section className="flex flex-col gap-3">
        {recurrings.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-slate-400">
            Nenhuma recorrente cadastrada. Crie uma acima.
          </div>
        ) : (
          recurrings.map((rec) => (
            <div key={rec.id} className={`flex flex-col gap-3 rounded-xl border p-4 md:flex-row md:items-center md:justify-between ${rec.active ? "border-slate-800 bg-slate-950/40" : "border-slate-800/40 bg-slate-950/20 opacity-60"}`}>
              <div>
                <p className="text-sm font-medium text-white">{rec.title}</p>
                <p className="text-xs text-slate-400">Todo dia {rec.day_of_month} · R$ {Number(rec.amount).toFixed(2)}</p>
              </div>
              <div className="flex items-center gap-3">
                <button type="button" onClick={() => handleToggleActive(rec)}
                  className={`rounded-full border px-3 py-1 text-xs transition ${rec.active ? "border-amber-500/40 text-amber-300 hover:bg-amber-500/10" : "border-slate-700 text-slate-400 hover:bg-slate-900"}`}>
                  {rec.active ? "Desativar" : "Ativar"}
                </button>
                <button type="button" onClick={() => handleDelete(rec.id)}
                  className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-rose-500/60 hover:text-rose-300">
                  Excluir
                </button>
              </div>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
