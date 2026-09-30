import { describeFreshness } from "../../lib/connectionFreshness";

// Distinto de "Sincronizado": aquilo é quando o LifeOS leu a Pluggy; isto é quando a
// Pluggy leu o banco. Uma conexão pode ter sincronizado hoje com dado de 13 dias.
const STYLES = {
  fresh: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  stale: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  attention: "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400",
  unknown: "border-slate-400/30 bg-slate-500/10 text-slate-600 dark:text-slate-400",
};

export default function ConnectionFreshness({ freshness }) {
  const info = describeFreshness(freshness);
  if (!info) return null;

  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1" data-testid="connection-freshness">
      <span
        className={`inline-flex flex-shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold ${STYLES[info.state] ?? STYLES.unknown}`}
      >
        {info.label}
      </span>
      <span className="text-xs text-slate-500 dark:text-slate-400">{info.detail}</span>
      {info.consent && (
        <span className="text-xs font-semibold text-amber-600 dark:text-amber-400">{info.consent}</span>
      )}
    </div>
  );
}
