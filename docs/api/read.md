# 只读接口

> 原 `architecture.md` 附录 A.1。公共参数见 [flows.md](../design/flows.md) 7.1，签名判断见 [README.md](README.md)。
> 订单 / 商品 / 售后 / 资金页面的字段级映射见同目录各附录。

### A.1 只读接口

| 用途 | 方法 | 路径 | 备注 |
|---|---|---|---|
| 待发货订单 | GET | `/api/order/searchlist?tab=stock_up&order_status=stock_up&scene=1` | page **0-based**；pageSize 上限 200。**响应（2026-11-25 样本）**：`data` 为订单数组，`total` 在顶层；时间字段为 unix 秒；金额整数分；`product_item[].item_order_id` 即子订单 ID；`sku_id` 可能为 `0`。按单号补查：`tab=all&order_status=&order_id=<单号>`。样本见 `backend/tests/fixtures/doudian/` |
| 打单台列表 | GET | `/api/order/searchCombineOrder` | ⏳ 返回结构未记录；可能是取号字段 `combine_id` / 实际 `sku_id` 的来源（gaps API-04） |
| 订单明细（取号前） | GET | `/api/order/orderListInfo` | ⏳ 页面取号前会调用（A.2.2 前置链路）；参数、返回、签名状态均未记录（gaps API-04） |
| 状态计数（会话探测） | GET | `/api/order/tabcnt` | **未登录返回 `code:10008`**，推荐作健康探测 |
| 快递公司 | **POST** | `/api/order/expressList` | GET 返回 `404 路由错误`。**请求体 `{}`，公共参数（appid / __token / _bid / aid / _lid）在 URL 查询串**。响应 `data.eBills[]`（快递编码字段为 `company`、名称 `name`）与 `data.favourites[]` |
| 发货地址列表 | GET | `/shopuser/tshopuser/getAfterSaleList?page=1&keyword=&pageSize=500&sort=2&source=send_deliver` | page **1-based**。响应 `data.address_list[]`（另有 `data.default_address[]`）：`id`、`user_name`、`mobile`、`province_id/name`…`street_id/name`、`detail`、`is_send_default=1` 为默认发货地址、`address_error`（地址异常提示） |
| 面单模板列表 | GET | `/shopuser/power/searchTemplates` | 响应 `data.list[]` **按快递分组**：`companyCode`、`parentTempList[]`（标准模板 `parentTempCode`）、`customTempList[]`（自定义模板 `customTempCode`，取号用它）、`publicTempList[]` |
| 面单账户列表 | GET | `/shopuser/power/getEbillAccountListByExpress?company=<快递编码>` | 响应 `data.accounts[]`。**京东月结样本（2026-11-25）**：`eBillId`（数字）、`monthlyAccountOrNetCode`（月结账号或网点编码，取号的 `net_code` 取此值）、`accountType`、`settleType`、`balance`（`-1` = 月结不计张数）、`isDefault`、`partnerId`、`subscribeAddress`。网点型快递（如中通）是否另有 `netCode` / `netName` 待补抓；取号必需的 `net_code` / `ebill_id` 来源见 backend 5.9 |
| 取号前置检查 | GET | `/api/order/getAftersaleAddressAndLogisticsTemplate` | 返回 4 个布尔位 |
| 增值服务与产品类型 | POST | `/api/order/query_added_services_and_product_types` | 只读（虽为 POST）。`logistics_product[].selectedValue` 即取号 `transport.expType`，详见 [write.md](write.md) A.2.7 |
| 包裹列表 | GET | `/api/order/searchPackageList` | ⚠️ **需签名**：无签名直连返回风控错误 `10001010A`（2026-11-25） |
| 包裹配置 | GET | `/api/order/getPackageConfig` | |
| 合单灰度 | GET | `/api/order/queryCombineOrderGrayShopStatus` | |
| 公告 | GET | `/api/order/getNotice` | |
| 收货信息解密 | GET | `/api/order/receiveinfo` | 参数名 `order_id`，**值传 `shop_order_id`**。响应 `data.receive_info`：`post_receiver` / `post_tel`（可能带分机号，形如 `-xxxx`）/ `post_addr.{province,city,town,street}.{name,id}` + `detail` / `can_view` / `expire_time`。`data.verify_type` 非空表示要验证。**配额制**：每日有解密额度（官方页面可见，样本店剩 8 次）；**连续约 13 次（间隔 0.5-0.8s）触发 `602502151`，3 小时恢复**（2026-11-25）。实现约束见 [flows.md](../design/flows.md) 7.3 |
| 包裹发货信息 | GET | `/api/order/get_manual_send_order_info?shop_order_no=<shop_order_id>&action=resend&version=1` | **改物流 `deliverId` 的来源**。响应 `data.order_info.package_list[]`：`deliver_id` / `track_no` / `company` / `company_name` / `can_re_send` / `no_re_send_reason` / `can_re_deliver` / `product_info[]` |
| 订单物流 | GET | `/api/order/getOrderLogistics?order_id=<shop_order_id>` | 返回 `logistics[]`：`logistics_name` / **`logistics_code`（运单号）** / `logistics_send_time` / `send_type` / `send_method_name` / `items[]` / `trace[]`（轨迹）；`data` 另有 `logistics_list[]`（按包裹分组）。**API-19 取号恢复的关键接口**；无 `deliverId` |
| 订单详情 | GET | `/api/order/orderDetail?order_id=<shop_order_id>&source=shop_order_view_upgrade` | 返回 `order_base` / `receiver` / `delivery` / `product` / `action_map` / `url_map` 等；**不含运单号**（`delivery.labels` 只有「送货方式」） |
| 店铺资质画像 | GET | `/center/qualification/shop/info` | 资质 ID / 地址 / 类目 / 审核状态 |
| 店铺管理人 | GET | `/byteshop/shopuser/getAdminV2` | 手机号脱敏 |
| 绑定账号 | GET | `/byteshop/accountbind/getbindlist` | |
| 菜单 | GET | `/byteshop/menu/list/v2` | |
| 登录校验 | GET | `/ecomauth/loginv1/session_check` | ⚠️ **不可用**：无 cookie 也返回 `check_code:0` |

> ⏳ **签名状态未注明（gaps API-20）**：`getOrderLogistics`、`orderDetail`、`get_manual_send_order_info`、
> `query_added_services_and_product_types` 是浏览器内调用还是浏览器外无签名直连验证的，未写明。
> 按 [backend.md](../design/backend.md) 5.3「逐接口验证」规则，需补无签名直连结果。
