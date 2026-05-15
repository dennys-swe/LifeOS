import { useEffect, useState } from "react";
import api from "../services/api";
import { useFinance } from "../context/FinanceContext";

const PAGES = {
  dashboard: "dashboard",
  payables: "payables",
  transactions: "transactions",
  recurring: "recurring",
  rules: "rules",
  upload: "upload",
  banks: "banks",
};

const NAV_ITEMS = [
  { key: PAGES.dashboard, label: "Início", icon: "⊞" },
  { key: PAGES.payables, label: "Contas", icon: "📋" },
  { key: PAGES.transactions, label: "Transações", icon: "↕" },
  { key: PAGES.recurring, label: "Recorrentes", icon: "↺" },
  { key: PAGES.rules, label: "Regras", icon: "⚙" },
  { key: PAGES.upload, label: "Importar", icon: "↑" },
  { key: PAGES.banks, label: "Bancos", icon: "🏦" },
];

// items shown in bottom mobile nav (most used)
const MOBILE_ITEMS = [
  PAGES.dashboard,
  PAGES.payables,
  PAGES.transactions,
  PAGES.upload,
  PAGES.banks,
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
    <>
      {/* Top nav — desktop */}
      <nav className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Controle Financeiro</p>
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

      {/* Bottom nav — mobile only */}
      <nav className="fixed bottom-0 left-0 right-0 z-20 border-t border-slate-800 bg-slate-950/95 backdrop-blur md:hidden">
        <div className="flex items-center justify-around px-2 py-2">
          {MOBILE_ITEMS.map((key) => {
            const item = NAV_ITEMS.find((n) => n.key === key);
            if (!item) return null;
            const active = activePage === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => onNavigate(item.key)}
                className="relative flex flex-col items-center gap-1 px-3 py-1"
              >
                <span className={`text-lg leading-none ${active ? "text-emerald-400" : "text-slate-500"}`}>
                  {item.icon}
                </span>
                <span className={`text-[10px] font-medium ${active ? "text-emerald-400" : "text-slate-500"}`}>
                  {item.label}
                </span>
                {item.key === PAGES.payables && upcomingCount > 0 && (
                  <span className="absolute right-1 top-0 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-rose-500 text-[8px] font-bold text-white">
                    {upcomingCount > 9 ? "9+" : upcomingCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Spacer so content is not hidden behind bottom nav on mobile */}
      <div className="h-16 md:hidden" />
    </>
  );
}
