import { act, renderHook } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useShopFilter } from "./use-shop-filter";

function setup(path: string) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
  return renderHook(() => ({ filter: useShopFilter(), location: useLocation() }), { wrapper });
}

describe("useShopFilter", () => {
  it("从 URL 读取店铺筛选", () => {
    const { result } = setup("/orders?shops=1,2");
    expect(result.current.filter.shopIds).toEqual([1, 2]);
  });
  it("没有参数时为空（全部）", () => {
    expect(setup("/orders").result.current.filter.shopIds).toEqual([]);
  });
  it("设置筛选写回 URL，并保留其他参数", () => {
    const { result } = setup("/orders?status=shipped");
    act(() => result.current.filter.setShopIds([3, 1]));
    expect(result.current.location.search).toBe("?status=shipped&shops=1%2C3");
    expect(result.current.filter.shopIds).toEqual([1, 3]);
  });
  it("清空筛选时删除参数", () => {
    const { result } = setup("/orders?shops=1");
    act(() => result.current.filter.setShopIds([]));
    expect(result.current.location.search).toBe("");
  });
  it("切换筛选回到第 1 页（删除 page）", () => {
    const { result } = setup("/orders?shops=1&page=4");
    act(() => result.current.filter.setShopIds([2]));
    expect(result.current.location.search).toBe("?shops=2");
  });
});
