import type { KpiTone } from "@/lib/kpi-tone";

/** 登录页右侧内容区的静态文案。功能分组与名称和侧栏（app-shell/logic/nav-items.ts）一致。 */

export const ASIDE_HEADLINE = "抖店多店铺统一运营后台";
export const ASIDE_LEAD = "订单、售后、商品与资金集中管理，跨店批量打单发货";

export interface PreviewTile {
  name: string;
  value: string;
  tone: KpiTone;
}

/** 「经营概览」示意，数字为样例。 */
export const PREVIEW_TILES: PreviewTile[] = [
  { name: "待发货", value: "128", tone: "info" },
  { name: "售后待办", value: "6", tone: "violet" },
  { name: "在营店铺", value: "8", tone: "success" },
  { name: "待结算", value: "¥23,560", tone: "neutral" },
];

export interface FeatureGroup {
  name: string;
  items: { name: string; text: string }[];
}

export const FEATURE_GROUPS: FeatureGroup[] = [
  {
    name: "订单",
    items: [
      { name: "全部订单", text: "跨店订单统一查询，按状态快速筛选" },
      { name: "打单发货", text: "批量取号、打印面单与确认发货" },
      { name: "售后处理", text: "售后待办按处理时限排序跟进" },
      { name: "发货异常", text: "比对本地与平台的发货及运单状态" },
    ],
  },
  {
    name: "商品",
    items: [
      { name: "商品列表", text: "跨店商品汇总，按状态与分组筛选" },
      { name: "库存", text: "多仓库存、售罄与库存预警" },
    ],
  },
  {
    name: "资金",
    items: [{ name: "结算与保证金", text: "待结算订单、保证金与账单明细" }],
  },
  {
    name: "设置",
    items: [
      { name: "店铺管理", text: "店铺接入、独立出口配置与扫码授权" },
      { name: "代理池", text: "代理批量导入与出口 IP 检测" },
    ],
  },
];

export const START_STEPS = [
  { name: "接入店铺", text: "添加店铺并配置独立出口，出口检测通过后方可授权" },
  { name: "扫码授权", text: "使用抖店 App 扫码登录，会话失效时实时提醒" },
  { name: "同步与履约", text: "同步订单后批量取号、打印面单并发货" },
];
