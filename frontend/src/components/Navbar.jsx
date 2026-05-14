import { useEffect, useState } from "react";
import api from "../services/api";
import { useFinance } from "../context/FinanceContext";

const PAGES = {
  dashboard: "dashboard",
  payables: "payables",
  recurring: "recurring",
  rules: "rules",
  upload: "upload",
};

const NAV_ITEMS = [
  { key: PAGES.dashboard, label: "Início" },
  { key: PAGES.payables, label: "Contas" },
  { key: PAGES.recurring, label: "Recorrentes" },
  { key: PAGES.rules, label: "Regras" },
  { key: PAGES.upload, label: "Importar" },
];

export default function Navbar({ activePage, onNavigate }) {
  const { refresh } = useFinance() ?? {};
  const [upcomingCount, setUpcomingCount] = useState(0);

  useEffect(() => {
    api
      .get("/payables/upcoming?days=7")
      .then((res) => setUpcomingCount(res.data?.length ?? 0))
      .catch(() => setUpcomingCount(0));
  }, [refresh]);

  return (
    <nav className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">
            Controle Financeiro
          </p>
          <p className="text-sm font-semibold text-white">Painel</p>
        </div>
        <div className="flex items-center gap-1 md:gap-2">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => onNavigate(item.key)}
              className={`relative rounded-full px-3 py-2 text-xs font-medium transition md:px-4 md:text-sm ${
                activePage === item.key
                  ? "bg-emerald-500/20 text-emerald-300"
                  : "text-slate-300 hover:bg-slate-900"
              }`}
            >
              {item.label}
              {item.key === PAGES.payables && upcomingCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white">
                  {upcomingCount > 9 ? "9+" : upcomingCount}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
