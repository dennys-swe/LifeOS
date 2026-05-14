import { useEffect, useState } from "react";
import api from "../services/api";
import { useFinance } from "../context/FinanceContext";

const INITIAL_FORM = { keyword: "", category_id: "", priority: 0 };

export default function CategoryRulesPage() {
  const { categories } = useFinance();
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const loadRules = async () => {
    try {
      const res = await api.get("/category-rules");
      setRules(res.data ?? []);
    } catch {
      setMessage("Erro ao carregar regras.");
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.category_id) { setMessage("Selecione uma categoria."); return; }
    setLoading(true);
    try {
      await api.post("/category-rules", {
        ...form,
        priority: Number(form.priority),
      });
      setForm(INITIAL_FORM);
      setShowForm(false);
      setMessage("Regra criada com sucesso.");
      await loadRules();
    } catch {
      setMessage("Erro ao criar regra.");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.delete(`/category-rules/${id}`);
      await loadRules();
    } catch {
      setMessage("Erro ao excluir regra.");
    }
  };

  const categoryMap = new Map(categories.map((c) => [c.id, c]));

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Automação</p>
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <h1 className="text-3xl font-semibold text-white">Regras de Categorização</h1>
          <button type="button" onClick={() => setShowForm((v) => !v)}
            className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400">
            + Nova Regra
          </button>
        </div>
        <p className="text-sm text-slate-400">
          Palavras-chave que categorizam transações automaticamente no upload de CSV.
        </p>
        {message && <p className="text-sm text-emerald-400">{message}</p>}
      </header>

      {showForm && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
          <h2 className="text-base font-semibold text-white">Nova Regra</h2>
          <div className="grid gap-4 md:grid-cols-3">
            <label className="text-sm text-slate-300">
              Palavra-chave
              <input type="text" required value={form.keyword} placeholder="ex: SUPERMERCADO"
                onChange={(e) => setForm((p) => ({ ...p, keyword: e.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white uppercase" />
            </label>
            <label className="text-sm text-slate-300">
              Categoria
              <select required value={form.category_id} onChange={(e) => setForm((p) => ({ ...p, category_id: e.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white">
                <option value="">Selecionar...</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="text-sm text-slate-300">
              Prioridade
              <input type="number" min="0" value={form.priority} onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
            </label>
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={loading}
              className="rounded-full bg-emerald-500 px-6 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50">
              {loading ? "Salvando..." : "Salvar"}
            </button>
            <button type="button" onClick={() => setShowForm(false)}
              className="rounded-full border border-slate-700 px-6 py-2 text-sm text-slate-300 hover:bg-slate-900">
              Cancelar
            </button>
          </div>
        </form>
      )}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 overflow-hidden">
        {rules.length === 0 ? (
          <div className="p-6 text-center text-slate-400">
            Nenhuma regra cadastrada. Adicione palavras-chave para categorizar seus extratos automaticamente.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3">Palavra-chave</th>
                <th className="px-4 py-3">Categoria</th>
                <th className="px-4 py-3">Prioridade</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => {
                const cat = categoryMap.get(rule.category_id);
                return (
                  <tr key={rule.id} className="border-b border-slate-800/50 hover:bg-slate-900/40">
                    <td className="px-4 py-3 font-mono text-white">{rule.keyword}</td>
                    <td className="px-4 py-3">
                      {cat ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: cat.color_hex }} />
                          <span className="text-slate-300">{cat.name}</span>
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{rule.priority}</td>
                    <td className="px-4 py-3 text-right">
                      <button type="button" onClick={() => handleDelete(rule.id)}
                        className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-rose-500/60 hover:text-rose-300">
                        Excluir
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
