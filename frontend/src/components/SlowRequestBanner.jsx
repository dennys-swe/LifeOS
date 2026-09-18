import { useSlowRequestBanner } from "../hooks/useSlowRequestBanner";

// Issue #23 (P2): sem isso, o cold start residual do Render Free (o
// keep-alive da #112 reduz mas não elimina) parecia a tela travada — nada
// distinguia "sem internet"/"bug" de "o servidor tá ligando, espera uns
// segundos". Fixo no topo, visível em qualquer rota (login incluído).
export default function SlowRequestBanner() {
  const slow = useSlowRequestBanner();

  if (!slow) return null;

  return (
    <div className="fixed inset-x-0 top-0 z-[60] flex justify-center px-4 pt-3">
      <div className="flex items-center gap-2 rounded-2xl border border-amber-500/30 bg-amber-50/95 px-4 py-2 text-xs font-semibold text-amber-700 shadow-lg backdrop-blur-xl animate-in fade-in slide-in-from-top-2 duration-300 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
        <span className="h-1.5 w-1.5 flex-shrink-0 animate-pulse rounded-full bg-amber-500" />
        Aquecendo o servidor — a primeira resposta pode levar até 1 minuto…
      </div>
    </div>
  );
}
