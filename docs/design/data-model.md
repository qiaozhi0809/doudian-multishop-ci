# 数据模型

> 订单状态机、表结构、关键约束、存储说明。章节号沿用原 `architecture.md` 第 6 节。
> 索引见 [docs/README.md](../README.md)。

## 6. 数据模型

### 6.1 订单状态机

```
          ┌──────────── 作废重取 ────────────┐
          ▼                                  │
 synced → pending_label → label_obtained → printed → shipped → closed
   │            │              │
   │            └──► exception ┘   （地址异常 / 超区 / 库存不足 / 余额不足）
   │                  │
   └─ 取消/退款 ──────► cancelled

 快捷路径：pending_label ──「打单并发货」──► shipped
```

- `status` 是**本地履约状态**，只由本系统推进；平台订单状态另存 `platform_status`（6.2 ③），两者不混用。
- `synced`：订单刚从平台同步入库，尚未做取号预检（会话/快递/地址）。
- `pending_label`：预检通过，允许进入取号批次。
- `label_obtained`（已取号未发货）是关键中间态，保证取号与发货可分离、可回滚。
- **打印结果不是订单状态**：打印失败时订单停留在 `label_obtained`，
  失败详情记在 `print_job.status` / `result_detail`，可无限重试；面单保持 `active`。
- `exception` 必须记录 `exception_reason`，人工处理后回到 `pending_label`。
- 面单作废后，`waybills.status=void`，订单回到 `pending_label`。
- **快捷路径**：`batchFetchTrackingNosAndDeliverGoods` 一步完成取号与发货，
  `pending_label` 直接转 `shipped`，跳过 `label_obtained` / `printed`；仍写一条 `waybills` 记录。
- `cancelled` 的触发：订单同步发现 `platform_status` 变为已关闭（`4`）且本地未发货（[backend.md](backend.md) 5.4）。
- 已发货订单改物流（阶段二）后面单与状态如何变化：⏳ 未设计（gaps DM-10）。

### 6.2 表结构

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ① 店铺
CREATE TABLE shop (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  entity        TEXT,                       -- 营业执照主体
  platform      TEXT NOT NULL DEFAULT 'doudian',
  shop_no       TEXT,                       -- 平台店铺号
  channel       TEXT NOT NULL DEFAULT 'protocol',  -- protocol | browser
  status        TEXT NOT NULL DEFAULT 'needs_login',
                -- active | needs_login | disabled
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

-- ①-b 店铺画像（取自已验证的资质/管理员/绑定接口，随会话同步刷新）
CREATE TABLE shop_profile (
  shop_id           INTEGER PRIMARY KEY REFERENCES shop(id),
  qual_id           TEXT,                   -- 资质主键（≠ shop_no，改名也不变）
  shop_type_code    INTEGER,
  operate_status_str TEXT,                  -- 如「正常营业」
  open_time         TEXT,
  main_category     TEXT,
  main_category_id  INTEGER,
  province          TEXT,
  city              TEXT,
  district          TEXT,
  street            TEXT,
  address_detail    TEXT,
  settle_delay      TEXT,                   -- 如「21天」
  admin_name        TEXT,
  admin_mobile      TEXT,                   -- 平台只返回脱敏值
  raw_json          TEXT,
  synced_at         TEXT NOT NULL
);

-- ② 会话
CREATE TABLE session (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER NOT NULL REFERENCES shop(id),
  cookies       BLOB,                       -- DPAPI 加密的全量 cookie（JSON），协议通道用
  token         BLOB,                       -- DPAPI 加密的 __token（每店一个，跟随会话）
  device_params TEXT,                       -- JSON：指纹与设备参数
  js_version    TEXT,                       -- 签名 JS 版本
  expires_at    TEXT,
  health        TEXT NOT NULL DEFAULT 'healthy',  -- healthy | expiring | expired
  updated_at    TEXT NOT NULL
);
CREATE INDEX idx_session_shop ON session(shop_id, updated_at DESC);

-- ③ 订单
CREATE TABLE orders (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  order_no        TEXT NOT NULL,             -- 平台店铺订单号
  platform_order_id TEXT,                    -- 平台内部订单 ID（部分接口使用）
  combine_id      TEXT,                      -- 合单 ID（取号必需，可空）
  status          TEXT NOT NULL,             -- 本地履约状态（6.1），不被平台数据覆盖
  platform_status INTEGER,                   -- 平台 order_status 数字（3 已发货 / 4 已关闭 / 5 已完成…），每次同步覆盖
  exception_reason TEXT,
  buyer_nick      TEXT,
  receiver_name   TEXT,                      -- 列表返回的脱敏值
  receiver_phone  TEXT,                      -- 列表返回的脱敏值
  receiver_region TEXT,
  receiver_address TEXT,                     -- 解密后的明文地址（仅按需解密时写入；存储与清除见 gaps DM-11）
  address_encrypted INTEGER NOT NULL DEFAULT 0,
  address_decrypted_at TEXT,
  amount_cents    INTEGER,
  pay_time        TEXT,
  create_time     TEXT,
  exp_ship_time   TEXT,                      -- 承诺发货时间
  logistics_status TEXT,                     -- 阶段二使用
  raw_json        TEXT,
  synced_at       TEXT NOT NULL,
  last_sync_at    TEXT,
  UNIQUE(shop_id, order_no)
);
CREATE INDEX idx_orders_status ON orders(status, shop_id);
CREATE INDEX idx_orders_platform_status ON orders(platform_status, shop_id);
CREATE INDEX idx_orders_paytime ON orders(pay_time);

-- ④ 订单商品行
CREATE TABLE order_items (
  id            INTEGER PRIMARY KEY,
  order_id      INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  sku_order_id  TEXT,                       -- 取号必需（子订单 ID）
  sku_id        TEXT,
  product_id    TEXT,                       -- 取号必需
  product_name  TEXT,
  sku_spec      TEXT,
  quantity      INTEGER NOT NULL,
  price_cents   INTEGER
);
CREATE INDEX idx_items_order ON order_items(order_id);

-- ⑤ 面单（一单可多次取号，保留历史）
CREATE TABLE waybills (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER NOT NULL REFERENCES shop(id),
  order_id      INTEGER NOT NULL REFERENCES orders(id),
  seq           INTEGER NOT NULL DEFAULT 1,  -- 该订单第几次取号（作废后 +1），参与幂等键（backend 5.11）
  courier_code  TEXT NOT NULL,
  waybill_no    TEXT,                       -- 运单号（平台字段 tracking_no）
  print_data    TEXT,                       -- 取号返回的加密打印数据（base64）
  sign          TEXT,                       -- 打印签名
  logistics_template_code TEXT,             -- 面单模板编码（取号请求用）
  exp_type      TEXT,                       -- 产品类型（transport.expType）
  ebill_id      TEXT,                       -- 面单账户 ID
  net_code      TEXT,                       -- 网点编码
  status        TEXT NOT NULL,              -- active | printed | void
  obtained_at   TEXT,
  printed_at    TEXT,
  voided_at     TEXT
);
CREATE INDEX idx_waybills_order ON waybills(order_id, status);
-- 同一订单同时只能存在一张有效面单；printed 也占用唯一名额，
-- 防止「已打印未发货」的订单重复取号。打印失败不改面单状态，只记 print_job.status
CREATE UNIQUE INDEX uq_active_waybill
  ON waybills(order_id) WHERE status IN ('active','printed');
-- 运单号全局唯一：本地发货防重（ship 幂等键）在数据库层也有保障
CREATE UNIQUE INDEX uq_waybill_no ON waybills(courier_code, waybill_no) WHERE waybill_no IS NOT NULL;

-- ⑤-b 打印任务（每次打印尝试一条）
CREATE TABLE print_job (
  id            INTEGER PRIMARY KEY,
  waybill_id    INTEGER NOT NULL REFERENCES waybills(id),
  printer_name  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'queued',  -- queued | success | failed
  result_code   TEXT,
  result_detail TEXT,                       -- 组件回执（notifyPrintResult）
  attempts      INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL,
  finished_at   TEXT
);
CREATE INDEX idx_print_job_waybill ON print_job(waybill_id, created_at DESC);

-- ⑥ 任务队列
CREATE TABLE tasks (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER REFERENCES shop(id),
  type            TEXT NOT NULL,            -- sync_orders | obtain_label | fetch_and_ship | void_label | print
                                            -- | ship | recover_label | decrypt | reconcile | sync_base | sync_aggregate
  payload         TEXT,
  idempotency_key TEXT UNIQUE,              -- 规则见 backend 5.11；重试复用本行，不新建
  status          TEXT NOT NULL DEFAULT 'queued',
                  -- queued | running | verifying（结果不明，待核实，backend 5.12）| success | failed | cancelled
  attempts        INTEGER NOT NULL DEFAULT 0,
  last_error      TEXT,
  created_at      TEXT NOT NULL,
  started_at      TEXT,
  finished_at     TEXT
);
CREATE INDEX idx_tasks_status ON tasks(status, created_at);

-- ⑦ 审计日志
CREATE TABLE audit_log (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER,
  task_id       INTEGER,
  action        TEXT NOT NULL,
  req_summary   TEXT,
  resp_summary  TEXT,
  result        TEXT NOT NULL,
  duration_ms   INTEGER,
  created_at    TEXT NOT NULL
);
CREATE INDEX idx_audit_time ON audit_log(created_at);
CREATE INDEX idx_audit_shop ON audit_log(shop_id, created_at);

-- ⑧ 对账结果
CREATE TABLE reconcile_findings (
  id          INTEGER PRIMARY KEY,
  run_id      TEXT NOT NULL,       -- 同一次对账的批次号（backend 5.10 按批次展示）
  run_at      TEXT NOT NULL,
  kind        TEXT NOT NULL,   -- local_shipped_platform_not | platform_shipped_local_not | waybill_mismatch
  shop_id     INTEGER,
  order_no    TEXT,
  detail      TEXT,
  resolved    INTEGER NOT NULL DEFAULT 0
);

-- ⑨ 配置
CREATE TABLE settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- ⑩ 发货地址（每店独立，取号必需）
CREATE TABLE shop_address (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER NOT NULL REFERENCES shop(id),
  address_id    TEXT NOT NULL,               -- 平台侧地址 ID
  name          TEXT,
  phone         TEXT,
  region        TEXT,
  detail        TEXT,
  province_id   INTEGER,                     -- 行政区 ID（取号 / sendcheck 必需）
  province_name TEXT,
  city_id       INTEGER,
  city_name     TEXT,
  town_id       INTEGER,
  town_name     TEXT,
  street_id     INTEGER,
  street_name   TEXT,
  is_default    INTEGER NOT NULL DEFAULT 0,
  raw_json      TEXT,
  synced_at     TEXT NOT NULL,
  UNIQUE(shop_id, address_id)
);

-- ⑩-b 面单账户（取号必需：net_code / ebill_id）
CREATE TABLE ebill_account (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER NOT NULL REFERENCES shop(id),
  courier_code  TEXT NOT NULL,
  ebill_id      TEXT NOT NULL,              -- 平台字段 eBillId（数字，按文本存）
  net_code      TEXT NOT NULL,              -- 平台字段 netCode
  net_name      TEXT,
  account_type  INTEGER,                    -- 平台字段 accountType
  balance       INTEGER,                    -- 面单余额（张数，非金额）
  is_default    INTEGER NOT NULL DEFAULT 0,
  raw_json      TEXT,
  synced_at     TEXT NOT NULL,
  UNIQUE(shop_id, courier_code, ebill_id, net_code)
);

-- ⑪ 面单模板（取号必需）
CREATE TABLE waybill_template (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER NOT NULL REFERENCES shop(id),
  template_code TEXT NOT NULL,
  courier_code  TEXT,
  name          TEXT,
  is_default    INTEGER NOT NULL DEFAULT 0,
  raw_json      TEXT,
  synced_at     TEXT NOT NULL,
  UNIQUE(shop_id, template_code)
);

-- ⑫ 快递公司
CREATE TABLE courier (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER NOT NULL REFERENCES shop(id),
  courier_code  TEXT NOT NULL,
  name          TEXT,
  enabled       INTEGER NOT NULL DEFAULT 1,
  raw_json      TEXT,
  synced_at     TEXT NOT NULL,
  UNIQUE(shop_id, courier_code)
);

-- ⑬ 包裹（阶段二：合单发货）
CREATE TABLE packages (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER NOT NULL REFERENCES shop(id),
  package_no    TEXT NOT NULL,
  status        TEXT,
  waybill_no    TEXT,
  order_nos     TEXT,                        -- JSON 数组
  raw_json      TEXT,
  synced_at     TEXT NOT NULL,
  UNIQUE(shop_id, package_no)
);

-- ⑭ 物流事件（阶段二：轨迹跟踪）
CREATE TABLE logistics_events (
  id            INTEGER PRIMARY KEY,
  shop_id       INTEGER NOT NULL REFERENCES shop(id),
  waybill_no    TEXT NOT NULL,
  event_time    TEXT,
  status        TEXT,
  description   TEXT,
  raw_json      TEXT,
  synced_at     TEXT NOT NULL
);
CREATE INDEX idx_logistics_waybill ON logistics_events(waybill_no, event_time);

-- ⑮ 跨店对账快照（[附录 G.4](../api/reconcile.md)）
CREATE TABLE orders_snapshot (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  shop_order_id   TEXT NOT NULL,
  order_status    INTEGER,
  tracking_no     TEXT,
  company_code    TEXT,
  pay_time        TEXT,
  ship_time       TEXT,
  raw_json        TEXT,
  first_seen_at   TEXT NOT NULL,
  last_synced_at  TEXT NOT NULL,
  UNIQUE(shop_id, shop_order_id)
);

-- ⑯ 售后聚合（[附录 E](../api/aftersale.md)）
CREATE TABLE aftersale (
  id                  INTEGER PRIMARY KEY,
  shop_id             INTEGER NOT NULL REFERENCES shop(id),
  after_sale_id       TEXT NOT NULL,
  order_no            TEXT,
  type                INTEGER,                -- after_sale_type（平台数字枚举）
  status              INTEGER,                -- after_sale_status（平台数字枚举）
  refund_amount_cents INTEGER,
  status_deadline     TEXT,                   -- ISO-8601 UTC；平台值为 unix 秒，0 表示已完结 → 存 NULL
  apply_time          TEXT,
  detail_json         TEXT,
  synced_at           TEXT NOT NULL,
  UNIQUE(shop_id, after_sale_id)
);

-- ⑰ 商品快照（[附录 D.1](../api/catalog.md)）
CREATE TABLE product_snapshot (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  product_id      TEXT NOT NULL,
  name            TEXT,
  status          TEXT,
  tab             TEXT,
  price_lower_cents   INTEGER,
  price_higher_cents  INTEGER,
  stock_num       INTEGER,
  sell_num        INTEGER,
  raw_json        TEXT,
  synced_at       TEXT NOT NULL,
  UNIQUE(shop_id, product_id)
);

-- ⑱ 库存快照（[附录 D.2](../api/catalog.md)）
CREATE TABLE stock_snapshot (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  product_id      TEXT NOT NULL,
  total_stock_num             INTEGER,
  spot_stock_num              INTEGER,       -- 现货
  future_stock_num            INTEGER,       -- 未来库存；与现货分开展示，不可相加（[附录 D.4](../api/catalog.md)）
  total_occupied_stock_num    INTEGER,
  total_unoccupied_stock_num  INTEGER,
  is_alarming     INTEGER,
  raw_json        TEXT,
  synced_at       TEXT NOT NULL,
  UNIQUE(shop_id, product_id)
);

-- ⑲ 待结算订单（[附录 F.1b](../api/fund.md)）
CREATE TABLE fund_unsettled (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  shop_order_no   TEXT NOT NULL,             -- 唯一键列必须非空：SQLite 中多个 NULL 互不冲突
  sku_order_no    TEXT NOT NULL,
  product_id      TEXT,
  income_amount_cents         INTEGER,
  unsettled_amount_cents      INTEGER,
  platform_service_fee_cents  INTEGER,
  ecom_order_status   TEXT,
  expected_settle_time TEXT,
  settle_period_detail TEXT,
  raw_json        TEXT,
  synced_at       TEXT NOT NULL,
  UNIQUE(shop_id, shop_order_no, sku_order_no)
);

-- ⑳ 保证金账户（[附录 F.1c](../api/fund.md)）
CREATE TABLE margin_account (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  payable_cents         INTEGER,             -- 平台 payable（单位：分，[附录 F.4](../api/fund.md)）
  balance_cents         INTEGER,             -- 平台 balance
  basic_payable_cents   INTEGER,             -- 平台 risk_detail.basic_payable
  basic_balance_cents   INTEGER,             -- 平台 risk_detail.basic_balance
  withdrawable_cents    INTEGER,             -- 平台 withdraw_detail.withdrawable_amount
  level           TEXT,
  raw_json        TEXT,
  synced_at       TEXT NOT NULL,
  UNIQUE(shop_id)
);
```

### 6.3 关键约束

1. 金额一律用**整数分**，禁止浮点。
2. 时间统一 **ISO-8601 UTC 文本**，界面按本地时区展示。
3. 订单唯一性由 `(shop_id, order_no)` 保证。`order_no` 即平台 `shop_order_id`（其他表中的 `shop_order_id` / `shop_order_no` 指同一个值）。
4. `uq_active_waybill` 保证同一订单同时只有一张有效面单。
5. `tasks.idempotency_key` 保证取号/发货不会重复执行；取号键含 `seq`，作废后可再次取号（backend 5.11）。
   `uq_waybill_no` 再从数据库层防止同一运单入库两次。
6. `raw_json` 保留完整平台报文，用于排障与重放解析。
7. 地址、模板、快递均按 `(shop_id, code)` 唯一，**禁止跨店复用**。
8. 取号与官方组件打印**不依赖**收货地址解密（DEC-06）；`receiver_address` 为空的订单照常进入取号批次。

### 6.4 只读聚合与存储说明（DM-06 ~ DM-09）

**只读聚合模块的表**（建表语句见 6.2 ⑮~⑳，字段定义参考对应附录）：

| 表 | 用途 | 字段依据 |
|---|---|---|
| `orders_snapshot` | 跨店对账快照 | [附录 G.4](../api/reconcile.md) |
| `aftersale` | 售后聚合 | [附录 E.1](../api/aftersale.md) / E.7 |
| `product_snapshot` / `stock_snapshot` | 商品与库存快照 | [附录 D.1](../api/catalog.md) / D.2 |
| `fund_unsettled` / `margin_account` | 资金待结算与保证金 | [附录 F.1b](../api/fund.md) / F.1c |
| `order_fact` / `order_fact_item` / `shop_daily_stats` / `product_daily_stats` / `shop_status_snapshot` | 经营仪表盘（草案） | [dashboard.md](dashboard.md) 第 3 节 |

**会话存储（DM-08）**：以 SQLite `session` 表为唯一来源。

- `session.cookies` 与 `session.token` 用 **DPAPI**（Windows）加密后存库，密钥随用户账户绑定
- 浏览器通道不存 `storage_state`，直接使用每店持久化用户目录 `data/profiles/<shop_id>/`（[backend.md](backend.md) 5.1）
- **不保留明文 `cookies/` 目录作为运行时依赖**；如需跨机迁移，
  导出包必须整体加密（DPAPI 或口令加密），且不入库、不同步
- 明文会话只存在于内存，进程退出即丢弃

**迁移机制（DM-09）**：使用 **Alembic** 管理表结构变更。

- 初始迁移脚本随第一次实现提交
- 迁移脚本只前进不后退（SQLite 的 ALTER 能力有限，必要时重建表）
- 每次发布前在副本库上演练迁移
