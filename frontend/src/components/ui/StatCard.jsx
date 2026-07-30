import Card from "./Card";
import { fmt } from "../../lib/format";

export default function StatCard({ label, value, subtitle, valueColor }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-slate-500">
        {label}
      </p>
      <p className={`mt-3 text-2xl font-semibold ${valueColor ?? "text-gray-900 dark:text-slate-100"}`}>
        {fmt(value)}
      </p>
      {subtitle && <p className="mt-2 text-xs text-gray-400 dark:text-slate-500">{subtitle}</p>}
    </Card>
  );
}
