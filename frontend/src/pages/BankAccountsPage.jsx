import { useCallback, useEffect, useRef, useState } from "react";
import api from "../services/api";

const PLUGGY_CONNECT_CDN = "https://cdn.pluggy.ai/pluggy-connect/latest/pluggy-connect.js";

function loadPluggyScript() {
  return new Promise((resolve, reject) => {
    if (window.PluggyConnect) { resolve(); return; }
    const script = document.createElement("script");
    script.src = PLUGGY_CONNECT_CDN;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

export default function BankAccountsPage() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState(null);
  const pluggyRef = useRef(null);

  const fetchAccounts = useCallback(async () => {
    try {
      const { data } = await api.get("/bank-accounts");
      setAccounts(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAccounts(); }, [fetchAccounts]);

  async function handleConnect() {
    setConnecting(true);
    setMessage(null);
    try {
      await loadPluggyScript();
      const { data } = await api.post("/bank-accounts/connect-token");

      pluggyRef.current = new window.PluggyConnect({
        connectToken: data.access_token,
        onSuccess: async ({ item }) => {
          try {
            await api.post("/bank-accounts", {
              name: item.connector?.name ?? "Conta bancária",
              bank_name: item.connector?.name ?? "Desconhecido",
              account_type: "checking",
              external_id: item.id,
            });
            setMessage({ type: "ok", text: "Banco conectado! Clique em Sincronizar para importar transações." });
            fetchAccounts();
          } catch {
            setMessage({ type: "err", text: "Banco conectado, mas falha ao salvar. Tente novamente." });
          }
        },
        onError: (err) => {
          setMessage({ type: "err", text: `Erro ao conectar: ${err?.message ?? "desconhecido"}` });
        },
        onClose: () => setConnecting(false),
      });
      pluggyRef.current.init();
    } catch {
      setMessage({ type: "err", text: "Não foi possível carregar o widget da Pluggy." });
      setConnecting(false);
    }
  }

  async function handleSync(account) {
    setSyncing(account.id);
    setMessage(null);
    try {
      const { data } = await api.post(`/bank-accounts/${account.id}/sync`);
      setMessage({ type: "ok", text: `Sincronizado: ${data.imported} transações importadas, ${data.skipped} já existiam.` });
      fetchAccounts();
    } catch (err) {
      const detail = err.response?.data?.detail ?? "Erro ao sincronizar.";
      setMessage({ type: "err", text: detail });
    } finally {
      setSyncing(null);
    }
  }

  async function handleDelete(account) {
    if (!confirm(`Remover "${account.name}"?`)) return;
    await api.delete(`/bank-accounts/${account.id}`);
    fetchAccounts();
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
        <header className="flex items-end justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Open Finance</p>
            <h1 className="text-3xl font-semibold text-white">Contas Bancárias</h1>
          </div>
          <button
            type="button"
            onClick={handleConnect}
            disabled={connecting}
            className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:opacity-50"
          >
            {connecting ? "Aguardando..." : "+ Conectar banco"}
          </button>
        </header>

        {message && (
          <div className={`rounded-xl px-4 py-3 text-sm ${message.type === "ok" ? "bg-emerald-900/40 text-emerald-300" : "bg-rose-900/40 text-rose-300"}`}>
            {message.text}
          </div>
        )}

        {loading ? (
          <p className="text-slate-400">Carregando...</p>
        ) : accounts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center">
            <p className="text-slate-400">Nenhuma conta conectada.</p>
            <p className="mt-1 text-sm text-slate-600">Clique em "+ Conectar banco" para começar.</p>
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {accounts.map((acct) => (
              <li
                key={acct.id}
                className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900 px-5 py-4"
              >
                <div>
                  <p className="font-medium text-white">{acct.name}</p>
                  <p className="text-sm text-slate-400">{acct.bank_name}</p>
                  {acct.last_sync_at && (
                    <p className="mt-1 text-xs text-slate-600">
                      Última sync: {new Date(acct.last_sync_at).toLocaleString("pt-BR")}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleSync(acct)}
                    disabled={syncing === acct.id || !acct.external_id}
                    className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-slate-600 disabled:opacity-40"
                    title={!acct.external_id ? "Conecte o banco primeiro" : "Importar transações"}
                  >
                    {syncing === acct.id ? "Sincronizando..." : "Sincronizar"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(acct)}
                    className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-rose-400 transition hover:bg-rose-900/30"
                  >
                    Remover
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
