# 经营仪表盘（多店聚合）

> 单店 / 多店的订单量、销售额、售后率、出单与发货、店铺排行、商品排行，按日 / 周 / 月展示。
> 状态：**草案**（2026-11-25）。依据的字段均来自已验证接口（[api/](../api/README.md)），未验证项标 ⏳ 并登记在 [gaps.md](../gaps.md)。
> 实现状态（M6，2026-11-25）：仪表盘已用**现有聚合接口**展示履约（待发货 / 24h 须发 / 超时未发）、
> 售后待办、资金（待结算 / 保证金）、库存预警与店铺排行、发货压力与待结算分布两张柱状图；
> 支付 GMV / 支付订单数 / 客单价 / 出单店铺数 / 售后率 / 退款金额在界面标「待补」，等 `order_fact`
> 与售后时间字段（API-23 / API-25）补齐后再展示，不显示估算值。
> 指标口径（出单率、售后率、事实表）为本设计的决定，见第 6 节；有业务上的不同理解时再调整。
> 索引见 [docs/README.md](../README.md)。

---

## 0. 可行性结论

| 结论 | 指标 |
|---|---|
| **可行，已验证字段即可** | 单店 / 多店的支付订单数、支付 GMV、客单价、成交人数（日 / 周 / 月）；店铺排行（今天谁卖得多、卖了多少，可比昨天同时段）；出单店铺数；发货及时率与发货时效；待发货 / 24h 内须发 / 超时未发；按销量的商品排行；售后待办与临近超时；待结算金额、保证金；库存预警与售罄 |
| **可行，但要先补验证** | 售后率、退款金额与退款率、净成交（API-25：售后能否按时间统计、退款成功时间）；商家实收（API-24）；按金额的商品排行、曝光 / 点击（API-26）；已结算账单（API-15） |
| **现有数据做不到，需新数据源** | 访客数、转化率、流量来源等流量类指标——只有抖店罗盘有（API-27，待抓取） |

**最关键的前提是 API-23**：`searchlist` 能否按支付时间筛时间窗。

- 能筛：历史可以按天回填，上表第一行全部可做，含过去的日 / 周 / 月。
- 不能筛：**从上线当天起**按热窗口持续同步，历史从那天开始积累，指标照样可做；
  只是上线前的历史只能按默认排序翻页尽量回填（成本高、可能不全）。不影响「今天 / 本周 / 本月」的实时看板。

因此仪表盘整体**可行**，不存在阻塞性风险；差别只在历史数据能回溯多远、售后类指标何时上线。

---

## 1. 指标目录

可行性：✅ 现有已验证字段即可；🔶 需补验证；🆕 需新接口。

### 1.1 成交

| 指标 | 口径 | 来源（已验证字段） | 粒度 | 可行性 |
|---|---|---|---|---|
| 支付订单数 | `pay_time` 落在北京时间窗口内的订单数；不含未支付；**支付后再关闭 / 退款的仍计入** | `searchlist`：`pay_time`、`order_status`（[附录 C.2](../api/order-page.md)） | 实时 / 日 / 周 / 月 | 🔶 未支付订单的 `pay_time` 取值、完整状态枚举待确认（API-23） |
| 支付 GMV | 同一批订单 `Σ pay_amount`（买家实付，含运费，单位分） | `pay_amount`（C.2） | 同上 | ✅ |
| 商品额 / 优惠 / 运费 | `Σ total_goods_amount` / `promotion_amount` / `post_amount` | C.2 | 日 | ✅（三者与实付的关系需用样本核对） |
| 商家实收 | `Σ actual_receive_amount_int` | C.2 | 日 | 🔶 是否已扣平台服务费，需与待结算 `income_amount` 对照（API-24） |
| 客单价 | 支付 GMV ÷ 支付订单数 | 推导 | 日 | ✅ |
| 成交人数 | 按 `user_id` 去重 | C.2 | 日 | ✅ 周 / 月必须从明细重新去重，不能把每天相加 |
| 净成交 | 支付 GMV − 退款金额 | 订单 + 售后 `refund_amount`（[附录 E.1](../api/aftersale.md)） | 日 / 周 / 月 | 🔶 退款成功状态与时间未知（API-25） |

### 1.2 售后

| 指标 | 口径 | 来源 | 粒度 | 可行性 |
|---|---|---|---|---|
| 售后率（同期） | 当天**申请**的售后单数 ÷ 当天支付订单数。适合看「今天」 | 售后 `apply_time`（E.1） | 日 | 🔶 售后列表能否按时间筛选未验证（API-25） |
| 售后率（回溯，推荐用于周 / 月） | 某天支付的订单中**后来发生过售后**的订单数 ÷ 当天支付订单数；按 `related_id` 关联订单。近 30 天标「未成熟」 | 同上 | 日 / 周 / 月 | 🔶 同上 |
| 退款金额 / 退款率 | 退款金额 ÷ 支付 GMV，按**退款成功时间**归日 | `refund_amount`（E.1） | 日 | 🔶 同上 |
| 售后待办 / 临近超时 | `all_audit`、`approaching_deadline_audit`、`audit_ddl_in_one_day`、`arbitrate_*` 计数 + `status_deadline` 队列 | `aftersale/counts`、列表（E.1 / E.2） | 实时 | ✅ |

**口径决定**：日视图用同期口径；周 / 月视图用回溯口径，近 30 天标「未成熟」。界面写明当前口径。

### 1.3 出单与发货

「出单率」有多种理解，下面三种都能做：

| 指标 | 口径 | 来源 | 可行性 |
|---|---|---|---|
| ① 出单店铺率 | 今天至少有 1 笔支付订单的店铺数 ÷ 在营店铺数（显示为「x / N 家出单」） | 订单 | ✅ |
| ② 动销率 | 有销量的商品数 ÷ 在售商品数 | `product_item[].product_id` + `aggsProductCount.onsale`（[附录 D.1](../api/catalog.md)） | ✅ |
| ③ 发货及时率 | 承诺发货时间 `exp_ship_time` 落在窗口内的订单中，`ship_time ≤ exp_ship_time` 的比例 | C.2 | ✅ |
| 发货时效 | 已发货订单 `ship_time − pay_time` 的平均值与 P90 | C.2 | ✅ |
| 待发货 / 24h 内须发 / 超时未发 | `stock_up` / `exp_ship` / `ship_delay` | `tabcnt`（[附录 C.1](../api/order-page.md)） | ✅ 即时值；要看趋势需定时存快照（3.3） |

**口径决定**：主卡片显示 ① 出单店铺数（x / N），旁边并列 ③ 发货及时率；② 动销率放在商品区。

### 1.4 排行

| 指标 | 口径 | 可行性 |
|---|---|---|
| 店铺排行 | 按店铺分组的支付 GMV、订单数、客单价、售后率，可与「昨天同一时段」比较 | ✅ |
| 商品排行（按销量） | 按 `product_id` 汇总 `quantity`；SKU 用 `sku_spec` 区分 | ✅ |
| 商品排行（按金额） | 需商品行单价 / 分摊金额字段，C.2 未收录 | 🔶 API-26 |
| 商品 30 天销量（平台值） | `sell_num_30d`（D.1） | ✅ |
| 曝光 / 点击 | `listTractionItems`（D.1 只记了用途，没有字段） | 🔶 API-26 |

### 1.5 资金与库存（快照）

| 指标 | 来源 | 可行性 |
|---|---|---|
| 待结算金额 | `aggregation_res.total_unsettled_amount`（[附录 F.1b](../api/fund.md)，单位分） | ✅ |
| 已结算 / 账单 | `CHARGE_BILL_ITEM` 字段未知（F.4） | 🔶 API-15 |
| 保证金 | `balance` / `basic_balance`（F.1c，单位分） | ✅ |
| 库存预警 / 售罄 | `stock_alarm_cnt` / `sold_out_cnt`（[附录 D.2](../api/catalog.md)） | ✅ |

### 1.6 口径约定

- **时间归属**：成交类按 `pay_time`，售后申请按 `apply_time`，退款按退款成功时间，发货按 `ship_time` / `exp_ship_time`。
- **日期边界**：存储仍用 UTC；入库时按**北京时间**（UTC+8，无夏令时）算出 `biz_date`，所有日 / 周 / 月边界按 `biz_date` 划分。
- **比率汇总**：周 / 月的比率一律用「分子之和 ÷ 分母之和」，不对每日比率求平均。
- **与平台数字的差异**：抖店罗盘等平台报表的口径（如订单是否按 SKU 计、是否含取消单）与本系统不同，界面必须标注「本系统口径」。

---

## 2. 数据策略

### 2.1 需要改变的地方

现有订单同步只拉待发货订单（[backend.md](backend.md) 5.4），而且 `orders.status` 是本地履约状态。仪表盘需要**所有状态**的订单和平台状态，因此：

- 新增**订单事实表** `order_fact` / `order_fact_item`（3.1），与履约用的 `orders` 分开；同步用 `searchlist` 的 `tab=all`。
- 附录 G 的对账快照 `orders_snapshot` 与 `order_fact` 字段高度重合：**合并**，对账改读 `order_fact`，`orders_snapshot` 不再单独建表。

### 2.2 同步节奏

| 窗口 | 频率 | 请求量估算（50 店，每店日单 10~500，pageSize 200） |
|---|---|---|
| 热窗口：今天 + 昨天 | 每 10~15 分钟 | 每店 1~3 页，一轮约 150 个请求；按每店串行、3 店并发、间隔 300~1200ms，约 1~2 分钟 |
| 温窗口：近 30 天 | 每晚一次，补上后来发生的关闭、退款、发货 | 最坏每店 75 页，约 3750 个请求，约 20~30 分钟，放在夜间 |
| 首次回填 | 按天切窗口，分几个晚上完成 | 避免深度翻页 |

前提：`searchlist` 能按 `pay_time` 或 `create_time` 筛时间窗（⏳ API-12 / API-23）。若不能，见第 0 节的退路：从上线日起持续积累。

### 2.3 迟到的状态变化

- 近 30 天（T−1 ~ T−30）每晚**从事实表整天重算**日汇总，不做增量累加。
- 超过 30 天的日汇总标 `is_final = 1`，不再重算。
- 回溯口径的售后率在 30 天内标「未成熟」。

---

## 3. 表结构（草案）

```sql
-- 订单事实（所有状态；仪表盘与对账共用，替代 orders_snapshot）
CREATE TABLE order_fact (
  shop_id            INTEGER NOT NULL REFERENCES shop(id),
  shop_order_id      TEXT NOT NULL,
  platform_status    INTEGER,
  user_id            TEXT,
  pay_time           TEXT,                 -- ISO UTC
  biz_date           TEXT,                 -- 北京时间日期（按 pay_time）
  pay_amount_cents       INTEGER,
  goods_amount_cents     INTEGER,
  promotion_cents        INTEGER,
  post_cents             INTEGER,
  receive_amount_cents   INTEGER,          -- actual_receive_amount_int
  exp_ship_time      TEXT,
  ship_time          TEXT,
  tracking_no        TEXT,
  company_code       TEXT,                 -- 对账用（附录 G）
  raw_json           TEXT,
  first_seen_at      TEXT NOT NULL,        -- 首次写入后不再更新（附录 G.4）
  synced_at          TEXT NOT NULL,
  PRIMARY KEY (shop_id, shop_order_id)
);
CREATE INDEX idx_fact_date ON order_fact(biz_date, shop_id);

CREATE TABLE order_fact_item (
  shop_id        INTEGER NOT NULL,
  shop_order_id  TEXT NOT NULL,
  product_id     TEXT,
  sku_spec       TEXT,
  quantity       INTEGER,
  PRIMARY KEY (shop_id, shop_order_id, product_id, sku_spec)
);

-- 店铺日汇总
CREATE TABLE shop_daily_stats (
  shop_id                 INTEGER NOT NULL,
  biz_date                TEXT NOT NULL,
  paid_orders             INTEGER,
  paid_amount_cents       INTEGER,
  goods_amount_cents      INTEGER,
  promotion_cents         INTEGER,
  post_cents              INTEGER,
  receive_amount_cents    INTEGER,
  buyers                  INTEGER,         -- 不可跨天相加
  closed_after_pay        INTEGER,
  item_qty                INTEGER,
  due_orders              INTEGER,         -- exp_ship_time 落在当天
  shipped_on_time         INTEGER,
  shipped_orders          INTEGER,
  ship_secs_sum           INTEGER,
  aftersale_applied       INTEGER,         -- 同期口径
  aftersale_refund_cents  INTEGER,
  cohort_aftersale_orders INTEGER,         -- 回溯口径
  is_final                INTEGER NOT NULL DEFAULT 0,
  computed_at             TEXT NOT NULL,
  PRIMARY KEY (shop_id, biz_date)
);

-- 商品日汇总
CREATE TABLE product_daily_stats (
  shop_id     INTEGER NOT NULL,
  biz_date    TEXT NOT NULL,
  product_id  TEXT NOT NULL,
  qty         INTEGER,
  orders      INTEGER,
  PRIMARY KEY (shop_id, biz_date, product_id)
);

-- tabcnt 定时快照（待发货积压 / 超时未发的趋势）
CREATE TABLE shop_status_snapshot (
  shop_id      INTEGER NOT NULL,
  taken_at     TEXT NOT NULL,
  stock_up     INTEGER,
  exp_ship     INTEGER,
  ship_delay   INTEGER,
  in_aftersale INTEGER,
  PRIMARY KEY (shop_id, taken_at)
);
```

**周 / 月汇总**：从日汇总现算，不另存。自然周（周一开始）按 `date(biz_date, '-6 days', 'weekday 1')` 分组，月按 `substr(biz_date, 1, 7)` 分组。成交人数例外，需回到 `order_fact` 去重。

---

## 4. 界面布局

| 区块 | 内容 |
|---|---|
| 顶栏 | 日期范围（今天 / 昨天 / 近 7 天 / 近 30 天 / 本月 / 自定义）、店铺筛选、数据更新时间、口径说明、同步失败或掉线店铺提示 |
| KPI 卡片 | 支付 GMV、支付订单数、客单价、出单店铺数（x / N）、售后率、退款额、发货及时率，均带环比 |
| 趋势图 | GMV / 订单量折线，按日 / 周 / 月切换；按店铺堆叠（前 5 家 + 其他） |
| 店铺排行表 | GMV、订单数、客单价、售后率、待发货、超时未发、会话状态；可排序，带迷你走势 |
| 店铺 × 日期热力图 | 一眼看出哪些店哪天零出单 |
| 履约区 | 待发货、24h 内须发、超时未发；发货时效 P50 / P90 |
| 售后区 | 临近超时的待办队列与各项计数 |
| 商品区 | Top 10 商品、库存预警、售罄 |
| 资金区 | 各店待结算金额、保证金 |

组件选型见 [frontend.md](frontend.md) 第 6 节（`metrics-dashboard`、`metric-card`、`bar-chart`、`line-chart`、`sparkline`、`sortable-data-table`）。
本地接口见 [local-api.md](local-api.md)「仪表盘」分组。

---

## 5. 平台官方数据（阶段二候选）

- **抖店罗盘**（`compass.jinritemai.com`）可直接给出成交金额、支付订单数、成交人数、退款、访客、转化率。仓库里**从未抓过**，接口路径待抓取；它是独立域名，现有会话与签名能否沿用未知（⏳ API-27）。
- 建议作为「官方参考值」每店每天抓一次，与自算结果并排展示，**不替代自算**。
- 商家体验分、品质退货率、揽收及时率等的官方公式未查到，页面同样待抓取。

---

## 6. 依赖的缺口与口径决定

| 编号 | 内容 |
|---|---|
| API-12 / API-23 | `searchlist` 按 `pay_time` / `create_time` 筛时间窗；完整状态枚举；未支付订单的 `pay_time`；默认排序与深度翻页上限 |
| API-24 | `actual_receive_amount_int` 与待结算 `income_amount` 的关系 |
| API-25 | 售后列表按时间筛选 / 排序；退款成功状态与时间；`after_sale_type` 枚举 |
| API-26 | 商品行单价 / 分摊金额字段；`listTractionItems` 字段 |
| API-27 | 抖店罗盘经营概览接口（待抓取） |
| API-15 | 资金账单 `CHARGE_BILL_ITEM` 字段 |

**口径决定**（本设计确定，业务上有不同理解时再改）：

| 编号 | 决定 |
|---|---|
| DEC-07 出单率 | 主显示出单店铺数 x / N，并列发货及时率；动销率放商品区 |
| DEC-08 售后率 | 日视图同期口径；周 / 月回溯口径，近 30 天标「未成熟」 |
| DEC-09 事实表 | `order_fact` 与对账快照合并，对账改读 `order_fact` |
