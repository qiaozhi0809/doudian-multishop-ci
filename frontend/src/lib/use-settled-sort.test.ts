import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useSettledSort } from "./use-list-sort";

describe("useSettledSort", () => {
  it("新排序的数据回来前仍显示上一次的排序，数据回来后再切换", () => {
    const first = { key: "pay_time", direction: "asc" as const };
    const next = { key: "amount_cents", direction: "desc" as const };
    const { result, rerender } = renderHook(({ sort, settled }) => useSettledSort(sort, settled), {
      initialProps: { sort: first as typeof first | typeof next | null, settled: true },
    });
    expect(result.current).toEqual(first);
    rerender({ sort: next, settled: false });
    expect(result.current).toEqual(first);
    rerender({ sort: next, settled: true });
    expect(result.current).toEqual(next);
    rerender({ sort: null, settled: true });
    expect(result.current).toBeNull();
  });
});
