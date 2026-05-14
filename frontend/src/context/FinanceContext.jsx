import { createContext, useContext, useEffect, useState } from "react";
import api from "../services/api";

const FinanceContext = createContext(null);

export function FinanceProvider({ children, month, year }) {
  const [payables, setPayables] = useState([]);
  const [categories, setCategories] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
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
        setPayables(payablesRes.data ?? []);
        setCategories(catsRes.data ?? []);
        setSummary(summaryRes.data ?? null);
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
