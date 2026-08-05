import { useEffect, useState } from "react";
import api from "../services/api";
import ConfirmModal from "../components/ConfirmModal";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { useFinance } from "../context/FinanceContext";

const DISMISSED_KEY = "lifeos:recurring-suggestions-dismissed";

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
  // Persistido no navegador: sem isso a sugestão dispensada voltava a cada
  // recarregamento, e a lista nunca ficava limpa. Não é por usuário no
  // servidor — é preferência de exibição, não dado financeiro.
  const [dismissed, setDismissed] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? "[]"));
    } catch {
      return new Set();
    }
  });
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
    setDismissed((prev) => {
      const next = new Set(prev).add(title);
      try {
        localStorage.setItem(DISMISSED_KEY, JSON.stringify([...next]));
      } catch {
        // Modo privado/quota cheia: a dispensa vale só nesta sessão.
      }
      return next;
    });
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

  const inputCls = "mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";
  const labelCls = "flex flex-col text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400";

  const categoryMap = new Map(categories.map((c) => [c.id, c]));
  // Recorrente é sempre despesa (aluguel, água, energia). Sem filtrar, a lista
  // oferecia "Salário"/"Renda extra" e dava para criar um recorrente com
  // categoria de receita — que o resto do app trata como entrada.
  const expenseCategories = categories.filter((c) => !c.kind || c.kind === "EXPENSE");

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
            <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">Automação</p>
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Contas Recorrentes</h1>
          </div>
        )}
        <div className={`flex gap-2 ${embedded ? "ml-auto" : ""}`}>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs font-bold text-emerald-600 transition hover:bg-emerald-500/20 disabled:opacity-50 dark:text-emerald-400"
          >
            {generating ? "Gerando..." : `Gerar ${month}/${year}`}
          </button>
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-500"
          >
            + Nova Recorrente
          </button>
        </div>
      </div>

      {message && (
        <p className={`text-xs font-bold ${messageType === "error" ? "text-rose-500" : "text-emerald-600 dark:text-emerald-400"}`}>
          {message}
        </p>
      )}

      {showForm && (
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <h2 className="font-display text-sm font-bold text-slate-900 dark:text-white">Nova Conta Recorrente</h2>
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
                  {expenseCategories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
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
            <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={form.active} onChange={(e) => setForm((p) => ({ ...p, active: e.target.checked }))} className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
              Ativa para geração automática
            </label>
            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={loading} className="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-50">
                {loading ? "Salvando..." : "Salvar Recorrente"}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="rounded-xl border border-slate-200 px-5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800">
                Cancelar
              </button>
            </div>
          </form>
        </Card>
      )}

      {visibleSuggestions.length > 0 && (
        <div className="flex flex-col gap-3">
          <h2 className="font-display text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Sugestões de recorrentes detectadas no extrato
          </h2>
          {visibleSuggestions.map((s) => (
            <div
              key={s.title}
              className="flex flex-col gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 backdrop-blur-md md:flex-row md:items-center md:justify-between"
            >
              <div>
                <p className="text-sm font-bold text-slate-900 dark:text-white">{s.title}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Todo dia {s.day_of_month} · R$ {Number(s.amount).toFixed(2)} · visto em {s.distinct_months} meses
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleAcceptSuggestion(s)}
                  disabled={acceptingTitle === s.title}
                  className="rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white transition hover:bg-emerald-500 disabled:opacity-50"
                >
                  {acceptingTitle === s.title ? "Adicionando..." : "Aceitar"}
                </button>
                <button
                  type="button"
                  onClick={() => handleDismissSuggestion(s.title)}
                  className="rounded-xl border border-slate-200/80 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800"
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
          <EmptyState className="h-auto py-8">Nenhuma recorrente cadastrada.</EmptyState>
        ) : (
          recurrings.map((rec) => {
            const cat = rec.category_id ? categoryMap.get(rec.category_id) : null;
            return (
              <Card key={rec.id} className={`p-4 ${!rec.active ? "opacity-60" : ""}`}>
                {editingRec?.id === rec.id ? (
                  <form onSubmit={handleEditSubmit} className="flex flex-col gap-4">
                    <h3 className="font-display text-sm font-bold text-slate-900 dark:text-white">Editar recorrente</h3>
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
                          {expenseCategories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
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
                    <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
                      <input type="checkbox" checked={editForm.active} onChange={(e) => setEditForm((p) => ({ ...p, active: e.target.checked }))} className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
                      Ativa
                    </label>
                    <div className="flex gap-3">
                      <button type="submit" disabled={loading} className="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-50">
                        {loading ? "Salvando..." : "Salvar Alterações"}
                      </button>
                      <button type="button" onClick={cancelEdit} className="rounded-xl border border-slate-200 px-5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800">
                        Cancelar
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-bold text-slate-900 dark:text-white">{rec.title}</p>
                        {!rec.active && (
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                            Inativa
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                        Todo dia {rec.day_of_month} · R$ {Number(rec.amount).toFixed(2)}
                        {rec.start_date && ` · A partir de ${rec.start_date.slice(0, 7).split("-").reverse().join("/")}`}
                      </p>
                      {cat && (
                        <span
                          className="mt-2 inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                          style={{
                            color: cat.color_hex,
                            backgroundColor: `${cat.color_hex}18`,
                          }}
                        >
                          {cat.name}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => startEdit(rec)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleActive(rec)}
                        className={`rounded-xl border px-3 py-1.5 text-xs font-bold transition ${
                          rec.active
                            ? "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
                            : "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                        }`}
                      >
                        {rec.active ? "Desativar" : "Ativar"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDelete(rec.id)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-500 hover:bg-rose-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-rose-500/10"
                      >
                        Excluir
                      </button>
                    </div>
                  </div>
                )}
              </Card>
            );
          })
        )}
      </div>
    </div>
  );

  if (embedded) return content;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-8">
        {content}
      </div>
    </div>
  );
}
