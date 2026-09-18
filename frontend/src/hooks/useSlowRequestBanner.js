import { useEffect, useState } from "react";
import { shouldShowColdStartBanner } from "../services/api";

// Issue #23 (P2): checagem por polling, não por evento — uma requisição só
// "fica lenta" com o passar do tempo (não há um instante único de "agora
// ela ficou lenta" pra escutar), então precisa reavaliar periodicamente
// enquanto ela ainda está pendente.
const CHECK_INTERVAL_MS = 1000;

export function useSlowRequestBanner() {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const id = setInterval(() => {
      setSlow(shouldShowColdStartBanner());
    }, CHECK_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return slow;
}
