import { useEffect, useRef } from "react";

// Compartilhado por FinanceContext e BankAccountsPage — um fetch em
// andamento não pode aplicar setState depois que o componente desmontou.
// Reseta pra `true` no próprio setup do efeito (não só declara o valor
// inicial do ref): o StrictMode do modo dev roda montagem → limpeza →
// montagem de novo de propósito, e só a limpeza mexendo no ref deixava
// `mountedRef.current` travado em `false` pra sempre depois da 2ª
// montagem — nunca afetou produção (que não double-invoca efeitos), mas
// travava qualquer fetch em `npm run dev` silenciosamente.
export function useMountedRef() {
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  return mountedRef;
}
