import { useState } from "react";

import { FinanceProvider } from "./context/FinanceContext";
import ConnectionPage from "./pages/ConnectionPage";
import PayablesPage from "./pages/PayablesPage";
import RecurringPayablesPage from "./pages/RecurringPayablesPage";
import CategoryRulesPage from "./pages/CategoryRulesPage";
import TransactionsPage from "./pages/TransactionsPage";
import UploadPage from "./pages/UploadPage";
import BankAccountsPage from "./pages/BankAccountsPage";
import FabModal from "./components/FabModal";
import Navbar from "./components/Navbar";

const PAGES = {
  dashboard: "dashboard",
  payables: "payables",
  transactions: "transactions",
  recurring: "recurring",
  rules: "rules",
  upload: "upload",
  banks: "banks",
};

export default function App() {
  const [activePage, setActivePage] = useState(PAGES.dashboard);
  const [payablesFilter, setPayablesFilter] = useState("all");
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());

  const handleMonthChange = (month, year) => {
    setSelectedMonth(month);
    setSelectedYear(year);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <FinanceProvider month={selectedMonth} year={selectedYear}>
        <Navbar activePage={activePage} onNavigate={setActivePage} />

        {activePage === PAGES.dashboard && (
          <ConnectionPage
            month={selectedMonth}
            year={selectedYear}
            onMonthChange={handleMonthChange}
          />
        )}
        {activePage === PAGES.payables && (
          <PayablesPage
            filter={payablesFilter}
            onFilterChange={setPayablesFilter}
            month={selectedMonth}
            year={selectedYear}
            onMonthChange={handleMonthChange}
          />
        )}
        {activePage === PAGES.transactions && (
          <TransactionsPage
            month={selectedMonth}
            year={selectedYear}
            onMonthChange={handleMonthChange}
          />
        )}
        {activePage === PAGES.recurring && (
          <RecurringPayablesPage month={selectedMonth} year={selectedYear} />
        )}
        {activePage === PAGES.rules && <CategoryRulesPage />}
        {activePage === PAGES.upload && (
          <UploadPage onNavigate={setActivePage} />
        )}
        {activePage === PAGES.banks && <BankAccountsPage />}

        <FabModal />
      </FinanceProvider>
    </div>
  );
}
