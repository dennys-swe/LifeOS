import { useEffect, useState } from "react";
import { NavLink } from "react-router";
import api from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useFinance } from "../context/FinanceContext";
import { useTheme } from "../context/ThemeContext";

// ─── Icons ────────────────────────────────────────────────────────────────────

function IconHome({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
    </svg>
  );
}

function IconList({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
    </svg>
  );
}

function IconArrows({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7.5 7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5" />
    </svg>
  );
}

function IconBank({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0 0 12 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75Z" />
    </svg>
  );
}

function IconSettings({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

function IconSun({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
    </svg>
  );
}

function IconMoon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
    </svg>
  );
}

function IconLogout({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 9V5.25A2.25 2.25 0 0 1 10.5 3h6a2.25 2.25 0 0 1 2.25 2.25v13.5A2.25 2.25 0 0 1 16.5 21h-6a2.25 2.25 0 0 1-2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3H21" />
    </svg>
  );
}

// ─── Nav config ───────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { to: "/", end: true, label: "Dashboard", Icon: IconHome },
  { to: "/payables", label: "Contas", Icon: IconList, showBadge: true },
  { to: "/transactions", label: "Extrato", Icon: IconArrows },
  { to: "/banks", label: "Contas Bancárias", Icon: IconBank },
  { to: "/settings", label: "Ajustes", Icon: IconSettings },
];

const linkClass = ({ isActive }) =>
  `relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
    isActive
      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
      : "text-gray-600 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-900"
  }`;

const mobileLinkClass = ({ isActive }) =>
  `relative flex flex-1 flex-col items-center gap-1 py-2 ${
    isActive ? "text-emerald-600 dark:text-emerald-400" : "text-gray-400 dark:text-slate-500"
  }`;

// ─── Component ────────────────────────────────────────────────────────────────

export default function Sidebar() {
  const { refresh } = useFinance() ?? {};
  const { dark, toggle } = useTheme();
  const { user, logout } = useAuth();
  const [upcomingCount, setUpcomingCount] = useState(0);

  useEffect(() => {
    api
      .get("/payables/upcoming?days=7")
      .then((res) => setUpcomingCount(res.data?.length ?? 0))
      .catch(() => setUpcomingCount(0));
  }, [refresh]);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-gray-200 bg-white dark:border-slate-800 dark:bg-slate-950 md:flex">
        {/* Logo */}
        <div className="flex h-16 items-center gap-2.5 border-b border-gray-200 px-5 dark:border-slate-800">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500">
            <span className="text-xs font-bold text-white">LO</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900 dark:text-slate-100">LifeOS</p>
            <p className="text-xs text-gray-400 dark:text-slate-500">Controle Financeiro</p>
          </div>
        </div>

        {/* Nav items */}
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map((navItem) => {
            const badge = navItem.showBadge && upcomingCount > 0;
            return (
              <NavLink key={navItem.to} to={navItem.to} end={navItem.end} className={linkClass}>
                <navItem.Icon className="h-5 w-5 flex-shrink-0" />
                <span>{navItem.label}</span>
                {badge && (
                  <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
                    {upcomingCount > 9 ? "9+" : upcomingCount}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* User + Theme toggle */}
        <div className="border-t border-gray-200 p-3 dark:border-slate-800">
          {user && (
            <p className="truncate px-3 pb-2 text-xs text-gray-400 dark:text-slate-500" title={user.email}>
              {user.email}
            </p>
          )}
          <button
            type="button"
            onClick={toggle}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-900"
          >
            {dark ? <IconSun className="h-5 w-5" /> : <IconMoon className="h-5 w-5" />}
            <span>{dark ? "Tema claro" : "Tema escuro"}</span>
          </button>
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-900"
          >
            <IconLogout className="h-5 w-5" />
            <span>Sair</span>
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-950 md:hidden">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500">
            <span className="text-[10px] font-bold text-white">LO</span>
          </div>
          <span className="text-sm font-semibold text-gray-900 dark:text-slate-100">LifeOS</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={toggle}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-900"
          >
            {dark ? <IconSun className="h-5 w-5" /> : <IconMoon className="h-5 w-5" />}
          </button>
          <button
            type="button"
            onClick={logout}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-900"
          >
            <IconLogout className="h-5 w-5" />
          </button>
        </div>
      </header>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-gray-200 bg-white dark:border-slate-800 dark:bg-slate-950 md:hidden">
        {NAV_ITEMS.map((navItem) => {
          const badge = navItem.showBadge && upcomingCount > 0;
          return (
            <NavLink key={navItem.to} to={navItem.to} end={navItem.end} className={mobileLinkClass}>
              <navItem.Icon className="h-5 w-5" />
              <span className="text-[10px] font-medium">{navItem.label}</span>
              {badge && (
                <span className="absolute right-3 top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-rose-500 text-[8px] font-bold text-white">
                  {upcomingCount > 9 ? "9+" : upcomingCount}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>
    </>
  );
}

