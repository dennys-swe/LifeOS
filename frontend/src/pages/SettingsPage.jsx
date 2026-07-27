import { useEffect, useState } from "react";
import api from "../services/api";
import { useFinance } from "../context/FinanceContext";

const TABS = ["Regras", "Categorias", "Notificações"];

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
        setMsg("Permissão de notificação negada.");
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
      setMsg("Notificações ativadas.");
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
      <p className="text-sm text-gray-500 dark:text-slate-400">
        Este navegador não suporta notificações push.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-gray-500 dark:text-slate-400">
        Receba um aviso quando uma conta estiver vencendo em breve.
      </p>
      <div className="flex items-center justify-between rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div>
          <p className="font-medium text-gray-900 dark:text-slate-100">Notificações de contas vencendo</p>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            {subscribed ? "Ativadas neste dispositivo" : "Desativadas"}
          </p>
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={subscribed ? handleDisable : handleEnable}
          className={`rounded-xl px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${
            subscribed
              ? "border border-gray-200 text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              : "bg-emerald-600 text-white hover:bg-emerald-500"
          }`}
        >
          {loading ? "Aguarde..." : subscribed ? "Desativar" : "Ativar"}
        </button>
      </div>
      {msg && <p className="text-sm text-emerald-600 dark:text-emerald-400">{msg}</p>}
    </div>
  );
}

// ─── Category Rules ───────────────────────────────────────────────────────────

const RULE_INITIAL = { keyword: "", category_id: "", priority: 0 };

function RulesTab() {
  const { categories } = useFinance();
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState(RULE_INITIAL);
  const [showForm, setShowForm] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    const res = await api.get("/category-rules").catch(() => ({ data: [] }));
    setRules(res.data ?? []);
  };

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.category_id) { setMsg("Selecione uma categoria."); return; }
    await api.post("/category-rules", { ...form, priority: Number(form.priority) }).catch(() => null);
    setForm(RULE_INITIAL);
    setShowForm(false);
    setMsg("Regra criada.");
    load();
  };

  const handleDelete = async (id) => {
    await api.delete(`/category-rules/${id}`).catch(() => null);
    load();
  };

  const catMap = new Map(categories.map((c) => [c.id, c]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500 dark:text-slate-400">
          Palavras-chave que categorizam transações automaticamente na sincronização bancária.
        </p>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
        >
          + Nova regra
        </button>
      </div>

      {msg && <p className="text-sm text-emerald-600 dark:text-emerald-400">{msg}</p>}

      {showForm && (
        <form onSubmit={handleSubmit} className="grid gap-4 rounded-2xl border border-gray-200 bg-gray-50 p-5 dark:border-slate-700 dark:bg-slate-800/50 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700 dark:text-slate-300">
            Palavra-chave
            <input
              type="text"
              required
              value={form.keyword}
              placeholder="ex: SUPERMERCADO"
              onChange={(e) => setForm((p) => ({ ...p, keyword: e.target.value }))}
              className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm uppercase text-gray-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700 dark:text-slate-300">
            Categoria
            <select
              required
              value={form.category_id}
              onChange={(e) => setForm((p) => ({ ...p, category_id: e.target.value }))}
              className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="">Selecionar...</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700 dark:text-slate-300">
            Prioridade
            <input
              type="number"
              min="0"
              value={form.priority}
              onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}
              className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
          </label>
          <div className="flex gap-3 sm:col-span-3">
            <button type="submit" className="rounded-xl bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-500">
              Salvar
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="rounded-xl border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
              Cancelar
            </button>
          </div>
        </form>
      )}

      <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden dark:border-slate-800 dark:bg-slate-900">
        {rules.length === 0 ? (
          <p className="p-8 text-center text-sm text-gray-400 dark:text-slate-500">
            Nenhuma regra. Adicione palavras-chave para categorizar extratos automaticamente.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wider text-gray-400 dark:border-slate-800 dark:text-slate-500">
                <th className="px-5 py-3">Palavra-chave</th>
                <th className="px-5 py-3">Categoria</th>
                <th className="px-5 py-3">Prioridade</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-slate-800/60">
              {rules.map((rule) => {
                const cat = catMap.get(rule.category_id);
                return (
                  <tr key={rule.id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                    <td className="px-5 py-3 font-mono text-gray-900 dark:text-slate-100">{rule.keyword}</td>
                    <td className="px-5 py-3">
                      {cat ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: cat.color_hex }} />
                          <span className="text-gray-700 dark:text-slate-300">{cat.name}</span>
                        </span>
                      ) : <span className="text-gray-400 dark:text-slate-500">—</span>}
                    </td>
                    <td className="px-5 py-3 text-gray-500 dark:text-slate-400">{rule.priority}</td>
                    <td className="px-5 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleDelete(rule.id)}
                        className="rounded-lg px-3 py-1 text-xs text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20"
                      >
                        Excluir
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
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
    setMsg("Categoria criada.");
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
        <p className="text-sm text-gray-500 dark:text-slate-400">
          Categorias usadas para classificar contas e transações.
        </p>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
        >
          + Nova categoria
        </button>
      </div>

      {msg && <p className="text-sm text-emerald-600 dark:text-emerald-400">{msg}</p>}

      {showForm && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-2xl border border-gray-200 bg-gray-50 p-5 dark:border-slate-700 dark:bg-slate-800/50">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700 dark:text-slate-300">
              Nome
              <input
                type="text"
                required
                value={form.name}
                placeholder="ex: Mercado"
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700 dark:text-slate-300">
              Cor
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 flex-shrink-0 rounded-lg border-2 border-gray-200 dark:border-slate-600" style={{ backgroundColor: form.color_hex }} />
                <div className="flex flex-wrap gap-1.5">
                  {PRESET_COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setForm((p) => ({ ...p, color_hex: c }))}
                      className={`h-6 w-6 rounded-full transition ${form.color_hex === c ? "ring-2 ring-offset-2 ring-gray-400 dark:ring-offset-slate-800" : ""}`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>
            </label>
          </div>
          <div className="flex gap-3">
            <button type="submit" className="rounded-xl bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-500">
              Salvar
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="rounded-xl border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
              Cancelar
            </button>
          </div>
        </form>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {categories.length === 0 ? (
          <p className="col-span-full text-center text-sm text-gray-400 dark:text-slate-500">Nenhuma categoria cadastrada.</p>
        ) : (
          categories.map((cat) => (
            <div key={cat.id} className="flex items-center justify-between rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center gap-3">
                <span className="h-8 w-8 flex-shrink-0 rounded-lg" style={{ backgroundColor: cat.color_hex }} />
                <span className="font-medium text-gray-800 dark:text-slate-200">{cat.name}</span>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(cat.id)}
                className="rounded-lg px-2 py-1 text-xs text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20"
              >
                Remover
              </button>
            </div>
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
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-8">
        <header>
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 dark:text-slate-500">Automação</p>
          <h1 className="mt-1 text-2xl font-semibold text-gray-900 dark:text-slate-100">Configurações</h1>
        </header>

        {/* Tab bar */}
        <div className="flex gap-1 rounded-xl border border-gray-200 bg-white p-1 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          {TABS.map((tab, i) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(i)}
              className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === i
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-gray-500 hover:text-gray-800 dark:text-slate-400 dark:hover:text-slate-200"
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
