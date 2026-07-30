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
    <div className="rounded-xl border border-slate-200/80 bg-white/95 px-3 py-1.5 text-xs shadow-xl backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-900/95">
      <p className="font-semibold text-slate-400 uppercase tracking-wider">{label}</p>
      <p className="font-display mt-0.5 text-xs font-bold text-slate-900 dark:text-white">{fmt(value)}</p>
    </div>
  );
}

export default function TrendChart({ months, currentMonth, currentYear, height = 130 }) {
  const data = months.map((m) => ({
    label: `${monthLabel(m.month, m.year)}/${String(m.year).slice(2)}`,
    value: Number(m.total_expenses),
    isCurrent: m.month === currentMonth && m.year === currentYear,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 4, left: 4, bottom: 0 }}>
        <XAxis
          dataKey="label"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 10, fill: "currentColor" }}
          className="text-slate-400 dark:text-slate-500 font-medium"
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "currentColor", opacity: 0.05 }} />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={32}>
          {data.map((entry) => (
            <Cell
              key={entry.label}
              fill={entry.isCurrent ? "#10b981" : "#64748b"}
              opacity={entry.isCurrent ? 1 : 0.45}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
