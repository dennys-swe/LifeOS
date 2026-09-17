import { Suspense, useState } from "react";
import { Navigate, Outlet } from "react-router";

import { useAuth } from "../context/AuthContext";
import { FinanceProvider } from "../context/FinanceContext";
import Sidebar from "./Sidebar";
import BottomNav from "./BottomNav";
import Header from "./Header";
import FabModal from "./FabModal";
import PageLoader from "./PageLoader";
import Skeleton from "./ui/Skeleton";

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
    return <PageLoader />;
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
            {/* Suspense aqui (não em volta de todo <Routes>) — a página lazy
                suspende só o conteúdo; Sidebar/Header/BottomNav continuam
                montados em vez de a casca inteira sumir a cada rota nova. */}
            <Suspense fallback={<Skeleton className="m-4 h-64" />}>
              <Outlet
                context={{
                  month: selectedMonth,
                  year: selectedYear,
                  onMonthChange: handleMonthChange,
                  payablesFilter,
                  onPayablesFilterChange: setPayablesFilter,
                }}
              />
            </Suspense>
          </main>
        </div>

        <FabModal />
      </FinanceProvider>
    </div>
  );
}
