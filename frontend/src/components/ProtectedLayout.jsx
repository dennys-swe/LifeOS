import { useState } from "react";
import { Navigate, Outlet } from "react-router";

import { useAuth } from "../context/AuthContext";
import { FinanceProvider } from "../context/FinanceContext";
import Sidebar from "./Sidebar";
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
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-slate-950">
        <p className="text-sm text-gray-400 dark:text-slate-500">Carregando...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-slate-950">
      <FinanceProvider month={selectedMonth} year={selectedYear}>
        <Sidebar />

        <main className="flex-1 overflow-x-hidden md:ml-60">
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

        <FabModal />
      </FinanceProvider>
    </div>
  );
}
