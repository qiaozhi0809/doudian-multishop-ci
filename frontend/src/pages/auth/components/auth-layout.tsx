import type { ReactNode } from "react";

/** 登录、初始化与加载 / 出错状态共用的居中版式。 */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-[var(--space-6)] p-[var(--space-6)]">
      <h1 style={{ fontSize: "var(--text-xl)" }}>抖店多店铺管理</h1>
      <div className="w-full max-w-[24rem]">{children}</div>
    </main>
  );
}
