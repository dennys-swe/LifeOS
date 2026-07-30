import { useState } from "react";
import { Navigate, Outlet } from "react-router";

import { useAuth } from "../context/AuthContext";
import { FinanceProvider } from "../context/FinanceContext";
import Sidebar from "./Sidebar";
import BottomNav from "./BottomNav";
import Header from "./Header";
import FabModal from "./FabModal";

export default function ProtectedLayout() {
  const { user, loading } = useAuth();
  const [payablesFilter, setPayablesFilter] = useState("all");
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());

  const handleMonthChange = (month, year) => {
    setSelectedMonth(month);
    setSelectedYear(year);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent" />
          <p className="font-display text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
            LifeOS · Carregando...
          </p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans text-slate-900 antialiased selection:bg-emerald-500 selection:text-white dark:bg-slate-950 dark:text-slate-100">
      <FinanceProvider month={selectedMonth} year={selectedYear}>
        <Sidebar />
        <BottomNav />

        <div className="flex flex-1 flex-col overflow-x-hidden md:ml-64">
          <Header />
          <main className="flex-1 pb-20 md:pb-8">
            <Outlet
              context={{
                month: selectedMonth,
                year: selectedYear,
                onMonthChange: handleMonthChange,
                payablesFilter,
                onPayablesFilterChange: setPayablesFilter,
              }}
            />
          </main>
        </div>

        <FabModal />
      </FinanceProvider>
    </div>
  );
}
