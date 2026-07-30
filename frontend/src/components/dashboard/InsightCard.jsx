import { Link } from "react-router";

import { categoryDetailPath } from "../../lib/routes";

const SEVERITY_STYLE = {
  warning: {
    border: "border-amber-200 dark:border-amber-500/30",
    bg: "bg-amber-50 dark:bg-amber-500/10",
    icon: "bg-amber-400",
    text: "text-amber-800 dark:text-amber-300",
  },
  good: {
    border: "border-emerald-200 dark:border-emerald-500/30",
    bg: "bg-emerald-50 dark:bg-emerald-500/10",
    icon: "bg-emerald-400",
    text: "text-emerald-800 dark:text-emerald-300",
  },
  neutral: {
    border: "border-gray-200 dark:border-slate-700",
    bg: "bg-gray-50 dark:bg-slate-800/60",
    icon: "bg-gray-400 dark:bg-slate-500",
    text: "text-gray-700 dark:text-slate-300",
  },
};

export default function InsightCard({ insight, month, year }) {
  const style = SEVERITY_STYLE[insight.severity] ?? SEVERITY_STYLE.neutral;

  const content = (
    <div
      className={`flex h-full w-64 flex-shrink-0 flex-col gap-1.5 rounded-2xl border p-4 ${style.border} ${style.bg}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.icon}`} />
      <p className={`text-sm font-semibold leading-snug ${style.text}`}>{insight.title}</p>
      <p className="text-xs leading-snug text-gray-600 dark:text-slate-400">{insight.detail}</p>
    </div>
  );

  // "category_id: null" também é um destino válido (Sem categoria) — só pula o
  // link para insights que não são sobre nenhuma categoria (ex: ritmo do mês).
  if (insight.kind === "pace") return content;

  return (
    <Link to={categoryDetailPath(insight.category_id, month, year)} className="contents">
      {content}
    </Link>
  );
}
