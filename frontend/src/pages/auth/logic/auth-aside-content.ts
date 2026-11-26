import type { KpiTone } from "@/lib/kpi-tone";

/** 登录页右侧内容区的静态文案。功能分组与名称和侧栏（app-shell/logic/nav-items.ts）一致。 */

export const ASIDE_HEADLINE = "一个人管好多家抖店";
export const ASIDE_LEAD = "多家店的订单、售后、商品和资金放在一处看，打单发货一次做完";

export interface PreviewTile {
  name: string;
  value: string;
  tone: KpiTone;
}

/** 「登录后的概览」示意，数字为样例。 */
export const PREVIEW_TILES: PreviewTile[] = [
  { name: "待发货", value: "128", tone: "info" },
  { name: "售后待办", value: "6", tone: "violet" },
  { name: "在营店铺", value: "8", tone: "success" },
  { name: "待结算", value: "¥23,560.00", tone: "neutral" },
];

export interface FeatureGroup {
  name: string;
  items: { name: string; text: string }[];
}

export const FEATURE_GROUPS: FeatureGroup[] = [
  {
    name: "订单",
    items: [
      { name: "全部订单", text: "各店订单合在一张表，按状态筛选" },
      { name: "打单发货", text: "批量取号、打印面单、确认发货" },
      { name: "售后处理", text: "待办售后按处理截止排序" },
      { name: "发货异常", text: "核对本地与平台的发货和运单" },
    ],
  },
  {
    name: "商品",
    items: [
      { name: "商品列表", text: "各店商品汇总，按状态和分组筛选" },
      { name: "库存", text: "各店库存与仓库，售罄和预警" },
    ],
  },
  {
    name: "资金",
    items: [{ name: "结算与保证金", text: "待结算订单、保证金和账单" }],
  },
  {
    name: "设置",
    items: [
      { name: "店铺管理", text: "添加店铺、设置出口、扫码登录" },
      { name: "代理池", text: "导入代理，检查出口 IP" },
    ],
  },
];

export const START_STEPS = [
  { name: "添加店铺并设置出口", text: "出口检查通过后才能扫码" },
  { name: "扫码登录店铺", text: "登录失效时页面顶部会提醒" },
  { name: "同步订单开始打单", text: "在打单发货里取号、打印、发货" },
];
