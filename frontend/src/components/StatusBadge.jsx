import React from 'react';

export default function StatusBadge({ status, isOverdue, isDueToday }) {
  let style = "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
  let dotColor = "bg-slate-400";
  let label = "";

  if (status === "PAID") {
    style = "border border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300";
    dotColor = "bg-emerald-500";
    label = "PAGO";
  } else if (isOverdue) {
    style = "border border-rose-500/20 bg-rose-500/10 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/15 dark:text-rose-300";
    dotColor = "bg-rose-500 animate-pulse";
    label = "ATRASADA";
  } else if (isDueToday) {
    style = "border border-amber-500/20 bg-amber-500/10 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300";
    dotColor = "bg-amber-500 animate-ping";
    label = "VENCE HOJE";
  }

  if (!label) return null;

  return (
    <span
      className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider shadow-sm ${style}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      <span>{label}</span>
    </span>
  );
}