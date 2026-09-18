import { useCallback, useEffect, useRef, useState } from "react";
import api from "../services/api";
import { useFinance } from "../context/FinanceContext";

// Issue #114: sincroniza contas bancárias sozinho ao abrir o app (contas
// "velhas", sem bloquear o render) e expõe `triggerSync(true)` pro botão
// "Sincronizar tudo" (issue futura) reaproveitar o mesmo mecanismo de
// polling + refresh.
const POLL_INTERVAL_MS = 5000;
// Teto de tentativas — sem isso, uma conta presa em SYNCING (ex: processo do
// Render reciclado no meio do job) faria esta aba pollar pra sempre, com o
// selo "Atualizando…" travado e tráfego de API sem fim. `STALE_SYNC_LOCK` no
// backend (15min) já trata esse lock como morto bem antes deste teto, então
// desistir aqui só evita o polling ocioso — a próxima sync (staleness ao
// reabrir, foco na aba, clique manual) tenta de novo.
const MAX_POLL_ATTEMPTS = 24; // ~2min a 5s por tentativa

export function useBankSync({ syncOnMount = false } = {}) {
  const { refresh } = useFinance();
  const [syncing, setSyncing] = useState(false);
  const pollRef = useRef(null);
  const wasSyncingRef = useRef(false);
  const pollAttemptsRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const checkStatus = useCallback(async () => {
    try {
      const { data } = await api.get("/bank-accounts");
      const anySyncing = (data ?? []).some((a) => a.sync_status === "SYNCING");

      if (anySyncing) {
        pollAttemptsRef.current += 1;
        if (pollAttemptsRef.current < MAX_POLL_ATTEMPTS) {
          setSyncing(true);
          wasSyncingRef.current = true;
          return;
        }
        // desistiu — ver comentário de MAX_POLL_ATTEMPTS acima.
      }

      setSyncing(false);
      stopPolling();
      // refresh() só se realmente havia algo sincronizando antes — senão
      // toda checagem inicial (mesmo sem nada em andamento) invalidaria o
      // cache do FinanceContext à toa. Ao desistir por teto, o estado real
      // ainda é incerto — não vale a pena refetch, a próxima sync que
      // terminar de verdade chama refresh() normalmente.
      if (wasSyncingRef.current && !anySyncing) refresh();
      wasSyncingRef.current = false;
    } catch {
      // se falhar, só desiste desta rodada — o próximo poll tenta de novo
    }
  }, [refresh, stopPolling]);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollAttemptsRef.current = 0;
    pollRef.current = setInterval(checkStatus, POLL_INTERVAL_MS);
  }, [checkStatus]);

  const triggerSync = useCallback(
    async (force = false) => {
      try {
        const { data } = await api.post("/bank-accounts/sync-all", null, { params: { force } });
        if ((data?.triggered ?? []).length > 0) {
          wasSyncingRef.current = true;
          setSyncing(true);
          startPolling();
        }
      } catch {
        // sync automático é best-effort — falhar aqui não pode quebrar o app
      }
    },
    [startPolling]
  );

  useEffect(() => {
    // `triggerSync` só faz setState depois do `await api.post(...)` (nunca
    // de forma síncrona dentro do corpo do efeito) — o lint não enxerga
    // através do await e trata qualquer chamada a uma função que
    // eventualmente muda estado como se fosse síncrona.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (syncOnMount) triggerSync(false);
    return () => stopPolling();
  }, [syncOnMount, triggerSync, stopPolling]);

  return { syncing, triggerSync };
}
