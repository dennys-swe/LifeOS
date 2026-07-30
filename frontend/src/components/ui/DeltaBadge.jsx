import { fmtPct } from "../../lib/format";

/**
 * `invertColor`: por padrão, alta = bom (ex: receita). Para gasto, alta é ruim
 * — passe `invertColor` para inverter a semântica de cor sem inverter o sinal.
 */
export default function DeltaBadge({ pct, invertColor = false }) {
  if (pct === null || pct === undefined) return null;
  const positive = pct > 0;
  const good = invertColor ? !positive : positive;
  const color = good
    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
    : "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400";
  return (
    <span className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>
      {positive ? "↑" : "↓"} {fmtPct(Math.abs(pct))}
    </span>
  );
}
