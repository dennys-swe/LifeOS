import { useEffect, useRef } from "react";

// Compartilhado por FinanceContext (issue #110) e BankAccountsPage (issue
// #116) — cada um decide o que conta como "velho" (TTL por chave de
// mês/ano vs. um único timestamp), mas os dois precisam do mesmo gatilho:
// revalidar ao voltar o foco/visibilidade da aba, sem disparar duas vezes
// quando visibilitychange e focus disparam juntos (comum nos navegadores).
export function useRevalidateOnFocus(revalidate) {
  const inFlightRef = useRef(false);

  useEffect(() => {
    const handler = async () => {
      if (document.visibilityState !== "visible") return;
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        await revalidate();
      } finally {
        inFlightRef.current = false;
      }
    };
    document.addEventListener("visibilitychange", handler);
    window.addEventListener("focus", handler);
    return () => {
      document.removeEventListener("visibilitychange", handler);
      window.removeEventListener("focus", handler);
    };
  }, [revalidate]);
}
