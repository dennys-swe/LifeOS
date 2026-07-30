import Card from "./Card";
import { fmt } from "../../lib/format";

export default function StatCard({ label, value, subtitle, valueColor, icon: Icon }) {
  return (
    <Card className="p-5 relative overflow-hidden group">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          {label}
        </p>
        {Icon && (
          <div className="p-2 rounded-xl bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 group-hover:scale-110 transition-transform">
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      <p className={`mt-3 font-display text-2xl font-bold tracking-tight ${valueColor ?? "text-slate-900 dark:text-white"}`}>
        {typeof value === "number" ? fmt(value) : value}
      </p>
      {subtitle && <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">{subtitle}</p>}
    </Card>
  );
}
