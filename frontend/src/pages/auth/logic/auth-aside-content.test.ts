import { FOOTER_NAV, NAV_SECTIONS } from "@/components/custom/app-shell/logic/nav-items";
import { FEATURE_GROUPS } from "./auth-aside-content";

describe("登录页功能介绍", () => {
  it("分组与名称和侧栏一致", () => {
    const sidebar = [
      ...NAV_SECTIONS.flatMap((s) => (s.kind === "group" ? [{ name: s.label, items: s.items.map((i) => i.label) }] : [])),
      { name: "设置", items: FOOTER_NAV.map((i) => i.label) },
    ];
    expect(FEATURE_GROUPS.map((g) => ({ name: g.name, items: g.items.map((i) => i.name) }))).toEqual(sidebar);
  });
});
