import { Link } from "react-router";

import { categoryDetailPath } from "../../lib/routes";

const SEVERITY_STYLE = {
  warning: {
    border: "border-amber-500/30 dark:border-amber-500/40",
    bg: "bg-amber-500/10 dark:bg-amber-500/15 backdrop-blur-md",
    icon: "bg-amber-500",
    text: "text-amber-900 dark:text-amber-300",
  },
  good: {
    border: "border-emerald-500/30 dark:border-emerald-500/40",
    bg: "bg-emerald-500/10 dark:bg-emerald-500/15 backdrop-blur-md",
    icon: "bg-emerald-500",
    text: "text-emerald-900 dark:text-emerald-300",
  },
  neutral: {
    border: "border-slate-200/80 dark:border-slate-800/80",
    bg: "bg-white/90 dark:bg-slate-900/80 backdrop-blur-md",
    icon: "bg-slate-400 dark:bg-slate-500",
    text: "text-slate-800 dark:text-slate-200",
  },
};

export default function InsightCard({ insight, month, year }) {
  const style = SEVERITY_STYLE[insight.severity] ?? SEVERITY_STYLE.neutral;

  const content = (
    <div
      className={`flex h-full w-72 flex-shrink-0 flex-col justify-between rounded-2xl border p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${style.border} ${style.bg}`}
    >
      <div className="flex items-start gap-2.5">
        <span className={`mt-1 h-2.5 w-2.5 flex-shrink-0 rounded-full ${style.icon}`} />
        <p className={`font-display text-sm md:text-base font-extrabold leading-snug ${style.text}`}>
          {insight.title}
        </p>
      </div>
      <p className="mt-3 text-xs font-medium leading-relaxed text-slate-600 dark:text-slate-400">
        {insight.detail}
      </p>
    </div>
  );

  if (insight.kind === "pace") {
    return <div className="flex flex-shrink-0 items-stretch">{content}</div>;
  }

  return (
    <Link to={categoryDetailPath(insight.category_id, month, year)} className="flex flex-shrink-0 items-stretch">
      {content}
    </Link>
  );
}
