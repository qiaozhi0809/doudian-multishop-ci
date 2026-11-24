## 附录 F：资金看板 UI → 接口映射（2026-11-24 验证）

> 覆盖「账户中心 / 账单管理 / 资金账单」。目标：多店营收与结算概览。
> 说明：样本店为 2026-11-06 新开，**至今 0 条账单**，金额字段名尚无真实样本。

### F.1 资金账单（核心，已调通）

```
POST /bill_center/domestic/shop/query_item
```

**请求体**（已验证）：

```json
{"time_type":"BILL_TIME",
 "start_time":"2026-11-17 00:00:00",
 "end_time":"2026-11-24 23:59:59",
 "page":0,"size":10,
 "query_type":"CHARGE_BILL_ITEM"}
```

- `page` **0-based**
- **成功码是 `code=100000`**（注意不是 0，且验证返回字符串 `"100000"`）
- 响应结构：`{"code":100000,"msg":"success","total":0,"data":[],"extra":{"biz_role":"normal"}}`
- `query_type` 目前只确认 `CHARGE_BILL_ITEM` 一种
- 时间范围放宽到 2025-01-01 仍为 `total=0`，确认是店铺无账单而非参数问题

### F.1b 待结算订单（已调通，样本有 7 条真实数据）

同一个接口，换 `query_type`：

```
POST /bill_center/domestic/shop/query_item
```

**请求体**（已验证）：

```json
{"time_field":"expected_settle_ts",
 "query_type":"SHOP_UNSETTLED_ORDER",
 "order_by":"ecom_order_create_ts","order_type":"desc",
 "product_field":"product_id","order_no_field":"shop_order_no",
 "member_id":"","page":0,"size":10}
```

**响应**（验证 `total=7`）：

```json
{"aggregation_res": {"total_unsettled_amount": "161308"},
 "code": "100000",
 "data": ["<JSON 字符串>", "..."]}
```

- **`data` 每个元素是 JSON 字符串**，需二次解析（不是对象）
- `aggregation_res.total_unsettled_amount` = 待结算总额（**分**），样本 161308 = 1613.08 元
- 单条关键字段：

| 字段 | 含义 | 样本 |
|---|---|---|
| `income_amount` | 收入（分） | 25800 |
| `platform_service_fee` | 平台服务费（分，负数） | -516（2%） |
| `unsettled_amount` | 该单待结算（分） | 25284 |
| `outcome_amount` | 支出合计（分） | -516 |
| `author_commission` / `channel_fee` / `colonel_service_fee` / `dou_customer_commission` | 各项佣金 | 0 |
| `ecom_order_status` | 订单状态文案 | 已发货 |
| `expected_settle_time` | 结算条件文案 | 订单确认收货或核销21天后结算 |
| `settle_period_detail` | 结算周期配置（JSON 字符串） | 含 `delay_day: 21` |
| `product_id` / `product_name` / `sku_detail_text` | 商品 | |
| `shop_order_no` / `sku_order_no` | 订单号 | |
| `collection_subject_name` | 收款主体 | 营业执照名称 |

**这正是「待结算金额」的最佳数据源**，比 `CHARGE_BILL_ITEM` 更实用（后者是已出账账单，新店为空）。

### F.1c 保证金账户（已调通）

```
GET /governance/shop/tpledgecash/payable/info_v2
    ?bizId=62000070001&marginPlatform=fxg_pc&base_margin_platform=fxg_pc&csrf=
```

响应：

```json
{"code":0,"data":{
  "payable":0, "balance":0, "level":"low",
  "withdraw_detail":{"withdrawable_amount":0,"end_time":0,"limit_day":0},
  "risk_detail":{"basic_payable":0,"basic_balance":0,"limit":50000,
                 "is_zero_out":false,"basic_payable_ceiling":0},
  "govern_detail":{"govern_stage":"PayableEnough"}
}}
```

- 上方样本店为**零保证金店铺**（`payable=0, balance=0, govern_stage=PayableEnough`）
- **金额单位：分**（2026-11-25 另一店实测 `risk_detail.basic_balance: 50000` 对应 500 元个体店保证金，
  `balance: 1000`，见 F.4）。⏳ 对照依据待补：50000 = 500 元是与页面显示金额核对所得还是推断（gaps API-15）
- 配套接口：`recharge/info`（充值信息）、`get_identity`（主体身份）、
  `crossborder/country_currency`（跨境币种）、`margin/common/getBankCode`（银行）、
  `getProvince`（省份）

### F.2 账单配置

```
GET /bill_center/domestic/query_bill_config?config_key_list=hosting_service_fee_show
```

- `_bid` 传空字符串即可
- 响应：`data={"hosting_service_fee_show":"hide"}`

### F.3 资金相关页面

| 页面 | 路径 | 状态 |
|---|---|---|
| 账户中心 | `/ffa/fund-control/account-center` | ⚠️ 页面主要加载贷款类接口（`/ffa/ml/pc/v2/cashloan_*`），未发现余额聚合接口 |
| 待结算订单 | `/ffa/fxg-bill/unsettled-order-bill` | ✅ 已探明，见 F.1b（有真实数据） |
| 资金账单 | `/ffa/fxg-bill/fund-detail-bill` | ✅ 已探明，见 F.1（样本店为空） |
| 保证金账户 | `/ffa/content/shop_deposit` | ✅ 已探明，见 F.1c |
| 结算账单 | `/ffa/fxg-bill/settlement-detail-bill` | ❌ 未探明 |
| 资金流水明细 | `/ffa/p-new/intlFundingDetails` | ❌ 未探明（国际版路径） |

### F.4 金额字段说明

| 数据类型 | 金额字段 | 状态 |
|---|---|---|
| 待结算订单（`SHOP_UNSETTLED_ORDER`） | `income_amount` / `platform_service_fee` / `unsettled_amount` / `aggregation_res.total_unsettled_amount` | ✅ **已确认，单位：分** |
| 资金账单（`CHARGE_BILL_ITEM`） | 未知 | ⚠️ 样本为空，字段名待有账单的店铺校准 |
| 保证金（`payable/info_v2`） | `payable` / `balance` / `withdrawable_amount` / `risk_detail.basic_payable` / `risk_detail.basic_balance` | ✅ **单位：分**（实测 `basic_balance: 50000` = 500 元个体店保证金；`payable: 0`、`balance: 1000`） |

资金账单条目的候选字段表（拿到首笔账单前使用，命中即按约定换算）：

1. 明确为分的字段：`amount_cents`
2. 候选（整数按分、带小数点按元）：`amount` / `bill_amount` / `order_amount` / `settle_amount` / `settlement_amount` / `total_amount` / `charge_amount` / `fee`
3. 全部未命中时记 0，界面标注「金额字段待探明」，**不要用猜测值冒充事实**

### F.5 多店资金看板建议

1. 每店一次 `query_item`（近 30 天），汇总条数与金额，单店失败不影响其他店
2. 上游不可用时回退本地缓存，并明确标注数据来源与错误
3. 资金数据只读；提现 / 转账等资金操作不纳入工具范围

> 索引见 [README.md](README.md)。
