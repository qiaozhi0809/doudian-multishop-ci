import type { ShopRow } from "@/lib/use-shops";
import type { ShopPatch } from "../hooks/use-shop-actions";

/**
 * 店铺手工维护字段的前端校验，与后端 domain/shop_profile_rules.py 同一套规则与文案：
 * 店铺ID 1–20 位数字、卡号尾号 4 位数字、开户行不超过 50 个字。数字只认半角 0-9。空值不校验（选填）。
 */
export const BANK_NAME_MAX = 50;

export function platformShopIdError(value: string): string | undefined {
  return value && !/^[0-9]{1,20}$/.test(value) ? "店铺ID是 1 到 20 位数字" : undefined;
}

export function bankTailError(value: string): string | undefined {
  return value && !/^[0-9]{4}$/.test(value) ? "卡号尾号是 4 位数字" : undefined;
}

export function bankNameError(value: string): string | undefined {
  return value.length > BANK_NAME_MAX ? `开户行不超过 ${BANK_NAME_MAX} 个字` : undefined;
}

export interface ShopFormValues {
  name: string;
  entity: string;
  platformShopId: string;
  bankName: string;
  bankTail: string;
}

/**
 * 编辑店铺只发有改动的字段（与代理池编辑的 buildPatch 同一做法）：校验上线前手填的不合规旧值，
 * 只要这次没改就不发送，不会挡住只改店铺名的保存。清空 = null。
 */
export function buildShopPatch(shop: ShopRow, values: ShopFormValues): ShopPatch {
  const patch: ShopPatch = {};
  const name = values.name.trim();
  if (name !== shop.name) patch.name = name;
  const pairs: [keyof ShopPatch, string, string | null][] = [
    ["entity", values.entity, shop.entity],
    ["platform_shop_id", values.platformShopId, shop.platform_shop_id],
    ["bank_name", values.bankName, shop.bank_name],
    ["bank_tail", values.bankTail, shop.bank_tail],
  ];
  for (const [key, raw, old] of pairs) {
    const next = raw.trim();
    if (next !== (old ?? "").trim()) (patch as Record<string, string | null>)[key] = next || null;
  }
  return patch;
}

/** 只校验改动过的字段（不合规的旧值不改就不报错）。 */
export function shopFieldErrors(shop: ShopRow, values: ShopFormValues) {
  const changed = (raw: string, old: string | null) => raw.trim() !== (old ?? "").trim();
  return {
    name: values.name.trim() ? undefined : "请输入店铺名称",
    id: changed(values.platformShopId, shop.platform_shop_id) ? platformShopIdError(values.platformShopId.trim()) : undefined,
    bankName: changed(values.bankName, shop.bank_name) ? bankNameError(values.bankName.trim()) : undefined,
    tail: changed(values.bankTail, shop.bank_tail) ? bankTailError(values.bankTail.trim()) : undefined,
  };
}
