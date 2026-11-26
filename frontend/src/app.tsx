import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "@/components/custom/app-shell";
import AftersalePage from "@/pages/aftersale";
import AuthPage from "@/pages/auth";
import { useUnauthorizedRedirect } from "@/pages/auth/hooks/use-unauthorized-redirect";
import { RequireAuth } from "@/pages/auth/require-auth";
import CatalogPage from "@/pages/catalog";
import DashboardPage from "@/pages/dashboard";
import FundPage from "@/pages/fund";
import LabelingPage from "@/pages/labeling";
import MessagePage from "@/pages/message";
import OrderPage from "@/pages/order";
import ProxyPoolPage from "@/pages/proxy-pool";
import ReconcilePage from "@/pages/reconcile";
import ShopPage from "@/pages/shop";
import StockPage from "@/pages/stock";

const createQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });

/** 发货台已并入「打单发货」：旧地址跳到它的「待发货」阶段，店铺范围等参数照带。 */
function ShippingRedirect() {
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  params.set("stage", "labeled");
  params.delete("page");
  return <Navigate to={`/labeling?${params.toString()}`} replace />;
}

function AppRoutes() {
  useUnauthorizedRedirect();
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/setup" element={<AuthPage mode="setup" />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/orders" element={<OrderPage />} />
          <Route path="/labeling" element={<LabelingPage />} />
          <Route path="/shipping" element={<ShippingRedirect />} />
          <Route path="/reconcile" element={<ReconcilePage />} />
          <Route path="/aftersale" element={<AftersalePage />} />
          <Route path="/messages" element={<MessagePage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/stock" element={<StockPage />} />
          <Route path="/fund" element={<FundPage />} />
          <Route path="/shops" element={<ShopPage />} />
          <Route path="/proxy-pool" element={<ProxyPoolPage />} />
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
