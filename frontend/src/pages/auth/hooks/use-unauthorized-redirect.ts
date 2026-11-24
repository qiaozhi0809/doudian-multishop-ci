import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { setUnauthorizedHandler } from "@/lib/api-client";

/** 会话过期：任意业务请求 401 → 清空查询缓存并跳到 /login?next=当前路径，登录后回到原页面。 */
export function useUnauthorizedRedirect(): void {
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const current = useRef(location);
  useEffect(() => {
    current.current = location;
  });

  useEffect(() => {
    setUnauthorizedHandler(() => {
      const { pathname, search } = current.current;
      if (pathname === "/login" || pathname === "/setup") return;
      client.clear();
      navigate(`/login?next=${encodeURIComponent(pathname + search)}`, { replace: true });
    });
    return () => setUnauthorizedHandler(null);
  }, [client, navigate]);
}
