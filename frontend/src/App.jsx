import { Navigate, Route, Routes, useOutletContext } from "react-router";

import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider } from "./context/AuthContext";
import ProtectedLayout from "./components/ProtectedLayout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import PayablesPage from "./pages/PayablesPage";
import TransactionsPage from "./pages/TransactionsPage";
import BankAccountsPage from "./pages/BankAccountsPage";
import SettingsPage from "./pages/SettingsPage";

function DashboardRoute() {
  const { month, year, onMonthChange } = useOutletContext();
  return <DashboardPage month={month} year={year} onMonthChange={onMonthChange} />;
}

function PayablesRoute() {
  const { month, year, onMonthChange, payablesFilter, onPayablesFilterChange } =
    useOutletContext();
  return (
    <PayablesPage
      filter={payablesFilter}
      onFilterChange={onPayablesFilterChange}
      month={month}
      year={year}
      onMonthChange={onMonthChange}
    />
  );
}

function TransactionsRoute() {
  const { month, year, onMonthChange } = useOutletContext();
  return <TransactionsPage month={month} year={year} onMonthChange={onMonthChange} />;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<DashboardRoute />} />
            <Route path="/payables" element={<PayablesRoute />} />
            <Route path="/transactions" element={<TransactionsRoute />} />
            <Route path="/banks" element={<BankAccountsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  );
}
