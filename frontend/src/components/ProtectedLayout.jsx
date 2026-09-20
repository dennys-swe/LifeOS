import { Suspense, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

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
  const location = useLocation();
  // FinanceProvider fica acima do <Outlet> (nunca desmonta ao trocar de
  // rota) e busca os fetches próprios do DashboardPage junto dos 3 core
  // (issue #141) — mas só quando a rota atual É o dashboard, pra não pagar
  // 5 chamadas a mais toda vez que `refresh()` é chamado de outra página
  // (convenção do projeto: toda mutação chama refresh()).
  //
  // Cogitado (e revertido) fazer o próprio DashboardPage avisar isso via
  // efeito ao montar, em vez do provider inferir pela rota — mais
  // desacoplado em tese, mas na prática quebra: DashboardPage é
  // descendente do FinanceProvider, e o efeito de fetch do provider (que
  // já dispara na MESMA montagem) roda antes do efeito do descendente
  // conseguir avisar — mesmo com useLayoutEffect, porque o setState do
  // efeito do filho dispara um commit separado cujos efeitos passivos são
  // processados DEPOIS do efeito passivo já agendado pelo commit original
  // do provider. Resultado: 2 fetches completos (um sem os extras, outro
  // completando) no primeiro carregamento do dashboard — pior do que as 5
  // chamadas extras que a leitura de rota evita nas outras páginas. Ler a
  // rota aqui é o valor conhecido SINCRONAMENTE no primeiro render, sem
  // essa corrida.
  const needsDashboardData = location.pathname === "/";
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
      <FinanceProvider
        month={selectedMonth}
        year={selectedYear}
        needsDashboardData={needsDashboardData}
      >
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
