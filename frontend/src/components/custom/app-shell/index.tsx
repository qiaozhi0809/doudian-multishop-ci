import { Outlet, useLocation } from "react-router-dom";
import { NoticeProvider } from "@/components/custom/notice/notice";
import { NotificationBanner, NotificationBell, NotificationCenterProvider } from "@/components/custom/notification-center";
import { useEvents } from "@/lib/use-events";
import { useShops } from "@/lib/use-shops";
import { useSystemInfo } from "@/lib/use-system-info";
import { useAuth } from "@/pages/auth/hooks/use-auth";
import { AdminMenu } from "./components/admin-menu";
import { ChangePasswordDialog } from "./components/change-password-dialog";
import { DryRunBanner } from "./components/dry-run-banner";
import { HealthIndicator } from "./components/health-indicator";
import { ShopFilterSelect } from "./components/shop-filter-select";
import { SideNav } from "./components/side-nav";
import { PageHead } from "./components/page-head";
import { useChangePassword } from "./hooks/use-change-password";
import { usePrefetchMetrics } from "./hooks/use-prefetch-metrics";
import { useQuickLogin } from "./hooks/use-quick-login";
import { useShopFilter } from "./hooks/use-shop-filter";
import { listAttention, summarizeHealth } from "./logic/health-summary";
import { pageTitle } from "./logic/nav-items";
import styles from "./app-shell.module.css";

/** 后台外壳：浮动侧栏（左下角个人中心）+ 内容区（强提醒横条 + 页面标题行与铃铛 + `<Outlet />`）。 */
export function AppShell() {
  useEvents();
  const { pathname } = useLocation();
  const { shopIds, setShopIds } = useShopFilter();
  const shopsQuery = useShops();
  const shops = shopsQuery.data ?? [];
  const auth = useAuth();
  const login = useQuickLogin();
  const password = useChangePassword();
  const system = useSystemInfo();
  usePrefetchMetrics(shopIds, (shopsQuery.data ?? []).length > 0);

  const healthState = shopsQuery.isError ? "error" : shopsQuery.isLoading ? "loading" : "ready";
  return (
    <NoticeProvider>
    <NotificationCenterProvider>
    <div className={styles.shell}>
      <SideNav
        shopIds={shopIds}
        scope={<ShopFilterSelect shops={shops} shopIds={shopIds} disabled={healthState !== "ready"} onChange={setShopIds} />}
        account={<AdminMenu username={auth.status?.username ?? "管理员"} onChangePassword={() => password.setOpen(true)} onLogout={() => void auth.logout()} />}
      />
      <main className={styles.main}>
        <div className={styles.page}>
          <NotificationBanner />
          {system.dryRun && <DryRunBanner active />}
          <PageHead
            title={pageTitle(pathname)}
            health={
              <HealthIndicator
                state={healthState}
                summary={summarizeHealth(shops)}
                attention={listAttention(shops)}
                onRetry={() => void shopsQuery.refetch()}
                login={{ pendingIds: login.pendingIds, waitingIds: login.waitingIds, errors: login.errors, onLogin: (id) => void login.login(id) }}
              />
            }
            bell={<NotificationBell />}
          />
          <Outlet />
        </div>
      </main>
      <ChangePasswordDialog
        open={password.open}
        onOpenChange={password.setOpen}
        onSubmit={password.submit}
        pending={password.pending}
        error={password.error}
        succeeded={password.succeeded}
      />
    </div>
    </NotificationCenterProvider>
    </NoticeProvider>
  );
}
