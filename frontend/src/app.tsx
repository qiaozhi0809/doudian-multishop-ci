import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/custom/app-shell";
import AuthPage from "@/pages/auth";
import { useUnauthorizedRedirect } from "@/pages/auth/hooks/use-unauthorized-redirect";
import { RequireAuth } from "@/pages/auth/require-auth";
import LabelingPage from "@/pages/labeling";
import OrderPage from "@/pages/order";
import ShopPage from "@/pages/shop";

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
