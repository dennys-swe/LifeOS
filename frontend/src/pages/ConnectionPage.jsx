import { useEffect, useMemo, useState } from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import api from "../services/api";
import MonthNavigator from "../components/MonthNavigator";

const STATUS = {
  idle: "idle",
  loading: "loading",
  success: "success",
  error: "error",
};

export default function ConnectionPage({ refreshKey, month, year, onMonthChange }) {
  const [status, setStatus] = useState(STATUS.idle);
  const [message, setMessage] = useState("");
  const [payables, setPayables] = useState([]);
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    let mounted = true;

    const loadData = async () => {
      setStatus(STATUS.loading);
      try {
        const [payablesResponse, categoriesResponse] = await Promise.all([
          api.get("/payables", { params: { month, year } }),
          api.get("/categories"),
        ]);

        if (!mounted) return;

        setPayables(payablesResponse.data ?? []);
        setCategories(categoriesResponse.data ?? []);
        setStatus(STATUS.success);
        setMessage("Conectado com sucesso");
      } catch (error) {
        if (!mounted) return;
        setStatus(STATUS.error);
        setMessage("Falha ao conectar com a API");
      }
    };

    loadData();

    return () => {
      mounted = false;
    };
  }, [refreshKey, month, year]);

  const payablesThisMonth = payables;

  const totalPending = useMemo(() => {
    return payablesThisMonth.reduce((acc, item) => {
      if (item.status !== "PENDING") return acc;
      return acc + (Number(item.amount) || 0);
    }, 0);
  }, [payablesThisMonth]);

  const totalPaid = useMemo(() => {
    return payablesThisMonth.reduce((acc, item) => {
      if (item.status !== "PAID") return acc;
      return acc + (Number(item.amount) || 0);
    }, 0);
  }, [payablesThisMonth]);

  const formatCurrency = (value) => {
    return value.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
    });
  };

  const categoryMap = useMemo(() => {
    return new Map(categories.map((category) => [category.id, category]));
  }, [categories]);

  const chartData = useMemo(() => {
    const totals = new Map();
    for (const item of payablesThisMonth) {
      const key = item.category_id || "uncategorized";
      const current = totals.get(key) ?? 0;
      totals.set(key, current + (Number(item.amount) || 0));
    }

    return Array.from(totals.entries()).map(([key, total]) => {
      if (key === "uncategorized") {
        return { name: "Sem categoria", value: total, color: "#64748B" };
      }
      const category = categoryMap.get(key);
      return {
        name: category?.name ?? "Sem categoria",
        value: total,
        color: category?.color_hex ?? "#64748B",
      };
    });
  }, [payablesThisMonth, categoryMap]);


  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10">
        <header className="flex flex-col gap-3">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">
            Dashboard Financeiro
          </p>
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-3xl font-semibold text-white md:text-4xl">
                Controle Financeiro
              </h1>
              <p className="mt-1 text-slate-400">Visao geral do mes</p>
            </div>
            <div className="rounded-full border border-slate-800 bg-slate-900/70 px-4 py-2 text-sm text-slate-300">
              {status === STATUS.loading && "Conectando..."}
              {status === STATUS.success && message}
              {status === STATUS.error && message}
            </div>
          </div>
          <MonthNavigator month={month} year={year} onChange={onMonthChange} />
        </header>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Total Pendente no Mes</p>
            <p className="mt-4 text-3xl font-semibold text-amber-400 md:text-4xl">
              {formatCurrency(totalPending)}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Somatorio de contas pendentes no mes selecionado
            </p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-400">Total Ja Pago</p>
            <p className="mt-4 text-3xl font-semibold text-emerald-400 md:text-4xl">
              {formatCurrency(totalPaid)}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Somatorio de contas pagas no mes selecionado
            </p>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <h2 className="text-lg font-semibold text-white">
              Payables por categoria
            </h2>
            <p className="text-sm text-slate-400">
              Distribuicao do mes selecionado
            </p>
          </div>

          <div className="mt-6 h-72">
            {chartData.length === 0 ? (
              <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-700 text-slate-400">
                Nenhuma conta encontrada para este mes.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={110}
                    paddingAngle={2}
                  >
                    {chartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => formatCurrency(Number(value))}
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "12px",
                    }}
                    labelStyle={{ color: "#e2e8f0" }}
                    itemStyle={{ color: "#e2e8f0" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
