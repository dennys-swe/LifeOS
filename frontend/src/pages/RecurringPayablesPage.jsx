import { useEffect, useState } from "react";
import api from "../services/api";
import ConfirmModal from "../components/ConfirmModal";
import { useFinance } from "../context/FinanceContext";

const firstOfCurrentMonth = () => {
  return new Date().toLocaleDateString("en-CA").slice(0, 7) + "-01";
};

const INITIAL_FORM = {
  title: "",
  amount: "",
  day_of_month: "",
  category_id: "",
  active: true,
  start_date: firstOfCurrentMonth(),
  end_date: "",
};

export default function RecurringPayablesPage({ month, year, embedded = false }) {
  const { categories, refresh } = useFinance();
  const [recurrings, setRecurrings] = useState([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [showForm, setShowForm] = useState(false);
  const [editingRec, setEditingRec] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("success");
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [dismissed, setDismissed] = useState(new Set());
  const [acceptingTitle, setAcceptingTitle] = useState(null);

  const setMsg = (text, type = "success") => { setMessage(text); setMessageType(type); };

  const loadRecurrings = async () => {
    try {
      const res = await api.get("/recurring-payables");
      setRecurrings(res.data ?? []);
    } catch {
      setMsg("Erro ao carregar recorrentes.", "error");
    }
  };

  const loadSuggestions = async () => {
    try {
      const res = await api.get("/recurring-payables/suggestions");
      setSuggestions(res.data ?? []);
    } catch {
      setSuggestions([]);
    }
  };

  useEffect(() => {
    loadRecurrings();
    loadSuggestions();
  }, []);

  const handleAcceptSuggestion = async (suggestion) => {
    setAcceptingTitle(suggestion.title);
    try {
      await api.post("/recurring-payables", {
        title: suggestion.title,
        amount: Number(suggestion.amount),
        day_of_month: suggestion.day_of_month,
        active: true,
        start_date: firstOfCurrentMonth(),
      });
      setMsg(`"${suggestion.title}" adicionada às recorrentes.`);
      await loadRecurrings();
      await loadSuggestions();
    } catch {
      setMsg("Erro ao aceitar sugestão.", "error");
    } finally {
      setAcceptingTitle(null);
    }
  };

  const handleDismissSuggestion = (title) => {
    setDismissed((prev) => new Set(prev).add(title));
  };

  const visibleSuggestions = suggestions.filter((s) => !dismissed.has(s.title));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/recurring-payables", {
        ...form,
        amount: Number(form.amount),
        day_of_month: Number(form.day_of_month),
        category_id: form.category_id || null,
        end_date: form.end_date || null,
      });
      setForm(INITIAL_FORM);
      setShowForm(false);
      setMsg("Recorrente criada com sucesso.");
      await loadRecurrings();
    } catch {
      setMsg("Erro ao criar recorrente.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.put(`/recurring-payables/${editingRec.id}`, {
        ...editForm,
        amount: Number(editForm.amount),
        day_of_month: Number(editForm.day_of_month),
        category_id: editForm.category_id || null,
        end_date: editForm.end_date || null,
      });
      setEditingRec(null);
      setEditForm(null);
      setMsg("Recorrente atualizada.");
      await loadRecurrings();
    } catch {
      setMsg("Erro ao atualizar.", "error");
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (rec) => {
    setEditingRec(rec);
    setEditForm({
      title: rec.title,
      amount: rec.amount,
      day_of_month: rec.day_of_month,
      category_id: rec.category_id ?? "",
      active: rec.active,
      start_date: rec.start_date ?? firstOfCurrentMonth(),
      end_date: rec.end_date ?? "",
    });
  };

  const cancelEdit = () => { setEditingRec(null); setEditForm(null); };

  const handleToggleActive = async (rec) => {
    try {
      await api.put(`/recurring-payables/${rec.id}`, { active: !rec.active });
      await loadRecurrings();
    } catch {
      setMsg("Erro ao atualizar.", "error");
    }
  };

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;
    try {
      await api.delete(`/recurring-payables/${confirmDelete}`);
      setMsg("Recorrente excluída.");
      await loadRecurrings();
    } catch {
      setMsg("Erro ao excluir.", "error");
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await api.post(`/recurring-payables/generate?month=${month}&year=${year}`);
      const count = res.data?.length ?? 0;
      setMsg(count > 0 ? `${count} conta(s) gerada(s) para ${month}/${year}.` : "Nenhuma nova conta gerada (já existem para este mês).");
      refresh();
    } catch {
      setMsg("Erro ao gerar contas do mês.", "error");
    } finally {
      setGenerating(false);
    }
  };

  const inputCls = "mt-1.5 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";
  const labelCls = "flex flex-col text-sm font-medium text-gray-700 dark:text-slate-300";

  const categoryMap = new Map(categories.map((c) => [c.id, c]));

  const content = (
    <div className="flex flex-col gap-6">
      <ConfirmModal
        open={confirmDelete !== null}
        title="Excluir recorrente?"
        description="Contas já geradas não serão removidas."
        confirmLabel="Excluir"
        variant="danger"
        onCancel={() => setConfirmDelete(null)}
        onConfirm={confirmDeleteAction}
      />

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

      {message && (
        <p className={`text-sm ${messageType === "error" ? "text-rose-500 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
          {message}
        </p>
      )}

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
            <label className={labelCls}>
              A partir de
              <input type="date" required value={form.start_date} onChange={(e) => setForm((p) => ({ ...p, start_date: e.target.value }))} className={inputCls} />
            </label>
            <label className={labelCls}>
              Encerrar em (opcional)
              <input type="date" value={form.end_date} onChange={(e) => setForm((p) => ({ ...p, end_date: e.target.value }))} className={inputCls} />
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

      {visibleSuggestions.length > 0 && (
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-gray-800 dark:text-slate-200">
            Sugestões de recorrentes detectadas no extrato
          </h2>
          {visibleSuggestions.map((s) => (
            <div
              key={s.title}
              className="flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 dark:border-emerald-500/30 dark:bg-emerald-500/5 md:flex-row md:items-center md:justify-between"
            >
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{s.title}</p>
                <p className="text-xs text-gray-500 dark:text-slate-400">
                  Todo dia {s.day_of_month} · R$ {Number(s.amount).toFixed(2)} · visto em {s.distinct_months} meses
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleAcceptSuggestion(s)}
                  disabled={acceptingTitle === s.title}
                  className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-emerald-500 disabled:opacity-50"
                >
                  {acceptingTitle === s.title ? "Adicionando..." : "Aceitar"}
                </button>
                <button
                  type="button"
                  onClick={() => handleDismissSuggestion(s.title)}
                  className="rounded-lg border border-gray-200 px-3 py-1 text-xs text-gray-500 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
                >
                  Descartar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-3">
        {recurrings.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-200 p-6 text-center text-gray-400 dark:border-slate-700 dark:text-slate-500">
            Nenhuma recorrente cadastrada.
          </div>
        ) : (
          recurrings.map((rec) => (
            <div key={rec.id} className="flex flex-col gap-3 rounded-xl border border-gray-100 bg-gray-50 dark:border-slate-800 dark:bg-slate-950/40">
              {editingRec?.id === rec.id ? (
                <form onSubmit={handleEditSubmit} className="flex flex-col gap-4 p-4">
                  <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-200">Editar recorrente</h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className={labelCls}>
                      Título
                      <input type="text" required value={editForm.title} onChange={(e) => setEditForm((p) => ({ ...p, title: e.target.value }))} className={inputCls} />
                    </label>
                    <label className={labelCls}>
                      Valor (R$)
                      <input type="number" step="0.01" required value={editForm.amount} onChange={(e) => setEditForm((p) => ({ ...p, amount: e.target.value }))} className={inputCls} />
                    </label>
                    <label className={labelCls}>
                      Dia do mês (1–31)
                      <input type="number" min="1" max="31" required value={editForm.day_of_month} onChange={(e) => setEditForm((p) => ({ ...p, day_of_month: e.target.value }))} className={inputCls} />
                    </label>
                    <label className={labelCls}>
                      Categoria
                      <select value={editForm.category_id} onChange={(e) => setEditForm((p) => ({ ...p, category_id: e.target.value }))} className={inputCls}>
                        <option value="">Sem categoria</option>
                        {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </label>
                    <label className={labelCls}>
                      A partir de
                      <input type="date" required value={editForm.start_date} onChange={(e) => setEditForm((p) => ({ ...p, start_date: e.target.value }))} className={inputCls} />
                    </label>
                    <label className={labelCls}>
                      Encerrar em (opcional)
                      <input type="date" value={editForm.end_date} onChange={(e) => setEditForm((p) => ({ ...p, end_date: e.target.value }))} className={inputCls} />
                    </label>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-300">
                    <input type="checkbox" checked={editForm.active} onChange={(e) => setEditForm((p) => ({ ...p, active: e.target.checked }))} />
                    Ativa
                  </label>
                  <div className="flex gap-3">
                    <button type="submit" disabled={loading} className="rounded-xl bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
                      {loading ? "Salvando..." : "Salvar"}
                    </button>
                    <button type="button" onClick={cancelEdit} className="rounded-xl border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
                      Cancelar
                    </button>
                  </div>
                </form>
              ) : (
                <div className={`flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between ${!rec.active ? "opacity-50" : ""}`}>
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{rec.title}</p>
                    <p className="text-xs text-gray-500 dark:text-slate-400">
                      Todo dia {rec.day_of_month} · R$ {Number(rec.amount).toFixed(2)}
                      {!rec.active && <span className="ml-2 text-gray-400 dark:text-slate-600">(inativa)</span>}
                    </p>
                    {rec.start_date && (
                      <p className="text-xs text-gray-400 dark:text-slate-500">
                        A partir de {rec.start_date.slice(0, 7).split("-").reverse().join("/")}
                        {rec.end_date && ` · até ${rec.end_date.slice(0, 7).split("-").reverse().join("/")}`}
                      </p>
                    )}
                    {rec.category_id && categoryMap.get(rec.category_id) && (
                      <span
                        className="mt-2 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                        style={{
                          borderColor: `${categoryMap.get(rec.category_id).color_hex}80`,
                          color: categoryMap.get(rec.category_id).color_hex,
                          backgroundColor: `${categoryMap.get(rec.category_id).color_hex}15`,
                        }}
                      >
                        {categoryMap.get(rec.category_id).name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => startEdit(rec)}
                      className="rounded-lg border border-gray-200 px-3 py-1 text-xs text-gray-500 transition hover:border-emerald-300 hover:text-emerald-700 dark:border-slate-700 dark:text-slate-400 dark:hover:border-emerald-500/60 dark:hover:text-emerald-400"
                    >
                      Editar
                    </button>
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
                      onClick={() => setConfirmDelete(rec.id)}
                      className="rounded-lg px-3 py-1 text-xs text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20"
                    >
                      Excluir
                    </button>
                  </div>
                </div>
              )}
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
