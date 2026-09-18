import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { loadFinanceCache, saveFinanceCache } from "../lib/financeCache";
import api from "../services/api";

const FinanceContext = createContext(null);

// Cache por "mês-ano" nesta sessão do navegador (issue #66). Sem isso, trocar
// de aba (Dashboard -> Extrato -> Dashboard) não desmontava o FinanceProvider
// (já está acima do Outlet em ProtectedLayout), mas voltar pra um mês/ano já
// buscado ainda refazia as 3 chamadas — causa real: `refresh` não era
// memoizado, então toda vez que o provider re-renderizava (ex: ao terminar
// um fetch) ele virava uma função nova, e efeitos em outras páginas que têm
// `refresh` como dependência (DashboardPage, PayablesPage) disparavam de
// novo — o de PayablesPage inclusive CHAMA refresh() dentro do próprio
// efeito, criando um loop de refetch a cada vez que a aba era aberta.
// sessionStorage sobrevive a um F5 (só nesta aba), então o reload também
// aproveita o último dado bom em vez de mostrar tela zerada. Limpo no
// logout em services/api.js (clearToken) — ver lib/financeCache.js.

// Cache sem expiração nunca pega mudança feita por fora desta aba (sync
// automático do cron, webhook da Pluggy, conciliação feita em outra aba) —
// só `refresh()` explícito depois de uma mutação local invalidava, então uma
// aba deixada aberta ficava com dado velho indefinidamente (só saía do ar no
// logout). `STALE_TTL_MS` marca a partir de quando um dado cacheado é velho
// o bastante pra merecer revalidação silenciosa (mostra o cache na hora,
// sem tela de loading, e busca por baixo dos panos) — ao focar a aba de
// novo ou trocar de mês/ano. Uma entrada de cache de antes desta mudança não
// tem `fetchedAt` (`?? 0` cai no epoch), então já nasce "velha" e se
// autocorrige no primeiro foco/troca de mês após o deploy, sem precisar de
// migração de formato.
const STALE_TTL_MS = 3 * 60 * 1000;

export function FinanceProvider({ children, month, year }) {
  const cacheRef = useRef(null);
  if (cacheRef.current === null) {
    cacheRef.current = loadFinanceCache();
  }
  const lastRefreshKeyRef = useRef(0);
  const mountedRef = useRef(true);
  // Chave do mês/ano exibido agora — checado no retorno de um fetch antes de
  // aplicar setState, senão uma resposta lenta de um mês antigo (ex: a
  // revalidação silenciosa de foco de aba) pode chegar depois do usuário já
  // ter trocado de mês e sobrescrever a tela com dado do mês errado.
  const activeKeyRef = useRef(`${month}-${year}`);
  // Evita revalidação duplicada quando `visibilitychange` e `focus` disparam
  // juntos ao voltar pra aba (comum nos navegadores) — sem isso, os dois
  // chamavam fetchFinance pro mesmo mês em paralelo.
  const revalidatingKeysRef = useRef(new Set());

  const cacheKey = `${month}-${year}`;
  const cachedEntry = cacheRef.current.get(cacheKey);

  const [payables, setPayables] = useState(() => cachedEntry?.payables ?? []);
  const [categories, setCategories] = useState(() => cachedEntry?.categories ?? []);
  const [summary, setSummary] = useState(() => cachedEntry?.summary ?? null);
  const [loading, setLoading] = useState(() => !cachedEntry);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Identidade estável (sem closure sobre month/year/state) — pode entrar em
  // dependência de efeito sem recriar o efeito a cada render, mesma
  // preocupação que already causou o loop de refetch da issue #66.
  const fetchFinance = useCallback(async (key, m, y, { silent = false } = {}) => {
    if (silent) {
      if (revalidatingKeysRef.current.has(key)) return;
      revalidatingKeysRef.current.add(key);
    } else {
      setLoading(true);
    }
    try {
      const [payablesRes, catsRes, summaryRes] = await Promise.all([
        api.get("/payables", { params: { month: m, year: y } }),
        api.get("/categories"),
        api.get("/summary", { params: { month: m, year: y } }),
      ]);
      if (!mountedRef.current) return;
      const data = {
        payables: payablesRes.data ?? [],
        categories: catsRes.data ?? [],
        summary: summaryRes.data ?? null,
        fetchedAt: Date.now(),
      };
      cacheRef.current.set(key, data);
      // Só aplica ao estado exibido se o usuário ainda estiver neste
      // mês/ano — a entrada de cache é gravada de qualquer forma (fica
      // pronta pra quando ele voltar pra este mês).
      if (key === activeKeyRef.current) {
        setPayables(data.payables);
        setCategories(data.categories);
        setSummary(data.summary);
      }
      // Persistência em sessionStorage é só uma otimização de reload — se
      // falhar (quota, modo privado), o cache em memória já foi atualizado
      // e a tela já tem o dado certo; não pode derrubar os setState acima.
      try {
        saveFinanceCache(cacheRef.current);
      } catch {
        // sem persistência entre reloads nesta sessão, mas os dados na
        // tela e o cache em memória continuam corretos
      }
    } catch {
      // keep previous data on error
    } finally {
      if (silent) {
        revalidatingKeysRef.current.delete(key);
      } else if (mountedRef.current && key === activeKeyRef.current) {
        // Mesmo cuidado do setState acima: uma resposta velha (mês que o
        // usuário já trocou) não pode desligar o loading do mês atual, que
        // pode ainda estar buscando.
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    // refresh() explícito (após criar/editar/pagar algo) é a única coisa que
    // invalida o cache — não sabemos o que mudou, então limpa tudo em vez de
    // arriscar mostrar um mês desatualizado.
    if (refreshKey !== lastRefreshKeyRef.current) {
      cacheRef.current.clear();
      lastRefreshKeyRef.current = refreshKey;
    }

    const key = `${month}-${year}`;
    activeKeyRef.current = key;
    const cached = cacheRef.current.get(key);
    if (cached) {
      setPayables(cached.payables);
      setCategories(cached.categories);
      setSummary(cached.summary);
      setLoading(false);
      if (Date.now() - (cached.fetchedAt ?? 0) > STALE_TTL_MS) {
        fetchFinance(key, month, year, { silent: true });
      }
      return;
    }

    fetchFinance(key, month, year);
  }, [month, year, refreshKey, fetchFinance]);

  // Revalida em segundo plano ao voltar pra aba (padrão comum em SaaS: Gmail,
  // Slack) — cobre "deixei aberta e o cron/webhook mudou algo" sem esperar o
  // usuário mexer em mês/ano ou fazer uma mutação local.
  useEffect(() => {
    const revalidateIfStale = () => {
      if (document.visibilityState !== "visible") return;
      const key = `${month}-${year}`;
      const cached = cacheRef.current.get(key);
      // Sem entrada nenhuma: o efeito de cima já cuida na próxima renderização.
      if (cached && Date.now() - (cached.fetchedAt ?? 0) > STALE_TTL_MS) {
        fetchFinance(key, month, year, { silent: true });
      }
    };
    document.addEventListener("visibilitychange", revalidateIfStale);
    window.addEventListener("focus", revalidateIfStale);
    return () => {
      document.removeEventListener("visibilitychange", revalidateIfStale);
      window.removeEventListener("focus", revalidateIfStale);
    };
  }, [month, year, fetchFinance]);

  return (
    <FinanceContext.Provider value={{ payables, categories, summary, loading, refresh }}>
      {children}
    </FinanceContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export const useFinance = () => useContext(FinanceContext);
