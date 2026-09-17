import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
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
// aproveita o último dado bom em vez de mostrar tela zerada.
const SESSION_CACHE_KEY = "lifeos-finance-cache-v1";

function loadSessionCache() {
  const raw = sessionStorage.getItem(SESSION_CACHE_KEY);
  return raw ? new Map(Object.entries(JSON.parse(raw))) : new Map();
}

function saveSessionCache(cache) {
  sessionStorage.setItem(SESSION_CACHE_KEY, JSON.stringify(Object.fromEntries(cache)));
}

export function FinanceProvider({ children, month, year }) {
  const cacheRef = useRef(null);
  if (cacheRef.current === null) {
    cacheRef.current = loadSessionCache();
  }
  const lastRefreshKeyRef = useRef(0);

  const cacheKey = `${month}-${year}`;
  const cachedEntry = cacheRef.current.get(cacheKey);

  const [payables, setPayables] = useState(() => cachedEntry?.payables ?? []);
  const [categories, setCategories] = useState(() => cachedEntry?.categories ?? []);
  const [summary, setSummary] = useState(() => cachedEntry?.summary ?? null);
  const [loading, setLoading] = useState(() => !cachedEntry);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    // refresh() explícito (após criar/editar/pagar algo) é a única coisa que
    // invalida o cache — não sabemos o que mudou, então limpa tudo em vez de
    // arriscar mostrar um mês desatualizado.
    if (refreshKey !== lastRefreshKeyRef.current) {
      cacheRef.current.clear();
      lastRefreshKeyRef.current = refreshKey;
    }

    const key = `${month}-${year}`;
    const cached = cacheRef.current.get(key);
    if (cached) {
      setPayables(cached.payables);
      setCategories(cached.categories);
      setSummary(cached.summary);
      setLoading(false);
      return;
    }

    let mounted = true;

    const load = async () => {
      setLoading(true);
      try {
        const [payablesRes, catsRes, summaryRes] = await Promise.all([
          api.get("/payables", { params: { month, year } }),
          api.get("/categories"),
          api.get("/summary", { params: { month, year } }),
        ]);
        if (!mounted) return;
        const data = {
          payables: payablesRes.data ?? [],
          categories: catsRes.data ?? [],
          summary: summaryRes.data ?? null,
        };
        cacheRef.current.set(key, data);
        saveSessionCache(cacheRef.current);
        setPayables(data.payables);
        setCategories(data.categories);
        setSummary(data.summary);
      } catch {
        // keep previous data on error
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();

    return () => {
      mounted = false;
    };
  }, [month, year, refreshKey]);

  return (
    <FinanceContext.Provider value={{ payables, categories, summary, loading, refresh }}>
      {children}
    </FinanceContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export const useFinance = () => useContext(FinanceContext);
