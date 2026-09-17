import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useOutletContext } from "react-router";

import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider } from "./context/AuthContext";
import ProtectedLayout from "./components/ProtectedLayout";
import PageLoader from "./components/PageLoader";
import RouteErrorBoundary from "./components/RouteErrorBoundary";

// Lazy: cada página só baixa quando a rota é visitada — o bundle inicial não
// precisa de todas de uma vez (issue #11, bundle único de 765kB).
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const CategoryDetailPage = lazy(() => import("./pages/CategoryDetailPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const PayablesPage = lazy(() => import("./pages/PayablesPage"));
const TransactionsPage = lazy(() => import("./pages/TransactionsPage"));
const BankAccountsPage = lazy(() => import("./pages/BankAccountsPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));

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
        <RouteErrorBoundary>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              <Route element={<ProtectedLayout />}>
                <Route path="/" element={<DashboardRoute />} />
                <Route path="/categoria/:id" element={<CategoryDetailPage />} />
                <Route path="/payables" element={<PayablesRoute />} />
                <Route path="/transactions" element={<TransactionsRoute />} />
                <Route path="/banks" element={<BankAccountsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </RouteErrorBoundary>
      </AuthProvider>
    </ThemeProvider>
  );
}
