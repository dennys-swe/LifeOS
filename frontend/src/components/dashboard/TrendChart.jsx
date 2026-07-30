import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from "recharts";

import { fmt } from "../../lib/format";

function monthLabel(month, year) {
  return new Date(year, month - 1, 1)
    .toLocaleDateString("pt-BR", { month: "short" })
    .replace(".", "");
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { label, value } = payload[0].payload;
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-slate-700 dark:bg-slate-800">
      <p className="font-medium text-gray-500 dark:text-slate-400">{label}</p>
      <p className="font-semibold text-gray-900 dark:text-slate-100">{fmt(value)}</p>
    </div>
  );
}

/** Primeiro gráfico de série temporal do app — `/summary/history` já existia,
 * mas nunca tinha sido consumido pelo frontend. */
export default function TrendChart({ months, currentMonth, currentYear }) {
  const data = months.map((m) => ({
    label: `${monthLabel(m.month, m.year)}/${String(m.year).slice(2)}`,
    value: Number(m.total_expenses),
    isCurrent: m.month === currentMonth && m.year === currentYear,
  }));

  return (
    <ResponsiveContainer width="100%" height={140}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
        <XAxis
          dataKey="label"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 11, fill: "currentColor" }}
          className="text-gray-400 dark:text-slate-500"
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "currentColor", opacity: 0.05 }} />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={36}>
          {data.map((entry) => (
            <Cell key={entry.label} fill={entry.isCurrent ? "#10b981" : "#94a3b8"} opacity={entry.isCurrent ? 1 : 0.5} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
