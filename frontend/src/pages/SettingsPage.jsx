import { useEffect, useState } from "react";
import api from "../services/api";
import Card from "../components/ui/Card";
import CategoryDot from "../components/ui/CategoryDot";
import EmptyState from "../components/ui/EmptyState";
import { useFinance } from "../context/FinanceContext";

const TABS = ["Regras de Categorização", "Categorias", "Notificações Push"];

// ─── Notifications ────────────────────────────────────────────────────────────

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  return window.btoa(String.fromCharCode(...bytes));
}

const PUSH_SUPPORTED =
  typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window;

function NotificationsTab() {
  const [subscribed, setSubscribed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!PUSH_SUPPORTED) return;
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => setSubscribed(!!sub))
      .catch(() => {});
  }, []);

  async function handleEnable() {
    setLoading(true);
    setMsg("");
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setMsg("Permissão de notificação negada no navegador.");
        return;
      }

      const { data } = await api.get("/push-subscriptions/vapid-public-key");
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(data.public_key),
      });

      await api.post("/push-subscriptions", {
        endpoint: subscription.endpoint,
        p256dh: arrayBufferToBase64(subscription.getKey("p256dh")),
        auth: arrayBufferToBase64(subscription.getKey("auth")),
      });

      setSubscribed(true);
      setMsg("Notificações ativadas com sucesso neste dispositivo.");
    } catch {
      setMsg("Não foi possível ativar as notificações.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDisable() {
    setLoading(true);
    setMsg("");
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      await subscription?.unsubscribe();
      setSubscribed(false);
      setMsg("Notificações desativadas neste dispositivo.");
    } catch {
      setMsg("Não foi possível desativar as notificações.");
    } finally {
      setLoading(false);
    }
  }

  if (!PUSH_SUPPORTED) {
    return (
      <Card className="p-6">
        <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
          Este navegador não suporta notificações push via Service Worker.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-6 flex flex-col gap-4">
      <div>
        <h2 className="font-display text-base font-bold text-slate-900 dark:text-white">Alertas do Sistema</h2>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          Receba avisos automáticos antes do vencimento das suas obrigações.
        </p>
      </div>

      <div className="flex items-center justify-between rounded-2xl border border-slate-200/80 bg-slate-50/50 px-5 py-4 dark:border-slate-800/80 dark:bg-slate-900/40">
        <div>
          <p className="text-sm font-bold text-slate-900 dark:text-white">Contas a Vencer</p>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            {subscribed ? "Ativas neste navegador" : "Desativadas"}
          </p>
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={subscribed ? handleDisable : handleEnable}
          className={`rounded-xl px-4 py-2 text-xs font-bold transition disabled:opacity-50 ${
            subscribed
              ? "border border-slate-200 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              : "bg-emerald-600 text-white shadow-sm hover:bg-emerald-500"
          }`}
        >
          {loading ? "Aguarde..." : subscribed ? "Desativar" : "Ativar Alertas"}
        </button>
      </div>
      {msg && <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400">{msg}</p>}
    </Card>
  );
}

// ─── Category Rules ───────────────────────────────────────────────────────────

const RULE_INITIAL = { keyword: "", category_id: "", priority: 0 };

function RulesTab() {
  const { categories, refresh } = useFinance();
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState(RULE_INITIAL);
  const [showForm, setShowForm] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    const res = await api.get("/category-rules").catch(() => ({ data: [] }));
    setRules(res.data ?? []);
  };

  // load() só chama setState depois de um await (fetch da lista de regras) — não
  // é o setState síncrono em cascata que a regra tenta evitar.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.category_id) { setMsg("Selecione uma categoria."); return; }
    const res = await api
      .post("/category-rules", { ...form, priority: Number(form.priority) })
      .catch(() => null);
    setForm(RULE_INITIAL);
    setShowForm(false);
    if (res === null) {
      setMsg("Não foi possível criar a regra.");
    } else {
      // Sem informar quantos lançamentos mudaram, a regra parece não ter feito
      // nada: o efeito dela está no extrato, não nesta tela.
      const n = res.data?.applied_count ?? 0;
      setMsg(
        n > 0
          ? `Regra criada — ${n} ${n === 1 ? "lançamento existente foi reclassificado" : "lançamentos existentes foram reclassificados"}.`
          : "Regra criada. Nenhum lançamento existente casou com ela; vale para as próximas sincronizações."
      );
    }
    load();
    // O gasto por categoria muda quando lançamentos trocam de categoria.
    refresh?.();
  };

  const handleDelete = async (id) => {
    await api.delete(`/category-rules/${id}`).catch(() => null);
    load();
  };

  const catMap = new Map(categories.map((c) => [c.id, c]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Mapeamento automático de palavras-chave para categorização na sincronização bancária.
        </p>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-500"
        >
          + Nova Regra
        </button>
      </div>

      {msg && <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400">{msg}</p>}

      {showForm && (
        <Card className="p-5">
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-3">
            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Palavra-chave
              <input
                type="text"
                required
                value={form.keyword}
                placeholder="ex: SUPERMERCADO"
                onChange={(e) => setForm((p) => ({ ...p, keyword: e.target.value }))}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold uppercase text-slate-900 focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-white"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Categoria
              <select
                required
                value={form.category_id}
                onChange={(e) => setForm((p) => ({ ...p, category_id: e.target.value }))}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-900 focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-white"
              >
                <option value="">Selecionar...</option>
                {/* Agrupado por tipo: a regra só vale para lançamentos da mesma
                    direção, então escolher "Renda extra" para uma despesa não
                    teria efeito nenhum e pareceria bug. */}
                <optgroup label="Despesa">
                  {categories
                    .filter((c) => !c.kind || c.kind === "EXPENSE")
                    .map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </optgroup>
                <optgroup label="Receita">
                  {categories
                    .filter((c) => c.kind === "INCOME")
                    .map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </optgroup>
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Prioridade
              <input
                type="number"
                min="0"
                value={form.priority}
                onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-900 focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-white"
              />
            </label>
            <div className="flex gap-3 sm:col-span-3 pt-2">
              <button type="submit" className="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white hover:bg-emerald-500">
                Salvar Regra
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="rounded-xl border border-slate-200 px-5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800">
                Cancelar
              </button>
            </div>
          </form>
        </Card>
      )}

      <Card className="p-4 overflow-hidden">
        {rules.length === 0 ? (
          <EmptyState className="h-auto py-8">Nenhuma regra cadastrada.</EmptyState>
        ) : (
          <div className="flex flex-col gap-2">
            {rules.map((rule) => {
              const cat = catMap.get(rule.category_id);
              return (
                <div key={rule.id} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3.5 dark:border-slate-800/40 dark:bg-slate-900/40">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold uppercase text-slate-900 dark:text-white">{rule.keyword}</span>
                    {cat ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                        <CategoryDot color={cat.color_hex} />
                        {cat.name}
                      </span>
                    ) : <span className="text-xs text-slate-400">—</span>}
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400">Prio: {rule.priority}</span>
                    <button
                      type="button"
                      onClick={() => handleDelete(rule.id)}
                      className="rounded-lg px-2.5 py-1 text-xs font-semibold text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10"
                    >
                      Excluir
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

// ─── Categories ───────────────────────────────────────────────────────────────

const CAT_INITIAL = { name: "", color_hex: "#10b981" };
const PRESET_COLORS = ["#10b981", "#f59e0b", "#3b82f6", "#ec4899", "#8b5cf6", "#14b8a6", "#f97316", "#84cc16"];

function CategoriesTab() {
  const { categories, refresh } = useFinance();
  const [form, setForm] = useState(CAT_INITIAL);
  const [showForm, setShowForm] = useState(false);
  const [msg, setMsg] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    await api.post("/categories", form).catch(() => null);
    setForm(CAT_INITIAL);
    setShowForm(false);
    setMsg("Categoria criada com sucesso.");
    refresh();
  };

  const handleDelete = async (id) => {
    await api.delete(`/categories/${id}`).catch(() => null);
    setMsg("Categoria removida.");
    refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Categorias para classificação das movimentações e orçamentos.
        </p>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-500"
        >
          + Nova Categoria
        </button>
      </div>

      {msg && <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400">{msg}</p>}

      {showForm && (
        <Card className="p-5">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Nome
                <input
                  type="text"
                  required
                  value={form.name}
                  placeholder="ex: Mercado"
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-900 focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Cor
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 flex-shrink-0 rounded-xl border-2 border-slate-200 shadow-sm dark:border-slate-700" style={{ backgroundColor: form.color_hex }} />
                  <div className="flex flex-wrap gap-1.5">
                    {PRESET_COLORS.map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => setForm((p) => ({ ...p, color_hex: c }))}
                        className={`h-6 w-6 rounded-full transition ${form.color_hex === c ? "ring-2 ring-offset-2 ring-emerald-500 dark:ring-offset-slate-900" : ""}`}
                        style={{ backgroundColor: c }}
                      />
                    ))}
                  </div>
                </div>
              </label>
            </div>
            <div className="flex gap-3 pt-2">
              <button type="submit" className="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white hover:bg-emerald-500">
                Salvar Categoria
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="rounded-xl border border-slate-200 px-5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800">
                Cancelar
              </button>
            </div>
          </form>
        </Card>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {categories.length === 0 ? (
          <EmptyState className="col-span-full py-8">Nenhuma categoria cadastrada.</EmptyState>
        ) : (
          categories.map((cat) => (
            <Card key={cat.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CategoryDot color={cat.color_hex} />
                <span className="text-sm font-bold text-slate-900 dark:text-white">{cat.name}</span>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(cat.id)}
                className="rounded-lg px-2 py-1 text-xs font-semibold text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10"
              >
                Remover
              </button>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
        <header>
          <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">Parâmetros & Automações</p>
          <h1 className="mt-1 font-display text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Configurações</h1>
        </header>

        {/* Tab bar */}
        <div className="flex rounded-2xl border border-slate-200/80 bg-slate-100 p-1.5 shadow-inner dark:border-slate-800/80 dark:bg-slate-900/60">
          {TABS.map((tab, i) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(i)}
              className={`flex-1 rounded-xl px-4 py-2.5 font-display text-xs font-bold transition-all duration-200 ${
                activeTab === i
                  ? "bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white"
                  : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {activeTab === 0 && <RulesTab />}
        {activeTab === 1 && <CategoriesTab />}
        {activeTab === 2 && <NotificationsTab />}
      </div>
    </div>
  );
}
