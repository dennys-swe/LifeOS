import { useState } from "react";
import { Link } from "react-router";

import CategoryDot from "../ui/CategoryDot";
import DeltaBadge from "../ui/DeltaBadge";
import EmptyState from "../ui/EmptyState";
import { fmt } from "../../lib/format";
import { categoryDetailPath } from "../../lib/routes";

function pctChange(current, previous) {
  if (!previous || Number(previous) === 0) return null;
  return ((Number(current) - Number(previous)) / Math.abs(Number(previous))) * 100;
}

export default function CategorySpendList({ categories, prevCategories, month, year }) {
  const [showAll, setShowAll] = useState(false);
  const withSpend = categories.filter((c) => Number(c.total_expenses) > 0);

  if (withSpend.length === 0) {
    return <EmptyState>Nenhum gasto registrado neste mês.</EmptyState>;
  }

  const prevByKey = new Map(
    (prevCategories ?? []).map((c) => [c.category_id ?? "uncategorized", c])
  );
  const max = Math.max(...withSpend.map((c) => Number(c.total_expenses)));

  const visibleCategories = showAll ? withSpend : withSpend.slice(0, 6);
  const hiddenCount = withSpend.length - 6;

  return (
    <div className="flex flex-col gap-1.5">
      {visibleCategories.map((c) => {
        const key = c.category_id ?? "uncategorized";
        const prev = prevByKey.get(key);
        const deltaPct = pctChange(c.total_expenses, prev?.total_expenses);
        const barPct = max > 0 ? (Number(c.total_expenses) / max) * 100 : 0;

        return (
          <Link
            key={key}
            to={categoryDetailPath(c.category_id, month, year)}
            className="group flex items-center gap-3 rounded-2xl p-2.5 transition hover:bg-slate-100/80 dark:hover:bg-slate-800/60"
          >
            <CategoryDot color={c.color_hex} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-semibold text-slate-800 dark:text-slate-200 group-hover:text-emerald-600 dark:group-hover:text-emerald-400">
                  {c.category_name}
                </span>
                <span className="font-display flex-shrink-0 text-sm font-bold text-slate-900 dark:text-white">
                  {fmt(c.total_expenses)}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className="h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${barPct}%`, backgroundColor: c.color_hex }}
                  />
                </div>
                <span className="flex-shrink-0 text-xs font-medium text-slate-400 dark:text-slate-500">
                  {c.transaction_count} lanç.
                </span>
                <DeltaBadge pct={deltaPct} invertColor />
              </div>
            </div>
          </Link>
        );
      })}

      {hiddenCount > 0 && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="mt-2 text-center text-xs font-bold text-emerald-600 hover:underline dark:text-emerald-400"
        >
          {showAll ? "Mostrar menos" : `+ Mostrar mais (${hiddenCount} categorias)`}
        </button>
      )}
    </div>
  );
}
