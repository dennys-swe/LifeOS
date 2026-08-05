import { useEffect, useRef, useState } from "react";
import api from "../services/api";
import ConfirmModal from "../components/ConfirmModal";
import Card, { CardHeader } from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { fmt } from "../lib/format";

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

function IconBank({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0 0 12 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75Z" />
    </svg>
  );
}

function IconRefresh({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
    </svg>
  );
}

export default function BankAccountsPage() {
  const [accounts, setAccounts] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState("");
  const [loading, setLoading] = useState(false);
  const [syncingId, setSyncingId] = useState(null);
  const [confirmMatch, setConfirmMatch] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [msg, setMsg] = useState("");
  const pluggyRef = useRef(null);

  const load = async () => {
    setLoading(true);
    try {
      const [accRes, sugRes] = await Promise.all([
        api.get("/bank-accounts").catch(() => ({ data: [] })),
        api.get("/bank-accounts/reconciliation-suggestions").catch(() => ({ data: [] })),
      ]);
      setAccounts(accRes.data ?? []);
      setSuggestions(sugRes.data ?? []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleConnect = async () => {
    setConnecting(true);
    setMsg("");
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
            setMsg("Banco conectado! Clique em Sincronizar para importar transações.");
            await load();
          } catch {
            setMsg("Banco conectado, mas falha ao salvar. Tente novamente.");
          }
        },
        onError: (err) => {
          setMsg(`Erro ao conectar: ${err?.message ?? "desconhecido"}`);
        },
        onClose: () => setConnecting(false),
      });
      pluggyRef.current.init();
    } catch {
      setMsg("Não foi possível carregar o widget da Pluggy.");
      setConnecting(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!confirmDelete) return;
    try {
      await api.delete(`/bank-accounts/${confirmDelete.id}`);
      setMsg("Conta removida.");
      await load();
    } catch {
      setMsg("Erro ao remover conta.");
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleSyncAccount = async (id) => {
    setSyncingId(id);
    setMsg("");
    try {
      await api.post(`/bank-accounts/${id}/sync`);
      setMsg("Sincronização iniciada.");
      await load();
    } catch {
      setMsg("Erro ao sincronizar.");
    } finally {
      setSyncingId(null);
    }
  };

  const handleSaveName = async (acc) => {
    if (!editingName.trim()) { setEditingId(null); return; }
    try {
      await api.patch(`/bank-accounts/${acc.id}`, { name: editingName.trim() });
      await load();
    } catch {
      setMsg("Erro ao atualizar nome.");
    } finally {
      setEditingId(null);
    }
  };

  const handleConfirmMatchAction = async () => {
    if (!confirmMatch) return;
    try {
      await api.patch(
        `/payables/${confirmMatch.payable_id}/reconcile`,
        null,
        { params: { transaction_id: confirmMatch.transaction_id } }
      );
      setMsg("Conciliação confirmada!");
      await load();
    } catch {
      setMsg("Erro ao confirmar conciliação.");
    } finally {
      setConfirmMatch(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <ConfirmModal
        open={confirmMatch !== null}
        title="Confirmar conciliação automatizada?"
        description="A transação bancária será vinculada e marcará a obrigação como PAGA."
        confirmLabel="Confirmar Conciliação"
        variant="success"
        onCancel={() => setConfirmMatch(null)}
        onConfirm={handleConfirmMatchAction}
      />

      <ConfirmModal
        open={confirmDelete !== null}
        title={`Remover "${confirmDelete?.name}"?`}
        description="A conta e suas faturas/transações vinculadas deixarão de ser sincronizadas."
        confirmLabel="Remover"
        variant="danger"
        onCancel={() => setConfirmDelete(null)}
        onConfirm={handleDeleteAccount}
      />

      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
        {/* Header */}
        <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">Open Finance Integrations</p>
            <h1 className="mt-1 font-display text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Contas Bancárias</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              <IconRefresh className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Atualizar Conexões
            </button>
            <button
              type="button"
              onClick={handleConnect}
              disabled={connecting}
              className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-500 disabled:opacity-50"
            >
              {connecting ? "Aguardando..." : "+ Conectar banco"}
            </button>
          </div>
        </header>

        {msg && <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400">{msg}</p>}

        {/* Bank Connection Cards */}
        <div className="flex flex-col gap-4">
          {accounts.length === 0 ? (
            <EmptyState className="h-auto py-12">Nenhuma conta bancária vinculada via Pluggy.</EmptyState>
          ) : (
            accounts.map((acc) => {
              const isSyncing = syncingId === acc.id;
              const isEditing = editingId === acc.id;

              return (
                <Card key={acc.id} className="p-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div className="flex items-center gap-4 min-w-0 flex-1">
                    <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400">
                      <IconBank className="h-6 w-6" />
                    </div>

                    <div className="min-w-0 flex-1">
                      {isEditing ? (
                        <input
                          autoFocus
                          value={editingName}
                          onChange={(e) => setEditingName(e.target.value)}
                          onBlur={() => handleSaveName(acc)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleSaveName(acc);
                            if (e.key === "Escape") setEditingId(null);
                          }}
                          className="w-full max-w-sm rounded-xl border border-emerald-500 bg-white px-3 py-1 text-sm font-bold text-slate-900 dark:bg-slate-800 dark:text-white"
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => { setEditingId(acc.id); setEditingName(acc.name); }}
                          title="Clique para renomear a conta"
                          className="text-left text-base font-bold text-slate-900 hover:text-emerald-600 dark:text-white dark:hover:text-emerald-400"
                        >
                          {acc.name}
                        </button>
                      )}
                      <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                        {acc.type === "CREDIT" ? "Cartão de Crédito" : "Conta Corrente/Poupança"}
                        {acc.number && ` · final ${acc.number}`}
                        {acc.last_sync_at && ` · Sincronizado ${new Date(acc.last_sync_at).toLocaleString("pt-BR")}`}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between md:justify-end gap-4 border-t border-slate-100 dark:border-slate-800/40 pt-3 md:pt-0 md:border-t-0">
                    <span className="font-display text-lg font-extrabold text-slate-900 dark:text-white">
                      {fmt(Number(acc.balance) || 0)}
                    </span>
                    <button
                      type="button"
                      disabled={isSyncing}
                      onClick={() => handleSyncAccount(acc.id)}
                      className="rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-bold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {isSyncing ? "Sincronizando..." : "Sincronizar"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(acc)}
                      title="Remover conta"
                      className="rounded-xl px-3 py-1.5 text-xs font-bold text-rose-500 transition hover:bg-rose-50 dark:hover:bg-rose-900/20"
                    >
                      Remover
                    </button>
                  </div>
                </Card>
              );
            })
          )}
        </div>

        {/* Reconciliation Suggestions */}
        {suggestions.length > 0 && (
          <Card className="p-6">
            <CardHeader
              title="Sugestões de Conciliação Automática"
              subtitle="Transações no extrato que correspondem a contas pendentes"
            />
            <div className="flex flex-col gap-3">
              {suggestions.map((sug) => {
                const confidence = Math.round((sug.confidence_score ?? 0) * 100);
                const isHigh = confidence >= 85;

                return (
                  <div
                    key={`${sug.payable_id}-${sug.transaction_id}`}
                    className="flex flex-col gap-3 rounded-2xl border border-slate-200/60 bg-slate-50/50 p-4 transition-all hover:bg-slate-100/50 dark:border-slate-800/60 dark:bg-slate-900/40 dark:hover:bg-slate-800/40 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-900 dark:text-white">{sug.payable_title}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          isHigh
                            ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
                        }`}>
                          {confidence}% Confiança
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                        Correspondente à transação:{" "}
                        <strong className="text-slate-700 dark:text-slate-300">{sug.transaction_description}</strong>{" "}
                        de {fmt(Number(sug.transaction_amount))}
                      </p>
                    </div>

                    <div className="flex items-center justify-between md:justify-end gap-3">
                      <span className="font-display text-sm font-bold text-emerald-600 dark:text-emerald-400">
                        {fmt(Number(sug.payable_amount))}
                      </span>
                      <button
                        type="button"
                        onClick={() => setConfirmMatch(sug)}
                        className="rounded-xl bg-emerald-600 px-4 py-1.5 text-xs font-bold text-white transition hover:bg-emerald-500"
                      >
                        Vincular & Baixar
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

      </div>
    </div>
  );
}
