import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HIDE_AFTER_MS, installScrollReveal } from "./scroll-reveal";

describe("滚动时才显示滚动条", () => {
  let uninstall: () => void;
  beforeEach(() => {
    vi.useFakeTimers();
    uninstall = installScrollReveal();
  });
  afterEach(() => {
    uninstall();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("滚动的元素加 data-scrolling，停下后去掉", () => {
    const box = document.createElement("div");
    document.body.append(box);
    box.dispatchEvent(new Event("scroll"));
    expect(box.hasAttribute("data-scrolling")).toBe(true);
    vi.advanceTimersByTime(HIDE_AFTER_MS);
    expect(box.hasAttribute("data-scrolling")).toBe(false);
  });

  it("一直在滚就一直显示，最后一次滚动后才计时", () => {
    const box = document.createElement("div");
    document.body.append(box);
    box.dispatchEvent(new Event("scroll"));
    vi.advanceTimersByTime(HIDE_AFTER_MS - 100);
    box.dispatchEvent(new Event("scroll"));
    vi.advanceTimersByTime(HIDE_AFTER_MS - 100);
    expect(box.hasAttribute("data-scrolling")).toBe(true);
    vi.advanceTimersByTime(100);
    expect(box.hasAttribute("data-scrolling")).toBe(false);
  });

  it("整页滚动标在根元素上；只标正在滚的那一处", () => {
    const other = document.createElement("div");
    document.body.append(other);
    document.dispatchEvent(new Event("scroll"));
    expect(document.documentElement.hasAttribute("data-scrolling")).toBe(true);
    expect(other.hasAttribute("data-scrolling")).toBe(false);
  });

  it("卸载后不再标记", () => {
    uninstall();
    const box = document.createElement("div");
    document.body.append(box);
    box.dispatchEvent(new Event("scroll"));
    expect(box.hasAttribute("data-scrolling")).toBe(false);
    uninstall = () => {};
  });
});
