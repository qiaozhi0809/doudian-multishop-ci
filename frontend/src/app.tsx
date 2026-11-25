import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/custom/app-shell";
import AftersalePage from "@/pages/aftersale";
import AuthPage from "@/pages/auth";
import { useUnauthorizedRedirect } from "@/pages/auth/hooks/use-unauthorized-redirect";
import { RequireAuth } from "@/pages/auth/require-auth";
import CatalogPage from "@/pages/catalog";
import FundPage from "@/pages/fund";
import LabelingPage from "@/pages/labeling";
import OrderPage from "@/pages/order";
import ReconcilePage from "@/pages/reconcile";
import ShippingPage from "@/pages/shipping";
import ShopPage from "@/pages/shop";
import StockPage from "@/pages/stock";

const createQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });

function AppRoutes() {
  useUnauthorizedRedirect();
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/setup" element={<AuthPage mode="setup" />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/orders" replace />} />
          <Route path="/orders" element={<OrderPage />} />
          <Route path="/labeling" element={<LabelingPage />} />
          <Route path="/shipping" element={<ShippingPage />} />
          <Route path="/reconcile" element={<ReconcilePage />} />
          <Route path="/aftersale" element={<AftersalePage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/stock" element={<StockPage />} />
          <Route path="/fund" element={<FundPage />} />
          <Route path="/shops" element={<ShopPage />} />
        </Route>
      </Route>
    </Routes>
  );
}

export function App() {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <AppRoutes />
    </QueryClientProvider>
  );
}
