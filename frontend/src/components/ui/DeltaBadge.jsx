import { fmtPct } from "../../lib/format";

/**
 * `invertColor`: por padrão, alta = bom (ex: receita). Para gasto, alta é ruim
 * — passe `invertColor` para inverter a semântica de cor sem inverter o sinal.
 */
export default function DeltaBadge({ pct, invertColor = false }) {
  if (pct === null || pct === undefined || isNaN(pct)) return null;
  const positive = pct > 0;
  const good = invertColor ? !positive : positive;
  const color = good
    ? "border border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-400"
    : "border border-rose-500/20 bg-rose-500/10 text-rose-600 dark:border-rose-500/30 dark:bg-rose-500/15 dark:text-rose-400";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-tight shadow-sm ${color}`}>
      <span>{positive ? "↑" : "↓"}</span>
      <span>{fmtPct(Math.abs(pct))}</span>
    </span>
  );
}
