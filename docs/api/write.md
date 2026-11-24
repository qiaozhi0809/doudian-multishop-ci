# 写接口

> 原 `architecture.md` 附录 A.2。所有接口均为 `fxg.jinritemai.com` 下的内部接口，公共参数见
> [flows.md](../design/flows.md) 7.1，签名判断见 [README.md](README.md)。

### A.2 写接口

> 批量备注、取号、发货前检查、发货、取号发货一体、面单作废、改物流 7 项已于 2026-11-25 用测试单完成真实调用验证，
> 请求体结构与响应见下方各小节。售后、商品、库存写接口仍待验证。
>
> 未验证接口的必查项：
> 1. 是否强制 `a_bogus` / `msToken` 签名（已验证的 7 个写接口均不强制）
> 2. 完整请求体字段（各字段的枚举/格式）
> 3. 售后写操作是否需要详情接口返回的 `token` 字段
> 4. 风控拦截的表现形式（错误码、是否需要二次验证）
> 5. 幂等性：重复提交是否会产生重复数据

| 用途 | 方法 | 路径 | 状态 |
|---|---|---|---|
| 批量备注 | POST | `/api/order/addremarks` | ✅ **已验证**（见 A.2.1） |
| 取号 | POST | `/api/order/batchFetchTrackingNos` | ✅ **已验证**（运单号 `79209902836406`，见 A.2.2） |
| 发货前检查 | POST | `/api/order/sendcheck` | ✅ **已验证**（见 A.2.3） |
| 发货（打单台） | POST | `/api/order/batchDeliverGoodsByEES` | ✅ **已验证**（见 A.2.4） |
| 发货（订单页） | POST | `/api/order/batchFetchTrackingNosAndDeliverGoods`（同一体接口） | ✅ 已验证；batchsend 不需要（见 A.2.7） |
| 取号+发货一体 | POST | `/api/order/batchFetchTrackingNosAndDeliverGoods` | ✅ **已验证**（见 A.2.5） |
| 改物流（重新发货） | POST | `/order/torder/modifyLogistic` | ✅ **已验证**（见 A.2.8） |
| 售后同意退款 | POST | 未抓（按钮 code `refund_audit`） | ⏳ 待定 |
| 售后代填运单号 | POST | 未抓（按钮 code `fill_logistics`） | ⏳ 待定 |
| 售后延长收货 | POST | 未抓（按钮 code `exchange_logistics_extend`） | ⏳ 待定 |
| 商品创建提交 | POST | 未抓（表单提交，需建测试商品） | ⏳ 待定 |
| 面单作废 | POST | `/api/order/batchCancelTrackingNos` | ✅ **已验证**（见 A.2.6） |
| 库存修改 | POST | 未抓 | ⏳ 待定 |

### A.2.1 批量备注（已验证）

```
POST /api/order/addremarks
Content-Type: application/x-www-form-urlencoded
```

**请求体**（form 格式，非 JSON）：

```
star=0
seller_words=<备注内容，URL 编码>
overwrite=true
order_id=<店铺订单号 shop_order_id>
appid=1&__token=<token>&_bid=ffa_order&aid=4272&_lid=<lid>
```

**响应**：

```json
{"code":0,"data":{"Total":1,"SuccessSize":1,"ErrorSize":0,"ErrorData":[],
                  "BaseResp":{"StatusCode":0,"StatusMessage":"success"}}}
```

**验证结论**：

- 写接口**免签名**（URL 中的 `a_bogus`/`msToken` 省略后依然成功）
- `x-secsdk-csrf-token` 请求头**可省略**（带与不带均返回成功）
- 单笔与批量共用一个接口，`order_id` 传单个订单号

### A.2.2 取号（已验证）

```
POST /api/order/batchFetchTrackingNos
Content-Type: application/json
```

**请求体**（已验证 2026-11-25，成功返回运单号）：

```json
{
  "logistics_company_code": "zhongtong",
  "logistics_template_code": "C1m77ow4c2qrrd",
  "address": {
    "id": 106591750,
    "province_id": 15, "province_name": "内蒙古自治区",
    "city_id": 150500, "city_name": "通辽市",
    "town_id": 150522, "town_name": "科尔沁左翼后旗",
    "street_id": 150522100, "street_name": "甘旗卡镇",
    "detail": "<详细地址>",
    "address": "内蒙古自治区通辽市科尔沁左翼后旗甘旗卡镇<详细地址>",
    "user_name": "<发货人姓名>",
    "mobile": "<发货人手机号>"
  },
  "transport": "{\"expType\":\"defaultProductType\"}",
  "net_code": "47530",
  "ebill_id": "16103369",
  "shop_order_list": [{
    "combine_id": "7711729127787004194",
    "is_cancel_combine": false,
    "shop_order_id": "6919920097284206086",
    "sku_orders": [{
      "sku_order_id": "6919920097284206086",
      "sku_id": "3694815853110274",
      "product_id": "3830193743160541308",
      "product_cnt": 1
    }],
    "is_sub_bundle_item": true
  }],
  "fetch_type": 1,
  "is_davinci": true,
  "order_type": 0,
  "version": 1,
  "printer": "Microsoft Print to PDF",
  "appid": 1, "__token": "...", "_bid": "ffa_order", "aid": 4272, "_lid": "..."
}
```

**响应**：

```json
{"code":0,"data":{
  "success_list":[{
    "logistics_company_code":"zhongtong",
    "tracking_no":"79209902836406",
    "logistics_template_code":"C1m77ow4c2qrrd",
    "logistics_company_name":"中通快递(常用)",
    "shop_order_list":[...],
    "print_data":"AVmQFscLF8HVP1Bv7oGhSyz...",
    "sign":"Ybh0fKUi..."
  }],
  "fail_orders_list":[]
}}
```

**关键发现**：

1. **`logistics_template_code` 传自定义模板 code**（`C1m77ow4c2qrrd`），
   不是标准模板 `zt_76_130_v2` —— 之前接口结构分析无法确定，现在已确认
2. **`net_code`（网点编码）和 `ebill_id`（电子面单账户 ID）是必需字段**，
   初期未发现，验证才暴露。来源：`GET /shopuser/power/getEbillAccountListByExpress?company=<快递>`
   （返回每个快递的账户列表，含 `ebill_id`、网点信息）
3. `transport` 是 **JSON 字符串**（不是对象）：`{"expType":"defaultProductType"}`
4. `shop_order_list` 每条需要 `combine_id` + `sku_orders[]`（含 `sku_id`/`product_id`/`product_cnt`）
5. 响应里的 `print_data` + `sign` 是给打印组件用的，协议层可忽略

**第二轮验证补充（2026-11-25，测试单 `6919927348895297368`）**：

6. **`combine_id` 必填**：传空字符串报 `code: 310011`
   「合并ID为空，请刷新页面重试或联系客服解决」。
   实际值来自打单台订单数据（样例 `7711789938665324819`）。
   来源接口待确认 —— `searchPackageList` 直连需签名，无签名返回风控错误（见 API-11）。
   ⏳ **下一步（gaps API-04）**：试 `GET /api/order/searchCombineOrder`（打单台列表，A.1 已收录）
   是否免签名且返回 `combine_id` 与实际 `sku_id`；若也需签名，取号前的订单数据只能走浏览器通道。
7. **`sku_id` 不能取自 `searchlist`**：`searchlist` 的 `product_item.sku_id`
   可能为 `0`，取号必须用实际 SKU ID（样例 `3707788120163074`）。
   实际值从打单台订单数据或订单详情获取。
8. **重复取号被拒绝**：已取号的订单再次取号 →
   `code: 0` + `fail_orders_list: [{ "fail_msg": "不存在可取号商品，请刷新后重试" }]`。
   服务端不会为同一订单返回第二张面单。
   ⏳ **待确认（gaps API-06）**：第二次取号时该订单是否已发货？若已发货，此报错可能源于「已发货」
   而非「已取号」，不能证明「已取号未发货」的订单不能重取。需用「取号后不发货」的订单再测一次。
   本条也决定了取号超时的恢复方式（[backend.md](../design/backend.md) 5.5 / 5.12，gaps API-19）。

**取号前置链路（页面实际调用顺序）**：

> ⏳ `orderListInfo` 未收录、签名状态未知（gaps API-04）；`sendcheck` 在取号前是否必经未验证（gaps API-21）。

```
1. GET  /api/order/orderListInfo                     ← 订单明细
2. GET  /shopuser/power/getEbillAccountListByExpress ← 面单账户与网点（取 ebill_id / net_code）
3. POST /api/order/sendcheck                         ← 发货前检查（含保证金/地址）
4. POST /api/order/batchFetchTrackingNos             ← 取号
5. 本地打印组件 wss://localhost:13999                 ← 打印（协议层可跳过）
```

### A.2.3 发货前检查（已验证）

```
POST /api/order/sendcheck
Content-Type: application/json
```

**请求体**：

```json
{
  "orderIds": ["6919920097284206086"],
  "checkType": 13,
  "address": { 同取号的 address 结构 },
  "appid": 1, "__token": "...", "_bid": "ffa_order", "aid": 4272, "_lid": "..."
}
```

**响应**：`{"code":0,"data":{"total":1,"doubleCheckNum":0,"doubleCheckDetail":[],
"withOutAftersalShopOrders":[],"placeHolder":{...}}}`

- `total` = 通过检查的订单数
- `doubleCheckDetail` 非空表示有二次确认项
- `placeHolder` 含保证金不足等提示的跳转链接

### A.2.4 发货（已验证）

**重要**：打单台的「发货」按钮实际调用的是 `batchDeliverGoodsByEES`，
**不是** M0 笔记里记录的 `/order/torder/batchsend`（订单页「打单发货」也不走它，见 A.2.7）。

```
POST /api/order/batchDeliverGoodsByEES
Content-Type: application/json
```

**请求体**（已验证 2026-11-25，订单已成功变更为「已发货」）：

```json
{
  "send_type": "3",
  "batch_deliver_packages": [{
    "logistics_company_code": "zhongtong",
    "tracking_no": "79209902836406"
  }],
  "appid": 1, "__token": "...", "_bid": "ffa_order", "aid": 4272, "_lid": "..."
}
```

**响应**：

```json
{"code":0,"data":{
  "success_package_list":[{
    "logistics_company_code":"zhongtong",
    "tracking_no":"79209902836406",
    "shop_order_list":[{"shop_order_id":"6919920097284206086","sku_orders":[...]}]
  }],
  "fail_package_list":[]
}}
```

**关键发现**：

1. **`send_type: "3"`（字符串）** —— 设计初稿一直标「待确认」的枚举值，
   电子面单发货场景下就是 `"3"`
2. **按「运单号」发货**，不需要订单 ID 列表 —— 只要 `快递编码 + 运单号`
3. 响应按 **package 维度**返回成功/失败（一个包裹可含多单）
4. 请求体极简，无 `deliverType`/`send_list` 等字段（与 batchsend 的设计不同）
5. **重复发货不阻止**（2026-11-25 实测）：同一运单号再次发货 →
   `code: 0`，`success_package_list` 仍返回成功。
   **服务端不做幂等保护，本地必须按「快递编码 + 运单号」判重。**

**完整发货链路（验证）**：

```
1. POST /api/order/sendcheck                 发货前检查（可选，界面会先调）
2. POST /api/order/batchDeliverGoodsByEES    按运单号发货
```

### A.2.5 取号 + 发货一体（已验证）

打单台「待打单」行的「**打单并发货**」按钮调用：

```
POST /api/order/batchFetchTrackingNosAndDeliverGoods
Content-Type: application/json
```

**请求体**（2026-11-25 实测成功）：

```json
{
  "send_type": "3",
  "fetch_type": 1,
  "logistics_company_code": "zhongtong",
  "logistics_template_code": "C1m77ow4c2qrrd",
  "address": { 同取号 },
  "transport": "{\"expType\":\"defaultProductType\"}",
  "net_code": "47530",
  "ebill_id": "16103369",
  "added_services": [],
  "shop_order_list": [ 同取号 ],
  "is_davinci": true,
  "version": 0,
  "printer": "Microsoft Print to PDF"
}
```

即：**取号字段 + `send_type`（发货枚举）+ `added_services`**。

**响应**（实测）：

```json
{"code":0,"data":{
  "success_deliver_list":[{
    "logistics_company_code":"zhongtong",
    "tracking_no":"79209905665503",
    "shop_order_list":[...],
    "sign":"..."
  }]
}}
```

注意：响应字段是 `success_deliver_list`，与单独发货的 `success_package_list` 不同。

⏳ **待补（gaps API-13）**：

- 失败时的字段名与结构（`fail_*`）未记录
- 响应里是否有 `print_data`：样本只见 `sign`。若一体接口不返回 `print_data`，
  「打单并发货」之后就没有打印数据，需要另找补打途径——直接影响打印方案（[flows.md](../design/flows.md) 第 10 节）

**价值**：一次请求完成「取号 + 发货」，省掉 `batchFetchTrackingNos` +
`batchDeliverGoodsByEES` 两次调用，也避免中间态（已取号未发货）。

**已验证**（2026-11-25，测试单 `6919938455108398936`）：作废旧面单后调用，
返回新运单号并直接发货成功。

### A.2.6 面单作废（已验证）

打单台「已打单」行的「**回收单号**」按钮调用：

```
POST /api/order/batchCancelTrackingNos
Content-Type: application/json
```

**请求体**（2026-11-25 实测成功）：

```json
{
  "cancel_list": [{
    "tracking_no": "79209905279026",
    "logistics_company_code": "zhongtong"
  }],
  "appid": 1, "__token": "...", "_bid": "ffa_order", "aid": 4272, "_lid": "..."
}
```

**响应**：

```json
{"code":0,"data":{
  "success_list":[{"logistics_company_code":"zhongtong","tracking_no":"79209905279026","fail_msg":""}],
  "fail_list":[],
  "fail_msg":""
}}
```

**关键点**：

1. 按「运单号 + 快递编码」作废，与发货接口对称
2. 作废后面单失效，**同一订单可重新取号**（实测：作废 `79209905279026` 后
   重取得到 `79209907035270`）
3. 失败明细在 `fail_list`，整体错误在 `fail_msg`

### A.2.7 订单页「打单发货」的实际链路（已验证）

订单页点「发货」→ 选「打单发货」→「打印并发货」，实际依次调用：

| # | 接口 | 用途 |
|---|---|---|
| 1 | `GET /shopuser/power/getEbillAccountListByExpress?company=<快递>` | 拉面单账户（含网点） |
| 2 | `GET /api/order/is_tracking_no_and_logistics_company_match?shop_order_ids=<单号>&logistics_company=<code>` | 校验运单号与物流公司匹配 |
| 3 | `POST /api/order/query_added_services_and_product_types` | 查询增值服务与产品类型 |
| 4 | `POST /api/order/batchFetchTrackingNosAndDeliverGoods` | **取号 + 发货**（同一体接口） |

**关键结论**：订单页「打单发货」与打单台「打单并发货」调用的是**同一个一体接口**。
`/order/torder/batchsend` 在两条电子面单发货路径上都未出现 → **电子面单场景不需要**，从设计中移除。
订单页「自行寄件发货」（手填运单号）未核查是否走 `batchsend`；本工具只做电子面单，不影响 MVP。

`is_tracking_no_and_logistics_company_match` 是可选校验，自行寄件场景有用。

**第 3 步 `query_added_services_and_product_types`（2026-11-25 实测）**：

```
POST /api/order/query_added_services_and_product_types
Content-Type: application/json

{"logistics_company_code":"zhongtong","shop_order_ids":["<shop_order_id>"],
 "appid":1,"__token":"...","_bid":"ffa_order","aid":4272,"_lid":"..."}
```

响应：

```json
{"code":0,"data":{
  "added_services": [],
  "logistics_product": [{
    "param": "expType", "paramName": "产品类型",
    "values": [
      {"name": "普快", "value": "defaultProductType", "hover_text": "", "code": ""},
      {"name": "中通标快(原尊享)", "value": "SVC-VIP", "hover_text": "", "code": ""},
      {"name": "中通好快(原标快)", "value": "SVC-TIMING-STANDARD", "hover_text": "", "code": ""},
      {"name": "中通飞快(原特快)", "value": "SVC-TIMING-HIGH", "hover_text": "", "code": ""}
    ],
    "selectedValue": "defaultProductType", "isRequire": 0
  }],
  "tips": [], "dynamic_fields": null
}}
```

**关键结论**：

1. **参数**：`logistics_company_code`（快递编码）+ `shop_order_ids`（订单号数组）+ 公共参数
2. **`logistics_product[].selectedValue`** 就是取号/一体接口里
   `transport: {"expType": "<selectedValue>"}` 的取值来源 ——
   默认 `defaultProductType`（普快）
3. `added_services` 是该快递可用的增值服务列表（本例为空），
   一体接口的 `added_services: []` 与之对应
4. `isRequire: 0` 表示该字段非必填
5. `dynamic_fields` 用于特殊服务的动态参数（本例为 null）

### A.2.8 重新发货 / 改物流（已验证）

订单详情页 / 订单列表「已发货」行的「**重新发货**」按钮，
弹窗说明：「已发货的运单号有误或者物流异常时，可以使用重新发货替换原单号」。

```
POST /order/torder/modifyLogistic
Content-Type: application/json
```

**请求体**（2026-11-25 实测成功）：

```json
{
  "sendType": "1",
  "sendAddressIdForSave": 106591750,
  "modifyList": [{
    "orderId": "6919938449191743320",
    "companyCode": "zhongtong",
    "logisticsCode": "79209907035270",
    "deliverId": "147767673767714066",
    "resendProductOrderList": [{
      "product_order_id": "6919938449191743320",
      "serial_nos": { "serial_no_list": [], "status": 1, "status_desc": "未上传", "is_show": true }
    }]
  }],
  "delivery_source_page": "order_detail",
  "appid": 1, "__token": "...", "_bid": "ffa_order", "aid": 4272, "_lid": "..."
}
```

**响应**：

```json
{"code":0,"data":{"failedNum":0,"sendFailList":[],"total":1,"sendFailListV2":[]}}
```

**关键点**：

1. **`deliverId` 是原包裹 ID**，不是订单号，替换前要先查到。
   ✅ **来源已确认（2026-11-25）**：`GET /api/order/get_manual_send_order_info?shop_order_no=<订单号>&action=resend&version=1`
   → `data.order_info.package_list[].deliver_id`（实测值 `147767673767714066`，与 modifyLogistic 请求一致）。
   该包裹对象还给出 `track_no` / `company` / `company_name` / `can_re_send` / `no_re_send_reason`。
   `getOrderLogistics` 与 `orderDetail` 均不含 `deliver_id`，已排除。
2. `companyCode` + `logisticsCode` 是新物流信息
3. `sendType: "1"`（字符串）。⏳ **含义未确认（gaps API-18）**：样本的新单号来自作废后重取
   （A.2.6），疑似「自行寄件」方式；用「打单发货」方式重新发货时取值可能不同，需补枚举
4. `delivery_source_page`：入口页面标识（`order_detail` / 其他）
5. 响应成功看 `failedNum: 0`；失败明细在 `sendFailList`

**弹窗结构**（已验证）：发货地址 / 发货方式（打单发货 / 在线寄件 / 自行寄件）/
选择重发包裹（原单号） / 自行寄件时填新单号 + 物流公司。

> ⏳ **本地状态待设计（gaps DM-10，阶段二）**：已发货订单改物流后，旧面单如何处理（标 `void` 或新增
> `replaced` 状态）、新运单如何入 `waybills`、订单状态是否保持 `shipped`，[data-model.md](../design/data-model.md) 6.1 / 6.2 均未覆盖。
> 不处理的话，每日对账会把它报成 `waybill_mismatch`。
