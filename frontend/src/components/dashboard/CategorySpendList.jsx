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

/**
 * Gasto real por categoria, em barras — substitui o donut. Já vem ordenado por
 * gasto do backend (`summary_service.get_summary`); com 10+ categorias uma
 * lista ordenada informa mais rápido que uma rosca.
 */
export default function CategorySpendList({ categories, prevCategories, month, year }) {
  const withSpend = categories.filter((c) => Number(c.total_expenses) > 0);

  if (withSpend.length === 0) {
    return <EmptyState>Nenhum gasto registrado neste mês.</EmptyState>;
  }

  const prevByKey = new Map(
    (prevCategories ?? []).map((c) => [c.category_id ?? "uncategorized", c])
  );
  const max = Math.max(...withSpend.map((c) => Number(c.total_expenses)));

  return (
    <div className="flex flex-col gap-1">
      {withSpend.map((c) => {
        const key = c.category_id ?? "uncategorized";
        const prev = prevByKey.get(key);
        const deltaPct = pctChange(c.total_expenses, prev?.total_expenses);
        const barPct = max > 0 ? (Number(c.total_expenses) / max) * 100 : 0;

        return (
          <Link
            key={key}
            to={categoryDetailPath(c.category_id, month, year)}
            className="group flex items-center gap-3 rounded-xl px-2 py-2.5 transition hover:bg-gray-50 dark:hover:bg-slate-800/60"
          >
            <CategoryDot color={c.color_hex} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium text-gray-800 dark:text-slate-200 group-hover:underline">
                  {c.category_name}
                </span>
                <span className="flex-shrink-0 text-sm font-semibold text-gray-900 dark:text-slate-100">
                  {fmt(c.total_expenses)}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-800">
                  <div
                    className="h-1.5 rounded-full transition-all"
                    style={{ width: `${barPct}%`, backgroundColor: c.color_hex }}
                  />
                </div>
                <span className="flex-shrink-0 text-xs text-gray-400 dark:text-slate-500">
                  {c.transaction_count} lanç.
                </span>
                {/* Gasto é ruim subindo — inverte a semântica de cor do delta. */}
                <DeltaBadge pct={deltaPct} invertColor />
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
