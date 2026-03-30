import { useState } from "react";

import ConnectionPage from "./pages/ConnectionPage";
import PayablesPage from "./pages/PayablesPage";
import UploadPage from "./pages/UploadPage";
import FabModal from "./components/FabModal";
import Navbar from "./components/Navbar";

const PAGES = {
  dashboard: "dashboard",
  payables: "payables",
  upload: "upload",
};

export default function App() {
  const [activePage, setActivePage] = useState(PAGES.dashboard);
  const [refreshKey, setRefreshKey] = useState(0);
  const [payablesFilter, setPayablesFilter] = useState("all");
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());

  const handleRefresh = () => setRefreshKey((prev) => prev + 1);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Navbar activePage={activePage} onNavigate={setActivePage} />
      {activePage === PAGES.dashboard && (
        <ConnectionPage
          refreshKey={refreshKey}
          month={selectedMonth}
          year={selectedYear}
          onMonthChange={(month, year) => {
            setSelectedMonth(month);
            setSelectedYear(year);
          }}
        />
      )}
      {activePage === PAGES.payables && (
        <PayablesPage
          refreshKey={refreshKey}
          filter={payablesFilter}
          onFilterChange={setPayablesFilter}
          month={selectedMonth}
          year={selectedYear}
          onMonthChange={(month, year) => {
            setSelectedMonth(month);
            setSelectedYear(year);
          }}
        />
      )}
      {activePage === PAGES.upload && (
        <UploadPage onNavigate={setActivePage} />
      )}
      <FabModal onCreated={handleRefresh} />
    </div>
  );
}
