import { useState } from "react";

import { ThemeProvider } from "./context/ThemeContext";
import { FinanceProvider } from "./context/FinanceContext";
import Sidebar from "./components/Sidebar";
import { PAGES } from "./pages";
import ConnectionPage from "./pages/ConnectionPage";
import PayablesPage from "./pages/PayablesPage";
import TransactionsPage from "./pages/TransactionsPage";
import BankAccountsPage from "./pages/BankAccountsPage";
import SettingsPage from "./pages/SettingsPage";
import UploadPage from "./pages/UploadPage";
import FabModal from "./components/FabModal";

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
    <ThemeProvider>
      <div className="flex min-h-screen bg-gray-50 dark:bg-slate-950">
        <FinanceProvider month={selectedMonth} year={selectedYear}>
          <Sidebar activePage={activePage} onNavigate={setActivePage} />

          <main className="flex-1 overflow-x-hidden md:ml-60">
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
            {activePage === PAGES.banks && (
              <BankAccountsPage onNavigateUpload={() => setActivePage("upload")} />
            )}
            {activePage === PAGES.settings && <SettingsPage />}
            {activePage === "upload" && (
              <UploadPage onNavigate={setActivePage} />
            )}
          </main>

          <FabModal />
        </FinanceProvider>
      </div>
    </ThemeProvider>
  );
}
