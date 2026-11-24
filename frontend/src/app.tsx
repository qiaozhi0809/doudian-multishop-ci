import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";
import OrderPage from "@/pages/order";
import ShopPage from "@/pages/shop";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/" element={<Navigate to="/orders" replace />} />
        <Route path="/orders" element={<OrderPage />} />
        <Route path="/shops" element={<ShopPage />} />
      </Routes>
    </QueryClientProvider>
  );
}
