import React from 'react';

export default function StatusBadge({ status, isOverdue, isDueToday }) {
  let style = "bg-gray-100 text-gray-600 dark:bg-slate-500/20 dark:text-slate-300";
  let label = "";

  if (status === "PAID") {
    style = "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300";
    label = "PAGO";
  } else if (isOverdue) {
    style = "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300";
    label = "ATRASADA";
  } else if (isDueToday) {
    style = "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300";
    label = "VENCE HOJE";
  }

  if (!label) return null;

  return (
    <span
      className={`mt-2 inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${style}`}
    >
      {label}
    </span>
  );
}