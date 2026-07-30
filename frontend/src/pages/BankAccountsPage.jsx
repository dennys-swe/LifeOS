import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api from "../services/api";
import { useFinance } from "../context/FinanceContext";
import { fmt } from "../lib/format";

function confidenceColor(score) {
  if (score >= 0.9) return "bg-emerald-500";
  if (score >= 0.7) return "bg-amber-400";
  return "bg-rose-500";
}

function groupSuggestionsByPayable(suggestions) {
  const groups = new Map();
  for (const s of suggestions) {
    if (!groups.has(s.payable_id)) {
      groups.set(s.payable_id, {
        payable_id: s.payable_id,
        payable_title: s.payable_title,
        payable_amount: s.payable_amount,
        candidates: [],
      });
    }
    groups.get(s.payable_id).candidates.push(s);
  }
  return Array.from(groups.values()).sort((a, b) => b.payable_title.localeCompare(a.payable_title));
}

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
  const { refresh } = useFinance() ?? {};
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [confirming, setConfirming] = useState(new Set());
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const pluggyRef = useRef(null);
  const prevStatusRef = useRef({});

  const suggestionGroups = useMemo(() => groupSuggestionsByPayable(suggestions), [suggestions]);

  const fetchAccounts = useCallback(async () => {
    try {
      const { data } = await api.get("/bank-accounts");
      setAccounts(data);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSuggestions = useCallback(async () => {
    try {
      const { data } = await api.get("/bank-accounts/reconciliation-suggestions");
      setSuggestions(data);
    } catch {
      setSuggestions([]);
    }
  }, []);

  useEffect(() => { fetchAccounts(); fetchSuggestions(); }, [fetchAccounts, fetchSuggestions]);

  // Enquanto alguma conta estiver com sync_status "SYNCING" (rodando em
  // background no servidor), fica de olho a cada poucos segundos até terminar.
  useEffect(() => {
    const anySyncing = accounts.some((a) => a.sync_status === "SYNCING");
    if (!anySyncing) return undefined;
    const interval = setInterval(fetchAccounts, 2500);
    return () => clearInterval(interval);
  }, [accounts, fetchAccounts]);

  // Detecta quando uma conta terminou de sincronizar (transição SYNCING -> outro status)
  // pra avisar o usuário e atualizar sugestões/contas.
  useEffect(() => {
    accounts.forEach((acct) => {
      const previous = prevStatusRef.current[acct.id];
      if (previous === "SYNCING" && acct.sync_status !== "SYNCING") {
        if (acct.sync_status === "ERROR") {
          setMessage({ type: "err", text: acct.last_sync_error ?? "Erro ao sincronizar." });
        } else {
          setMessage({ type: "ok", text: "Sincronização concluída." });
        }
        fetchSuggestions();
        refresh?.();
      }
    });
    prevStatusRef.current = Object.fromEntries(accounts.map((a) => [a.id, a.sync_status]));
  }, [accounts, fetchSuggestions, refresh]);

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
            // Sem nome: o backend deriva das accounts da Pluggy. Com o conector
            // MeuPluggy, item.connector.name é sempre "MeuPluggy" — usá-lo aqui
            // deixaria todos os bancos conectados com o mesmo rótulo.
            await api.post("/bank-accounts", {
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
    setMessage(null);
    try {
      const { data } = await api.post(`/bank-accounts/${account.id}/sync`);
      setAccounts((prev) =>
        prev.map((a) => (a.id === account.id ? { ...a, sync_status: data.sync_status } : a))
      );
      setMessage({ type: "ok", text: "Sincronizando em segundo plano — pode continuar navegando." });
    } catch (err) {
      const detail = err.response?.data?.detail ?? "Erro ao sincronizar.";
      setMessage({ type: "err", text: detail });
    }
  }

  async function handleDelete(account) {
    if (!confirm(`Remover "${account.name}"?`)) return;
    await api.delete(`/bank-accounts/${account.id}`);
    fetchAccounts();
  }

  function startRename(account) {
    setRenamingId(account.id);
    setRenameValue(account.name);
  }

  async function handleRename(account) {
    const name = renameValue.trim();
    setRenamingId(null);
    if (!name || name === account.name) return;

    setAccounts((prev) => prev.map((a) => (a.id === account.id ? { ...a, name } : a)));
    try {
      await api.patch(`/bank-accounts/${account.id}`, { name });
    } catch {
      setMessage({ type: "err", text: "Não foi possível renomear a conta." });
      fetchAccounts();
    }
  }

  async function handleConfirmSuggestion(suggestion) {
    setConfirming((prev) => new Set([...prev, suggestion.payable_id]));
    try {
      await api.patch(`/payables/${suggestion.payable_id}/reconcile?transaction_id=${suggestion.transaction_id}`);
      setSuggestions((prev) => prev.filter((s) => s.payable_id !== suggestion.payable_id));
      refresh?.();
    } catch {
      setMessage({ type: "err", text: "Erro ao conciliar. Tente novamente." });
    } finally {
      setConfirming((prev) => { const n = new Set(prev); n.delete(suggestion.payable_id); return n; });
    }
  }

  function handleIgnoreSuggestion(suggestion) {
    setSuggestions((prev) =>
      prev.filter((s) => !(s.payable_id === suggestion.payable_id && s.transaction_id === suggestion.transaction_id))
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 dark:text-slate-500">Open Finance</p>
            <h1 className="mt-1 text-2xl font-semibold text-gray-900 dark:text-slate-100">Contas Bancárias</h1>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleConnect}
              disabled={connecting}
              className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:opacity-50"
            >
              {connecting ? "Aguardando..." : "+ Conectar banco"}
            </button>
          </div>
        </header>

        {message && (
          <div className={`rounded-xl px-4 py-3 text-sm ${message.type === "ok" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300" : "bg-rose-50 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300"}`}>
            {message.text}
          </div>
        )}

        {suggestionGroups.length > 0 && (
          <section className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50/60 p-4 dark:border-amber-900/40 dark:bg-amber-900/10">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100">
              Confirmações pendentes ({suggestionGroups.length})
            </h2>
            <p className="text-xs text-gray-500 dark:text-slate-400">
              Achamos que essas transações importadas podem ser o pagamento de uma conta. Quando uma conta tem mais de um
              candidato, confirme só o certo — os outros somem sozinhos.
            </p>
            <ul className="flex flex-col gap-3">
              {suggestionGroups.map((group) => (
                <li
                  key={group.payable_id}
                  className="rounded-xl border border-gray-200 bg-white dark:border-slate-800 dark:bg-slate-900"
                >
                  <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-4 py-2.5 dark:border-slate-800">
                    <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{group.payable_title}</p>
                    <p className="text-xs text-gray-500 dark:text-slate-400">{fmt(group.payable_amount)}</p>
                  </div>
                  <ul className="flex flex-col divide-y divide-gray-100 dark:divide-slate-800">
                    {group.candidates.map((s) => (
                      <li
                        key={`${s.payable_id}-${s.transaction_id}`}
                        className="flex items-center justify-between gap-3 px-4 py-2.5"
                      >
                        <div className="flex items-center gap-3">
                          <span className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${confidenceColor(s.confidence_score)}`} />
                          <p className="text-xs text-gray-500 dark:text-slate-400">
                            {s.transaction_description} · {fmt(s.transaction_amount)}
                          </p>
                        </div>
                        <div className="flex flex-shrink-0 gap-2">
                          <button
                            type="button"
                            onClick={() => handleConfirmSuggestion(s)}
                            disabled={confirming.has(s.payable_id)}
                            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-emerald-500 disabled:opacity-50"
                          >
                            Confirmar
                          </button>
                          <button
                            type="button"
                            onClick={() => handleIgnoreSuggestion(s)}
                            className="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-500 transition hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-800"
                          >
                            Ignorar
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </section>
        )}

        {loading ? (
          <p className="text-gray-400 dark:text-slate-400">Carregando...</p>
        ) : accounts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-gray-200 p-12 text-center dark:border-slate-700">
            <p className="text-gray-500 dark:text-slate-400">Nenhuma conta conectada.</p>
            <p className="mt-1 text-sm text-gray-400 dark:text-slate-600">Clique em "+ Conectar banco" para começar.</p>
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {accounts.map((acct) => (
              <li
                key={acct.id}
                className="flex items-center justify-between rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="min-w-0 flex-1">
                  {renamingId === acct.id ? (
                    <input
                      autoFocus
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={() => handleRename(acct)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRename(acct);
                        if (e.key === "Escape") setRenamingId(null);
                      }}
                      maxLength={100}
                      className="w-full rounded-lg border border-gray-300 px-2 py-1 font-medium text-gray-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => startRename(acct)}
                      title={`${acct.name} — clique para renomear`}
                      className="block max-w-full truncate text-left font-medium text-gray-900 hover:underline dark:text-slate-100"
                    >
                      {acct.name}
                    </button>
                  )}
                  <p className="truncate text-sm text-gray-500 dark:text-slate-400">{acct.bank_name}</p>
                  {acct.last_sync_at && (
                    <p className="mt-1 text-xs text-gray-400 dark:text-slate-600">
                      Última sync: {new Date(acct.last_sync_at).toLocaleString("pt-BR")}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleSync(acct)}
                    disabled={acct.sync_status === "SYNCING" || !acct.external_id}
                    className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-100 disabled:opacity-40 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                    title={!acct.external_id ? "Conecte o banco primeiro" : "Importar transações"}
                  >
                    {acct.sync_status === "SYNCING" ? "Sincronizando..." : "Sincronizar"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(acct)}
                    className="rounded-lg px-3 py-1.5 text-xs font-medium text-rose-500 transition hover:bg-rose-50 dark:hover:bg-rose-900/20"
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
