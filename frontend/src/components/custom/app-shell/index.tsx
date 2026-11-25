import { Outlet, useLocation } from "react-router-dom";
import { TaskCenter } from "@/components/custom/task-center";
import { useEvents } from "@/lib/use-events";
import { useShops } from "@/lib/use-shops";
import { useAuth } from "@/pages/auth/hooks/use-auth";
import { AdminMenu } from "./components/admin-menu";
import { ChangePasswordDialog } from "./components/change-password-dialog";
import { HealthIndicator } from "./components/health-indicator";
import { ShopFilterSelect } from "./components/shop-filter-select";
import { SideNav } from "./components/side-nav";
import { TopBar } from "./components/top-bar";
import { useChangePassword } from "./hooks/use-change-password";
import { useNavGroups } from "./hooks/use-nav-groups";
import { useQuickLogin } from "./hooks/use-quick-login";
import { useShopFilter } from "./hooks/use-shop-filter";
import { useSideNavCollapsed } from "./hooks/use-side-nav-collapsed";
import { listAttention, summarizeHealth } from "./logic/health-summary";
import { pageTitle } from "./logic/nav-items";
import styles from "./app-shell.module.css";

/** 后台外壳：侧边栏 + 顶栏 + 内容区（`<Outlet />`）。 */
export function AppShell() {
  useEvents();
  const { pathname } = useLocation();
  const { shopIds, setShopIds } = useShopFilter();
  const shopsQuery = useShops();
  const shops = shopsQuery.data ?? [];
  const auth = useAuth();
  const nav = useSideNavCollapsed();
  const groups = useNavGroups();
  const login = useQuickLogin();
  const password = useChangePassword();

  const healthState = shopsQuery.isError ? "error" : shopsQuery.isLoading ? "loading" : "ready";
  return (
    <div className={styles.shell}>
      <SideNav
        collapsed={nav.collapsed}
        onToggle={nav.toggle}
        shopIds={shopIds}
        collapsedGroups={groups.collapsedGroups}
        onToggleGroup={groups.toggleGroup}
      />
      <div className={styles.main}>
        <TopBar
          title={pageTitle(pathname)}
          filter={<ShopFilterSelect shops={shops} shopIds={shopIds} disabled={healthState !== "ready"} onChange={setShopIds} />}
          tasks={<TaskCenter />}
          health={
            <HealthIndicator
              state={healthState}
              summary={summarizeHealth(shops)}
              attention={listAttention(shops)}
              onRetry={() => void shopsQuery.refetch()}
              login={{ pendingIds: login.pendingIds, waitingIds: login.waitingIds, errors: login.errors, onLogin: (id) => void login.login(id) }}
            />
          }
          admin={<AdminMenu username={auth.status?.username ?? "管理员"} onChangePassword={() => password.setOpen(true)} onLogout={() => void auth.logout()} />}
        />
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
      <ChangePasswordDialog
        open={password.open}
        onOpenChange={password.setOpen}
        onSubmit={password.submit}
        pending={password.pending}
        error={password.error}
        succeeded={password.succeeded}
      />
    </div>
  );
}
