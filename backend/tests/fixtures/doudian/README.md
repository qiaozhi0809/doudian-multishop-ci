# 抖店接口脱敏样本

2026-11-25 在内置浏览器中登录**测试店**后，于页面内直接请求抓取（浏览器外无签名同样可调，见 `docs/api/read.md`）。

## 脱敏规则

- 姓名 → `测试` / `测*`；手机号 → `138****0000`；详细地址 → `<详细地址>`；昵称 → `测*`；`user_id` → `user_placeholder`
- 订单号 → `6900000000000000001`；售后单号 → `140000000000000001`
- 面单账户的月结 / 网点账号（`partnerId`、`monthlyAccountOrNetCode`）→ `ACCOUNT_PLACEHOLDER`，`subscribeAddress` → `<详细地址>`
- 订单样本裁剪掉解析用不到的展示字段（`action_map`、`order_status_info`、`tags` 等）；数组最多保留 3 条
- 省市区街道名称与 ID、商品 ID、面单账户 `eBillId`、模板 code 保留（不是个人信息，解析测试需要）

## 文件

| 文件 | 请求 | 说明 |
|---|---|---|
| `tabcnt.json` | `GET /api/order/tabcnt?tabcnt_version=v1&tab=all` | 状态计数 |
| `searchlist.json` | `GET /api/order/searchlist?tab=all&page=0&pageSize=10&order=desc&order_by=create_time` | 1 单，`order_status=4`（已关闭）、`sku_id=0`、有退款售后 |
| `searchlist_by_order_id.json` | 同上加 `order_status=&order_id=<单号>` | 按单号补查 |
| `searchlist_stock_up.json` | `tab=stock_up&order_status=stock_up&scene=1` | 1 单待发货：`order_status=2`、`sku_id=0` 且 `sku_id_str` 为空、无 `combine_id`、商品规格两项 |
| `searchlist_stock_up_empty.json` | 同上 | 待发货为空 |
| `address_list.json` | `GET /shopuser/tshopuser/getAfterSaleList?page=1&keyword=&pageSize=500&sort=2&source=send_deliver` | 1 个默认发货地址（`is_send_default=1`） |
| `template_list.json` | `GET /shopuser/power/searchTemplates` | 按快递分组：`parentTempList` / `customTempList` / `publicTempList` |
| `express_list.json` | `POST /api/order/expressList`（请求体 `{}`，公共参数在 URL） | `data.eBills[]`，快递编码字段为 `company` |
| `ebill_accounts.json` | `GET /shopuser/power/getEbillAccountListByExpress?company=jd` | 京东月结账户：`monthlyAccountOrNetCode`、`balance=-1` |

所有请求的 `_bid` 均为 `ffa_order`。

## 尚未覆盖（需有订单的店铺补抓）

- 已发货订单（`order_status=3`）、一单多商品
- 取号所需的 `combine_id` 与实际 `sku_id`：订单列表（含打单发货页的列表请求）都不返回，需在打单弹窗打开时抓取（gaps API-04）
- 网点型快递（如中通）的面单账户：字段是否为 `netCode` / `netName`，`balance` 是否为张数
- 多个发货地址、非默认地址
