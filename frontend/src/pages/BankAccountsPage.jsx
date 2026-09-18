import { useCallback, useEffect, useRef, useState } from "react";
import api from "../services/api";
import ConfirmModal from "../components/ConfirmModal";
import Card, { CardHeader } from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { fmt } from "../lib/format";
import { useFinance } from "../context/FinanceContext";
import { useMountedRef } from "../hooks/useMountedRef";
import { useRevalidateOnFocus } from "../hooks/useRevalidateOnFocus";
import { STALE_TTL_MS } from "../lib/staleness";

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
  const { refresh } = useFinance();
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
  const [cardsByAccount, setCardsByAccount] = useState({});
  const [togglingCard, setTogglingCard] = useState(null);
  const pluggyRef = useRef(null);
  const lastLoadedAtRef = useRef(0);
  const mountedRef = useMountedRef();
  // Nº sequencial da chamada a `load()` mais recente — uma revalidação
  // automática lenta (ex: disparada no foco da aba) que termine DEPOIS de
  // um load() manual mais novo (ex: pós-"Sincronizar") não pode sobrescrever
  // a tela com o dado pré-mutação, mais velho. Mesmo cuidado do
  // `activeKeyRef` do FinanceContext, adaptado pra um fetch sem chave.
  // Checado em dois pontos (depois de accounts+suggestions, depois de
  // cards) pra manter a renderização incremental: a lista de contas
  // continua aparecendo assim que chega, sem esperar os cartões de todas.
  const requestSeqRef = useRef(0);
  // Quantas chamadas NÃO-silenciosas estão em andamento agora — o spinner só
  // desliga quando a ÚLTIMA delas termina, não a primeira (duas ações
  // manuais quase simultâneas, ex: "Sincronizar" seguido de "Atualizar
  // Conexões", não podem desligar o spinner uma da outra enquanto a mais
  // nova ainda está buscando). Não conta chamadas silenciosas de propósito
  // — elas nunca ligam nem desligam esse spinner.
  const pendingNonSilentRef = useRef(0);

  // Identidade estável (refs/setState são estáveis, sem props/state no
  // corpo) — pode entrar em array de dependência de outro hook sem recriar
  // esse hook a cada render.
  const load = useCallback(async ({ silent = false } = {}) => {
    const seq = ++requestSeqRef.current;
    if (!silent) {
      pendingNonSilentRef.current += 1;
      setLoading(true);
    }
    try {
      const [accRes, sugRes] = await Promise.all([
        api.get("/bank-accounts").catch(() => ({ data: [] })),
        api.get("/bank-accounts/reconciliation-suggestions").catch(() => ({ data: [] })),
      ]);
      if (!mountedRef.current || seq !== requestSeqRef.current) return;

      const accs = accRes.data ?? [];
      setAccounts(accs);
      setSuggestions(sugRes.data ?? []);

      // `account_type` da conexão é sempre "checking" (a Pluggy Connect não
      // diferencia no momento de conectar — quem detecta cartão é o sync,
      // por pluggy_account, não a conexão como um todo). Por isso busca pra
      // TODAS as contas em vez de filtrar por account_type: o endpoint só
      // devolve algo pras que já sincronizaram algum CreditCardBill, então é
      // barato e inofensivo pras que não têm cartão nenhum.
      const cardResults = await Promise.all(
        accs.map((a) => api.get(`/bank-accounts/${a.id}/cards`).catch(() => ({ data: [] })))
      );

      if (!mountedRef.current || seq !== requestSeqRef.current) return;

      const next = {};
      accs.forEach((a, i) => { next[a.id] = cardResults[i].data ?? []; });
      setCardsByAccount(next);
      lastLoadedAtRef.current = Date.now();
    } finally {
      if (!silent) {
        pendingNonSilentRef.current -= 1;
        if (mountedRef.current && pendingNonSilentRef.current === 0) setLoading(false);
      }
    }
  }, [mountedRef]);

  useEffect(() => { load(); }, [load]);

  // Revalida em segundo plano ao voltar pra aba (mesmo padrão do
  // FinanceContext, issue #110) — cobre "deixei esta tela aberta e o
  // cron/webhook mudou algo" sem esperar um clique manual. `silent: true`
  // busca por baixo dos panos sem animar/desabilitar o botão "Atualizar
  // Conexões" (a lista já carregada continua na tela normalmente). O dedup
  // de visibilitychange+focus disparando juntos mora no hook — não bloqueia
  // `load()` em si, que outras ações (sync, conectar, editar, etc.)
  // continuam podendo chamar livremente mesmo com uma revalidação em
  // andamento.
  useRevalidateOnFocus(
    useCallback(async () => {
      if (Date.now() - lastLoadedAtRef.current > STALE_TTL_MS) {
        await load({ silent: true });
      }
    }, [load])
  );

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
      refresh();
    } catch {
      setMsg("Erro ao confirmar conciliação.");
    } finally {
      setConfirmMatch(null);
    }
  };

  const handleToggleCard = async (accountId, card) => {
    const key = `${accountId}:${card.pluggy_account_id}`;
    setTogglingCard(key);
    try {
      if (card.ignored) {
        await api.delete(`/bank-accounts/${accountId}/cards/${card.pluggy_account_id}/ignore`);
        setMsg(`"${card.label}" voltará a ser sincronizado.`);
      } else {
        await api.post(`/bank-accounts/${accountId}/cards/${card.pluggy_account_id}/ignore`);
        setMsg(`"${card.label}" ignorado — nenhuma cobrança nova será gerada.`);
      }
      await load();
      refresh();
    } catch {
      setMsg("Erro ao atualizar o cartão.");
    } finally {
      setTogglingCard(null);
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
              const cards = cardsByAccount[acc.id] ?? [];

              return (
                <Card key={acc.id} className="p-5 flex flex-col gap-4">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
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
                </div>

                {cards.length > 0 && (
                  <div className="flex flex-col gap-2 border-t border-slate-100 pt-3 dark:border-slate-800/40">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                      Cartões desta conexão
                    </p>
                    {cards.map((card) => {
                      const key = `${acc.id}:${card.pluggy_account_id}`;
                      const isToggling = togglingCard === key;
                      return (
                        <div
                          key={card.pluggy_account_id}
                          className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2 dark:bg-slate-800/40"
                        >
                          <span className={`text-xs font-semibold ${card.ignored ? "text-slate-400 line-through dark:text-slate-600" : "text-slate-700 dark:text-slate-200"}`}>
                            {card.label}
                            {card.ignored && (
                              <span className="ml-2 rounded-full border border-slate-300 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:border-slate-700 dark:text-slate-500">
                                Ignorado
                              </span>
                            )}
                          </span>
                          <button
                            type="button"
                            disabled={isToggling}
                            onClick={() => handleToggleCard(acc.id, card)}
                            title={card.ignored ? "Voltar a sincronizar este cartão" : "Parar de gerar fatura/cobrança deste cartão"}
                            className={`rounded-lg px-3 py-1 text-[11px] font-bold transition disabled:opacity-50 ${
                              card.ignored
                                ? "border border-emerald-500/40 text-emerald-600 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
                                : "border border-rose-300/60 text-rose-500 hover:bg-rose-50 dark:border-rose-500/30 dark:hover:bg-rose-900/20"
                            }`}
                          >
                            {isToggling ? "..." : card.ignored ? "Reativar" : "Ignorar"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
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
