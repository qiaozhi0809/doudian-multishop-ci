import { act, renderHook } from "@testing-library/react";
import { useSideNavCollapsed } from "./use-side-nav-collapsed";

afterEach(() => localStorage.clear());

describe("useSideNavCollapsed", () => {
  it("默认展开，切换后记住", () => {
    const first = renderHook(() => useSideNavCollapsed());
    expect(first.result.current.collapsed).toBe(false);
    act(() => first.result.current.toggle());
    expect(first.result.current.collapsed).toBe(true);
    first.unmount();
    expect(renderHook(() => useSideNavCollapsed()).result.current.collapsed).toBe(true);
  });
  it("localStorage 不可用时仍可切换", () => {
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const { result } = renderHook(() => useSideNavCollapsed());
    expect(result.current.collapsed).toBe(false);
    act(() => result.current.toggle());
    expect(result.current.collapsed).toBe(true);
    spy.mockRestore();
  });
});
