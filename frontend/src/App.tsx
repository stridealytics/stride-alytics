import { Suspense, lazy, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster as HotToaster } from "react-hot-toast";

import { AppLayout } from "./components/layout";
import { useAuthStore } from "./store";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";

// Every other page is loaded on demand so the first paint ships only the login + layout code
// (Recharts and the heavy pages download when first visited).
const page = (load: () => Promise<Record<string, unknown>>, name: string) =>
  lazy(async () => ({ default: (await load())[name] as React.ComponentType }));

const ActiveHoldingsPage = page(() => import("./pages/ActiveHoldingsPage"), "ActiveHoldingsPage");
const ActiveTradesPage = page(() => import("./pages/ActiveTradesPage"), "ActiveTradesPage");
const DashboardPage = page(() => import("./pages/DashboardPage"), "DashboardPage");
const ExitAlertsPage = page(() => import("./pages/ExitAlertsPage"), "ExitAlertsPage");
const GreeksPage = page(() => import("./pages/GreeksPage"), "GreeksPage");
const HeatDashboardPage = page(() => import("./pages/HeatDashboardPage"), "HeatDashboardPage");
const OptionChainPage = page(() => import("./pages/OptionChainPage"), "OptionChainPage");
const PicksPage = page(() => import("./pages/PicksPage"), "PicksPage");
const PortfolioPage = page(() => import("./pages/PortfolioPage"), "PortfolioPage");
const RegimePage = page(() => import("./pages/RegimePage"), "RegimePage");
const ScenariosPage = page(() => import("./pages/ScenariosPage"), "ScenariosPage");
const ScreenerPage = page(() => import("./pages/ScreenerPage"), "ScreenerPage");
const SettingsPage = page(() => import("./pages/SettingsPage"), "SettingsPage");
const SignalLogPage = page(() => import("./pages/SignalLogPage"), "SignalLogPage");
const SizingPage = page(() => import("./pages/SizingPage"), "SizingPage");
const StrategyMatrixPage = page(() => import("./pages/StrategyMatrixPage"), "StrategyMatrixPage");
const WatchlistPage = page(() => import("./pages/WatchlistPage"), "WatchlistPage");

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AuthBootstrap({ children }: { children: React.ReactNode }) {
  const hydrate = useAuthStore((s) => s.hydrate);
  const devAdminLogin = useAuthStore((s) => s.devAdminLogin);
  const devAuthBypass = import.meta.env.DEV && import.meta.env.VITE_DEV_AUTH_BYPASS === "true";
  const [ready, setReady] = useState(!devAuthBypass);

  useEffect(() => {
    if (devAuthBypass) {
      devAdminLogin();
      setReady(true);
      return;
    }
    hydrate();
  }, [devAdminLogin, devAuthBypass, hydrate]);

  if (!ready) return <div className="p-6 text-sm text-gray-500">Loading…</div>;
  return <>{children}</>;
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token);
  const location = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: location }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthBootstrap>
          <HotToaster position="top-right" />
          <Suspense fallback={<div className="p-6 text-sm text-gray-500">Loading…</div>}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />

            <Route
              element={
                <RequireAuth>
                  <AppLayout />
                </RequireAuth>
              }
            >
              <Route index element={<DashboardPage />} />
              <Route path="screener" element={<ScreenerPage />} />
              <Route path="greeks" element={<GreeksPage />} />
              <Route path="regime" element={<RegimePage />} />
              <Route path="picks" element={<PicksPage />} />
              <Route path="portfolio" element={<PortfolioPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="exit-alerts" element={<ExitAlertsPage />} />
              <Route path="active-holdings" element={<ActiveHoldingsPage />} />
              <Route path="strategy-matrix" element={<StrategyMatrixPage />} />
              <Route path="watchlist" element={<WatchlistPage />} />
              <Route path="option-chain" element={<OptionChainPage />} />
              <Route path="active-trades" element={<ActiveTradesPage />} />
              <Route path="sizing" element={<SizingPage />} />
              <Route path="scenarios" element={<ScenariosPage />} />
              <Route path="heat-dashboard" element={<HeatDashboardPage />} />
              <Route path="signal-log" element={<SignalLogPage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </Suspense>
        </AuthBootstrap>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
