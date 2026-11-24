# 抖店多店铺管理后台 · 设计文档

> 本文档描述抖店多店铺管理后台的产品设计、接口规范与工程约束。
> 所有接口结论均基于对店铺后台的授权使用与合法接口调用记录整理。



- 日期：2026-11-03（初版）；2026-11-24（第一轮验证 + 技术栈修订）；2026-11-25（写接口与打印协议验证）
- 状态：已评审（设计阶段）；2026-11-24 更新只读接口清单与技术栈（React 19 + Arc 组件库）
- 参考产品：抖小宝（douxiaobao.com）
- 项目目录：`doudian-multishop-admin/`（本仓库根目录）
- UI 组件库：`uiarc-system`（Arc Free 122 + Arc Pro 121 + Pro blocks 130+）
- 研究证据：`artifacts/`（本地留存，不入库）

---

## 目录

**正文**：0 说明 · 1 背景与目标 · 2 范围 · 3 假设与约束 · 4 总体架构 · 5 模块设计 · 6 数据模型 · 7 核心流程 · 8 异常处理 · 9 风控与合规 · 10 打印方案 · 11 技术栈与目录结构 · 12 测试策略 · 13 里程碑 · 14 验收标准 · 15 风险与对策 · 16 M0 技术验证清单

**附录**：A 接口清单（只读已验证 / 写接口待定）· B 能力分级 · C 订单页 UI→接口 · D 商品/库存 UI→接口 · E 售后聚合 UI→接口 · F 资金看板 UI→接口 · G 跨店对账逻辑

---

## 0. 一句话说明

给管理**多家不同主体的抖音小店**的商家，做一个**本机运行的多店管理后台**：把订单、售后、商品、库存、资金、对账聚合到同一个界面，替代「逐个登录每个店后台、重复操作」的日常劳动。

前端用 Arc 组件库（`uiarc-system`）搭完整后台，后端在本机代理所有抖店请求，数据与登录态全部留在本机。

---

## 1. 背景与目标

### 1.1 背景

抖小宝等「抖店商家助手」把多店管理做成 PC 客户端。其核心价值不是某个单点功能，而是：

- **一个后台管理多家店**，免去反复登录切换；
- 把**重复的批量操作**自动化，降低人力成本；
- 数据留存在商家本机，登录态走商家自己的网络环境。

本项目为**自用工具**，不对外售卖，因此不需要授权、计费、自动更新、反破解等商业化设施，全部精力投入"把活干成"。

### 1.2 目标

| 目标 | 衡量方式 |
|---|---|
| 多店订单聚合 | 一个界面看到所有店的待发货订单 |
| 批量取号 | 勾选 N 单，一次操作完成全部取号 |
| 批量打印 | 按店铺/快递分组打印，面单与店铺对应关系零错误 |
| 发货回传 | 人工确认后一次点击，全部订单回写平台为"已发货" |
| 安全可控 | 取号与发货分离；重复取号/重复发货为 0 |
| 可维护 | 抖店接口变化时，只改 `adapter/doudian/`（含签名子目录） |

### 1.3 已确认的业务前提

1. 多店**分属不同营业执照主体**，需分别登录，每店独立会话。
2. 电子面单**已开通**，快递公司**已绑定**，无需对接快递公司开放平台。
3. 打印机与打印方式已在各店后台配置好（具体打印实现见第 10 节）。
4. 采用**半自动**模式：软件负责取号等可逆动作，发货回传由人工最终确认。

---

## 2. 范围

### 2.1 MVP 范围（本设计覆盖）

**会话与基础**
- 多店扫码登录与会话持久化，Cookie 导出供协议层使用
- 会话健康检测与一键重登
- 基础数据同步：发货地址、面单模板、快递公司、店铺配置

**订单履约**
- 待发货订单同步（手动 + 定时）
- 多店订单聚合池（筛选、勾选）
- 收货地址解密（`/api/order/receiveinfo`）
- 批量取电子面单号
- 面单打印（官方打印组件 `wss://localhost:13999`；自渲染兜底）
- 发货前检查 + 发货回传（人工确认）
- 面单作废与重打（依赖作废接口验证，见 gaps API-08）
- 每日对账
- 操作审计日志、限速、演练模式

**多店聚合（只读）**
- 售后聚合：列表、详情、状态计数、待办队列（附录 E）
- 商品管理：列表、状态计数、分组、类目（附录 D）
- 库存管理：列表、现货/未来库存、预警（附录 D）
- 资金看板：账单查询、多店概览（附录 F）
- 跨店对账：快照比对、三类异常（附录 G）

**前端**
- 完整后台界面（React + Arc 组件库），页面见第 11.3 节

### 2.2 非目标（明确不做或延后）

| 内容 | 去处 |
|---|---|
| 售后处理动作（同意退款、填运单号等写接口） | 阶段二 |
| 商品创建 / 编辑 / 上下架（写接口） | 阶段二 |
| 物流轨迹、改物流、批量备注、合单发货 | 阶段二 |
| 营销活动、优惠券、千川/联盟推广 | 阶段三 |
| 客服 IM（飞鸽）、评价管理 | 阶段三 |
| 直播管理、店铺装修、供应链 | 不做 |
| 对外授权、多租户、账户体系、计费 | 不做 |
| 移动端 | 不做 |
| 跨平台（快手/淘宝/拼多多） | 不做 |

> 说明：非目标中的功能大多可在「渠道适配层 + 任务队列」之上扩展；写接口因涉及资金与平台风控，统一放在只读链路验证完成之后。

### 2.3 路线图

| 阶段 | 范围 |
|---|---|
| **MVP** | 会话管理、基础数据、拉单、取号、打印、发货、对账 + 售后/商品/库存/资金只读聚合 + 完整前端后台 |
| **阶段二** | 售后处理动作、商品写操作、物流轨迹、改物流、批量备注、合单发货、通知通道 |
| **阶段三** | 营销活动、客服 IM、评价管理、包裹中心、电子面单余额 |

---

## 3. 假设与约束

| 编号 | 假设 | 影响 |
|---|---|---|
| A1 | 店铺数量 5~50 家 | 每店一条串行队列；SQLite 单库足够 |
| A2 | 单店日单量 10~500，总日单量 < 5000 | SQLite + WAL 可支撑；超过需迁移 PostgreSQL |
| A3 | **开发机 ≠ 出单机** | 打印与真实取号在出单机验证；交付时整体拷贝 |
| A4 | 每个店首次由人工扫码登录，之后持久化 | 掉线重登是日常运维动作，必须第一版就有 |
| A5 | 出单机为 Windows 10/11 | 打印优先走官方打印组件；兜底走 Windows 打印子系统 |
| A6 | 网络出口为商家自有宽带（非机房 IP） | 降低风控关联风险 |

---

## 4. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│  Web 控制台（React 19 + Arc 组件库，http://localhost:8787）       │
│  仪表盘 │ 订单 │ 打单 │ 发货 │ 售后 │ 商品 │ 库存 │ 资金 │ 对账     │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP / JSON（TanStack Query）
┌───────────────────────────▼──────────────────────────────────┐
│  应用服务层（FastAPI）                                           │
│  会话管理 │ 订单同步 │ 打单编排 │ 发货回传 │ 调度队列              │
│  售后聚合 │ 商品/库存聚合 │ 资金看板 │ 跨店对账（只读）             │
└───────┬────────────────────────────────────────┬─────────────┘
        │                                        │
┌───────▼────────┐                    ┌──────────▼──────────────┐
│ SQLite         │                    │ 渠道适配层                │
│ 店铺/订单/任务   │                    │ FxgClient（统一抖店客户端） │
│ 售后/账单/对账   │                    │ protocol │ browser       │
│ 商品/库存快照    │                    │ （同一接口两个实现）        │
└────────────────┘                    └──────────┬──────────────┘
                                                 │
                                    ┌────────────▼─────────────┐
                                    │ 抖店内部接口               │
                                    │ fxg.jinritemai.com/...    │
                                    └──────────────────────────┘
```

**分层原则**：

- 界面层不直接访问抖店，只调用本地 API。
- 应用服务层只编排业务，不关心请求怎么发出去。
- 渠道适配层是唯一与抖店交互的地方。
- 存储层只负责持久化，不含业务判断。
- **写操作与读操作分离**：聚合模块（售后/商品/库存/资金/对账）全部只读，
  写操作（取号/发货/售后处理）单独走任务队列并需人工确认。

---

## 5. 模块设计

### 5.1 店铺会话管理器（`service/session_manager.py`）

**职责**：维护每个店的登录态，是所有模块获取会话的唯一入口。

**行为**：

- 首次添加店铺时，启动 Playwright 打开抖店登录页，人工扫码。
- 登录成功后保存：
  - `cookies`（JSON）
  - `storage_state`（Playwright 格式，供兜底渠道使用）
  - `device_params`（UA、屏幕、时区、语言、插件列表、Canvas 指纹等）
- 定期（默认 30 分钟）调用 `GET /api/order/tabcnt` 探测会话有效性（未登录返回 `code:10008`）。
- 会话失效时标记 `needs_login`，暂停该店队列并通知界面。

**会话有效期（API-02）**：

- `sid_guard` 解码后的有效期：**60 天**（`5184000` 秒）；两个样本店均为扫码后 60 天到期
- 界面在到期前 7 天提示重新扫码
- 平台是否通过响应 `Set-Cookie` 刷新会话：未验证；实现按「不刷新」保守处理
  （从扫码时刻起算 60 天），到期前必须重扫

**接口**：

```python
get_session(shop_id) -> Session          # 取可用会话，失效时抛 SessionExpired
refresh(shop_id) -> Session              # 强制重新登录（弹浏览器）
probe(shop_id) -> Health                 # healthy | expiring | expired
```

### 5.2 渠道适配层（`adapter/doudian/`）

**职责**：把"对抖店做的动作"抽象成最少的一组原语，屏蔽协议差异。

```python
class ShopChannel(Protocol):
    # 会话
    def probe_session(shop) -> SessionHealth

    # 基础数据（登录后立即同步并缓存）
    def list_addresses(shop) -> list[AddressDTO]          # 发货地址
    def list_waybill_templates(shop) -> list[TemplateDTO]  # 面单模板
    def list_couriers(shop) -> list[CourierDTO]            # 快递公司

    # 订单
    def list_pending_orders(shop, cursor=None, page_size=50) -> Page[OrderDTO]
    def decrypt_receiver(shop, order) -> ReceiverDTO       # 收货地址解密

    # 面单
    def obtain_waybill(shop, order, courier_code, template_code, address_id) -> WaybillDTO
    def void_waybill(shop, waybill) -> None

    # 发货
    def precheck_ship(shop, orders) -> PrecheckResult      # sendcheck
    def ship_orders(shop, orders, send_type, deliver_type) -> ShipResult
```

**两个实现**：

| 实现 | 技术 | 用途 |
|---|---|---|
| `protocol.py` | `curl_cffi`（签名按需启用） | 默认通道，快、省资源 |
| `browser.py` | Playwright + 页面内 fetch | 兜底通道，签名搞不定时使用 |

通道选择：全局默认 `protocol`，可按店覆盖；单次任务失败后自动降级一次。

### 5.3 签名引擎（`adapter/doudian/signing/`，按需启用）

**M0 / 第一轮验证结论**：只读接口在只带 Cookie + `__token` 时可正常返回（Python + curl_cffi 已在浏览器外验证）。已验证免签名的只读接口：订单列表、状态计数、快递公司（POST）、面单模板、发货地址、收货地址解密、店铺画像。`a_bogus` / `msToken` / `verifyFp` 属于风控打分参数，不是这类接口的鉴权必需项。

因此签名引擎**不进入 MVP 主路径**，保留为接口级开关。

**职责**：当某个接口被确认强制校验签名时，为该接口生成动态参数。

```python
class Signer(Protocol):
    def sign(self, url: str, params: dict, device: DeviceParams) -> dict
```

- 实现：`JsSigner`，用 `py_mini_racer` 在 V8 中执行提取出的 JS。
- 抖店签名由构建产物后的 `bdms` SDK（`rc-client-security/web/stable/1.0.1.20/bdms.js`）生成，静态提取成本较高。
- 启用条件：某接口在无签名时返回风控错误，且已用「带签名 / 不带签名」双对照确认。
- `adapter/doudian/signing/js/` 存放 JS 快照与版本号；抖店更新后替换文件即可。

### 5.4 订单同步器（`service/order_sync.py`）

**职责**：按店拉取待发货订单并归一化入库。

- 触发：手动点击 + 定时（默认 5 分钟，可配置）。
- 分页拉全，使用 `cursor`/时间窗减少重复拉取。
- 归一化：平台字段 → 内部 `OrderDTO` → `orders` / `order_items`。
- 幂等：按 `(shop_id, order_no)` upsert；本地状态机字段不被平台数据覆盖。
- 单店失败不影响其他店。

### 5.5 打单编排器（`service/labeling.py`）

**职责**：把"勾选的订单"变成"已打印的面单"。

流程：

1. 预检：会话有效 / 发货地址已配置 / 面单模板存在 / 地址已解密 / 订单状态允许取号。
2. 按店分组，逐店串行执行取号（`POST /api/order/batchFetchTrackingNos`）。
3. 写入 `waybills`（`status=active`），订单转 `label_obtained`。
4. 按「店 + 快递」分组生成打印批次。
5. 推送打印（见第 10 节），成功后 `waybills.status=printed`，订单转 `printed`。

失败处理：

- 单笔业务拒绝（超区/地址异常/余额不足）→ 订单转 `exception`，记原因，不阻塞批次。
- 会话失效 → 暂停该店，提示重登，重登后从断点继续。
- 瞬时故障 → 退避重试。

### 5.6 发货回传器（`service/shipping.py`）

**职责**：在人工确认后，把运单号回写平台。

- 入口：界面「确认发货」，携带「快递编码 + 运单号」列表。
- 先调用 `POST /api/order/sendcheck` 做发货前检查；不通过则整批拦截并展示原因。
- 通过后调用 `POST /api/order/batchDeliverGoodsByEES`：
  - `send_type`：电子面单枚举，已验证为字符串 `"3"`
  - `batch_deliver_packages`：`[{ logistics_company_code, tracking_no }]`
  - 按「运单号」发货，不需要 `deliverType` / `send_list`
- 幂等：`tasks.idempotency_key = ship:{shop_id}:{courier_code}:{tracking_no}`。
- 成功：`orders.status=shipped`；失败：退避重试 3 次，之后转人工。
- 记录平台返回的完整报文摘要（`success_package_list` / `fail_package_list`）。

### 5.7 调度队列（`service/scheduler.py`）

- **每店一条串行队列**，同店请求绝不并发。
- 全局并发上限（默认 3 个店同时执行）。
- 请求间加入随机延迟（默认 300~1200ms，可配置）。
- 可配置"工作时段"，非时段内不执行定时任务。
- 失败任务进入重试队列，指数退避。

### 5.8 审计与对账（`service/reconcile.py`）

- 每次外部调用记录 `audit_log`：动作、请求摘要、响应摘要、结果、耗时。
- 每日定时对账：
  1. 拉取平台"已发货"订单（时间窗 = 最近 7 天）。
  2. 与本地 `orders` 比对。
  3. 输出三类异常：
     - 本地已发货、平台未发货 → 可能回传失败，需补发。
     - 平台已发货、本地无记录 → 可能人工在其他地方操作。
     - 运单号不一致 → 需人工核对。
- 对账结果落库并在界面展示，支持导出。

### 5.9 基础数据同步器（`service/base_data.py`）

**职责**：登录成功后同步「取号 / 发货所必需」的店铺配置，并缓存到本地。

| 数据 | 来源 | 落库 |
|---|---|---|
| 发货地址（含行政区 ID） | `GET /shopuser/tshopuser/getAfterSaleList`（page **1-based**；`is_send_default=1` 标默认发货地址） | `shop_address` |
| 面单账户（`net_code` / `ebill_id`） | `GET /shopuser/power/getEbillAccountListByExpress` | `ebill_account` |
| 面单模板 | `GET /shopuser/power/searchTemplates`（返回 parentTempList / customTempList） | `waybill_template` |
| 快递公司 | `POST /api/order/expressList`（**必须 POST**，无业务参数） | `courier` |

- **地址行政区 ID（API-05）**：`getAfterSaleList` 的 `address_list[]` 已包含
  `province_id` / `city_id` / `town_id` / `street_id` 及对应名称，
  取号与 `sendcheck` 的 `address` 可直接复用，无需额外查询。
- **面单账户（API-03）**：`getEbillAccountListByExpress?company=<快递编码>`
  返回 `accounts[]`，字段为驼峰命名：`netCode` / `netName` / `eBillId` /
  `balance`（面单张数，非金额）/ `accountType` / `isDefault`。
  一个快递可返回多个账户，每个账户自带网点编码，
  唯一键取 `(shop_id, courier_code, ebill_id, net_code)`。
  余额不足时取号会失败，界面需提示。
- 刷新时机：首次登录后、店铺配置变更提示、每日首次同步前。
- 失效策略：取号失败且错误指向模板/地址时，强制刷新一次再重试。
- **取号必须使用本店已配置的 `address_id` 与 `template_code`**，不能跨店复用。

### 5.10 多店聚合模块（只读）

**职责**：把售后、商品、库存、资金四类数据按店聚合，产出跨店视图与预警。全部只读。

| 子模块 | 服务模块 | 接口依据 |
|---|---|---|
| 售后聚合 | `service/aftersale.py` | 附录 E |
| 商品 / 库存 | `service/catalog.py` | 附录 D |
| 资金看板 | `service/fund.py` | 附录 F |
| 跨店对账 | `service/reconcile.py` | 第 5.8 节 + 附录 G |

**共同约束**：

1. 只调只读接口，不触发任何写操作
2. 每店一请求；单店失败隔离（会话失效标记 `needs_login`，不影响其他店）
3. **分页基准按接口区分**：订单 `searchlist` 0-based、资金 `query_item` 0-based、
   售后 `after_sale/pc/list` 1-based、库存 `stock/manage/list` 1-based
4. 金额统一整数分（`*_cents`），展示层再换算
5. 上游不可用时回退本地缓存，并标注数据来源（`source: upstream | local_db`）

**刷新策略**：

| 数据 | 频率 | 理由 |
|---|---|---|
| 售后待办 | 高频（5 分钟） | 有时效压力（`status_deadline`） |
| 订单 | 高频（5 分钟） | 取号/发货依赖 |
| 商品 / 库存 | 低频（15 分钟） | 变化慢 |
| 资金账单 | 低频（30 分钟或手动） | 结算按日 |

**统计算法**：

- 售后待办 = 需商家处理的计数之和（待审核 + 待商家收货 + 换货待收 + 各类待审 + 仲裁）
- 对账异常按 `run_id` 分批保留，界面只展示最近一次未处理项

---

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

- `synced`：订单刚从平台同步入库，尚未做取号预检（会话/快递/地址）。
- `pending_label`：预检通过，允许进入取号批次。
- `label_obtained`（已取号未发货）是关键中间态，保证取号与发货可分离、可回滚。
- **打印结果不是订单状态**：打印失败时订单停留在 `label_obtained`，
  失败详情记在 `print_job.status` / `result_detail`，可无限重试；面单保持 `active`。
- `exception` 必须记录 `exception_reason`，人工处理后回到 `pending_label`。
- 面单作废后，`waybills.status=void`，订单回到 `pending_label`。
- **快捷路径**：`batchFetchTrackingNosAndDeliverGoods` 一步完成取号与发货，
  `pending_label` 直接转 `shipped`，跳过 `label_obtained` / `printed`。

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
  cookies       TEXT,                       -- JSON
  device_params TEXT,                       -- JSON：指纹与设备参数
  storage_state TEXT,                       -- Playwright storageState
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
  status          TEXT NOT NULL,
  exception_reason TEXT,
  buyer_nick      TEXT,
  receiver_name   TEXT,
  receiver_phone  TEXT,
  receiver_region TEXT,
  receiver_address TEXT,                     -- 解密后的明文地址
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
  order_id      INTEGER NOT NULL REFERENCES orders(id),
  courier_code  TEXT NOT NULL,
  template_id   TEXT,
  waybill_no    TEXT,
  label_url     TEXT,
  label_payload TEXT,                       -- 打印组件所需完整参数（JSON）
  print_data    TEXT,                       -- 取号返回的加密打印数据（base64）
  sign          TEXT,                       -- 打印签名
  logistics_template_code TEXT,             -- 面单模板编码（取号请求用）
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
  type            TEXT NOT NULL,            -- sync_orders | obtain_label | print | ship | reconcile
  payload         TEXT,
  idempotency_key TEXT UNIQUE,
  status          TEXT NOT NULL DEFAULT 'queued',
                  -- queued | running | success | failed | cancelled
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

-- ⑮ 跨店对账快照（附录 G.4）
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

-- ⑯ 售后聚合（附录 E）
CREATE TABLE aftersale (
  id                  INTEGER PRIMARY KEY,
  shop_id             INTEGER NOT NULL REFERENCES shop(id),
  after_sale_id       TEXT NOT NULL,
  order_no            TEXT,
  type                TEXT,
  status              INTEGER,
  refund_amount_cents INTEGER,
  status_deadline     INTEGER,
  apply_time          TEXT,
  detail_json         TEXT,
  synced_at           TEXT NOT NULL,
  UNIQUE(shop_id, after_sale_id)
);

-- ⑰ 商品快照（附录 D.1）
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

-- ⑱ 库存快照（附录 D.2）
CREATE TABLE stock_snapshot (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  product_id      TEXT NOT NULL,
  total_stock_num             INTEGER,
  spot_stock_num              INTEGER,
  total_occupied_stock_num    INTEGER,
  total_unoccupied_stock_num  INTEGER,
  is_alarming     INTEGER,
  raw_json        TEXT,
  synced_at       TEXT NOT NULL,
  UNIQUE(shop_id, product_id)
);

-- ⑲ 待结算订单（附录 F.1b）
CREATE TABLE fund_unsettled (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  shop_order_no   TEXT,
  sku_order_no    TEXT,
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

-- ⑳ 保证金账户（附录 F.1c）
CREATE TABLE margin_account (
  id              INTEGER PRIMARY KEY,
  shop_id         INTEGER NOT NULL REFERENCES shop(id),
  payable_cents   INTEGER,
  balance_cents   INTEGER,
  level           TEXT,
  raw_json        TEXT,
  synced_at       TEXT NOT NULL,
  UNIQUE(shop_id)
);
```

### 6.3 关键约束

1. 金额一律用**整数分**，禁止浮点。
2. 时间统一 **ISO-8601 UTC 文本**，界面按本地时区展示。
3. 订单唯一性由 `(shop_id, order_no)` 保证。
4. `uq_active_waybill` 保证同一订单同时只有一张有效面单。
5. `tasks.idempotency_key` 保证取号/发货不会重复执行。
6. `raw_json` 保留完整平台报文，用于排障与重放解析。
7. 地址、模板、快递均按 `(shop_id, code)` 唯一，**禁止跨店复用**。
8. 收货地址未解密（`address_encrypted=1` 且 `receiver_address` 为空）的订单不得进入取号批次。

### 6.4 只读聚合与存储说明（DM-06 ~ DM-09）

**只读聚合模块的表**（建表语句见 6.2 ⑮~⑳，字段定义参考对应附录）：

| 表 | 用途 | 字段依据 |
|---|---|---|
| `orders_snapshot` | 跨店对账快照 | 附录 G.4 |
| `aftersale` | 售后聚合 | 附录 E.1 / E.7 |
| `product_snapshot` / `stock_snapshot` | 商品与库存快照 | 附录 D.1 / D.2 |
| `fund_unsettled` / `margin_account` | 资金待结算与保证金 | 附录 F.1b / F.1c |

**会话存储（DM-08）**：以 SQLite `session` 表为唯一来源。

- `session.cookies` 用 **DPAPI**（Windows）加密后存库，密钥随用户账户绑定
- `storage_state`（Playwright 格式）同样加密存储
- **不保留明文 `cookies/` 目录作为运行时依赖**；如需跨机迁移，
  导出包必须整体加密（DPAPI 或口令加密），且不入库、不同步
- 明文会话只存在于内存与 Playwright 临时上下文，进程退出即丢弃

**迁移机制（DM-09）**：使用 **Alembic** 管理表结构变更。

- 初始迁移脚本随第一次实现提交
- 迁移脚本只前进不后退（SQLite 的 ALTER 能力有限，必要时重建表）
- 每次发布前在副本库上演练迁移

---

## 7. 核心流程

### 7.1 登录流程

```
添加店铺 → 打开 Playwright 浏览器 → 人工扫码
        → 检测到登录成功
        → 导出 cookies（用 context.cookies() 取全量；document.cookie 只含 20/37，
          缺 HttpOnly 的 sessionid / sid_tt / uid_tt / sid_guard / ttwid）
        → 保存 storage_state / device_params
        → 探测轻量接口（GET /api/order/tabcnt；未登录返回 code=10008）
        → 获取 __token（页面公共参数）
        → 同步基础数据：发货地址 / 面单模板 / 快递公司
        → shop.status = active
```

**公共参数（API-01）**：

每个请求都要带，来源如下：

| 参数 | 来源 | 有效期 |
|---|---|---|
| `appid` | 固定 `1` | 永久 |
| `aid` | 固定 `4272` | 永久 |
| `_bid` | 按业务域选：`ffa_order`（订单）/ `ffa_goods`（商品）/ `ffa_aftersale`（售后） | 永久 |
| `__token` | 登录后从页面请求 URL 提取，每店一个；随会话文件持久化（`token` 字段） | 跟随会话（约 60 天） |
| `_lid` | 页面会话内递增计数器（12 位数字；见下方证据） | 单次请求 |

- `__token` 在扫码登录成功后即可获取并保存，浏览器外协议直连时从会话文件读取
- **`_lid` 证据（API-01 追加）**：10 个样本（2026-11-24 ~ 11-25）全部 12 位、
  单调递增（`331325398959` → `380214583677`），同一时刻的两次请求相差约 5000。
  与标准时间戳位数不符（秒 10 位 / 毫秒 13 位 / 微秒 16 位），
  判断为**页面会话内的高精度递增计数器**，不是时间戳。
  实现时每请求生成 12 位递增数字；若平台校验严格，改从页面实时读取。

### 7.2 拉单流程

```
触发（手动/定时）
  → 遍历 active 店铺（受全局并发限制）
  → channel.list_pending_orders(shop, cursor) 分页拉取
  → 归一化 DTO
  → upsert orders / order_items（不覆盖本地状态机字段）
  → 更新同步游标
```

### 7.3 取号流程

**打单台提供两种操作，对齐官方交互、二者并存**：

| 操作按钮 | 接口 | 订单终态 | 适用场景 |
|---|---|---|---|
| **打面单** | `batchFetchTrackingNos` | `label_obtained`（已取号，待发货） | 半自动：人工核对面单后再发货 |
| **打单并发货** | `batchFetchTrackingNosAndDeliverGoods` | `shipped`（已发货） | 全自动：单量大、面单模板稳定 |

两种操作共用同一个打单台界面与预检流程，只是最后一步调用的接口不同。
默认推荐「打面单」（保留中间态可核对），「打单并发货」作为快捷选项。

下面是「打面单」的完整流程：

```
人工勾选订单 → 预检（会话 / 地址 / 模板 / 地址解密）
  → GET /api/order/getAftersaleAddressAndLogisticsTemplate
     一次返回 has_aftersale_address / has_template / has_logistics_service / has_printer
  → 地址未解密的先调 /api/order/receiveinfo 解密
     （参数名 order_id，值传 shop_order_id；返回明文，另含 verify_type 风控通道）
  → 按店分组，逐店串行
  → POST /api/order/batchFetchTrackingNos
      { logistics_company_code, logistics_template_code, address,
        transport, shop_order_list, fetch_type, is_davinci: true,
        order_type, version: 1, printer }
  → 成功：写 waybills(active)，订单 → label_obtained
  → 业务拒绝：订单 → exception + 原因（超区 / 模板 / 余额 / 地址）
  → 会话失效：暂停该店并提示重登
```

**取号前置条件（缺一不可）**：

1. 会话有效；
2. 该店已配置默认发货地址（`shop_address.is_default`，平台侧标位为 `is_send_default=1`）；
3. 已选择快递公司，且存在对应面单模板（`waybill_template`）；
4. 收货地址已解密。

第 2~4 项可由 `GET /api/order/getAftersaleAddressAndLogisticsTemplate` 一次性预检
（`has_aftersale_address` / `has_template` / `has_logistics_service`）；
`has_printer` 反映打印组件侧配置，不影响取号本身。

### 7.4 打印流程

```
按「店 + 快递」分组生成打印批次
  → 连接本地打印组件 wss://localhost:13999（HTTP 13888）
  → 发送 { printer, printConfig: "waybill", documents: [...], env, preview }
  → 等待组件回执
  → 成功：waybills.printed，订单 → printed
  → 失败：渲染 100×150 PDF 交系统打印（兜底）
  → 仍失败：标记 print_failed，提示人工打印
  → 重打不重复取号
```

打印消息结构（来自页面实现，见第 10 节）：

```js
{
  printer,
  printConfig: "waybill",
  documents: [{
    documentID,
    standard, custom, copy,
    contents: [{ templateURL, data: { pdf: { url } } }]
  }],
  env, preview, previewType, taskArgs
}
```

### 7.5 发货流程

**主路径（2026-11-25 验证，打单台「已打单」发货）**：

```
界面「确认发货」→ 发货前检查 /api/order/sendcheck
  → 按店分组
  → POST /api/order/batchDeliverGoodsByEES
      { send_type: "3",
        batch_deliver_packages: [{ logistics_company_code, tracking_no }] }
  → 成功：orders.shipped，写审计
  → 失败：退避重试 3 次，仍失败转人工
  → 全程幂等（按「快递编码 + 运单号」去重）
```

- **`send_type` 验证值 `"3"`**（字符串，电子面单场景）
- 按 **运单号** 发货，不需要订单 ID 列表
- 响应按 package 维度返回 `success_package_list` / `fail_package_list`
- 验证样本：订单 `6919920097284206086` 用中通运单 `79209902836406` 发货成功

**备用路径（未验证）**：`/order/torder/batchsend`

```
{ send_type, deliverType: "1" | "2", send_list: [{ order_id, ... }] }
```

可能是订单页发货的路径（与打单台不同）；`deliverType` 语义待已确认。
实现时优先用已验证的 `batchDeliverGoodsByEES`。

### 7.6 对账流程

```
每日定时 → 拉取平台最近 7 天已发货订单
  → 与本地比对
  → 产出 reconcile_findings
  → 界面展示，支持标记已处理 / 导出
```

---

## 8. 异常处理

| 类型 | 例子 | 策略 |
|---|---|---|
| 瞬时故障 | 网络超时、502、限流 | 指数退避重试，最多 3 次 |
| 会话失效 | 返回未登录/验证码页 | 暂停该店队列，提示重登，重登后断点继续 |
| 业务拒绝 | 超区、地址异常、余额不足、模板未配 | 不重试，转 `exception`，人工处理 |
| 数据问题 | 订单已取消/已发货 | 同步最新状态，关闭本地任务 |
| 程序错误 | 解析失败、字段缺失 | 保留 `raw_json`，告警，不重试 |

原则：**单笔失败不阻塞批次；单店失败不影响其他店。**

---

## 9. 风控与合规策略

> 本工具仅用于管理商家**自有店铺**，登录态来自商家本人扫码授权。

| 措施 | 说明 |
|---|---|
| TLS 指纹模拟 | `curl_cffi` `impersonate="chrome"` |
| 独立设备参数 | 每店独立 UA/屏幕/时区/指纹 |
| 每店串行 | 同店请求不并发 |
| 随机节奏 | 请求间隔 300~1200ms 随机 |
| 全局限流 | 默认同时 3 个店 |
| 工作时段 | 可配置仅在工作时间执行定时任务 |
| 操作留痕 | 全部外部调用记审计日志 |

**风险说明**：以上措施降低但不能消除平台风控关联判定风险。若出现连续风控拦截，应立即暂停该店自动化并人工检查。

---

## 10. 打印方案

### A. 复用抖店官方打印组件（首选，协议已验证）

打印组件通过**本地 WebSocket** 通信，端口固定：

| 目标 | HTTP | WSS | 连接地址 |
|---|---|---|---|
| 默认（抖店） | 13888 | **13999** | `wss://localhost:13999` |
| 菜鸟 | 13528 | 13529 | — |
| 拼多多 | 5000 | 18653 | — |

**连接要点（验证 2026-11-25）**：

- HTTPS 页面必须用 **`wss://`**；用 `ws://` 会被组件直接断开连接
- 组件使用自签证书，客户端需跳过证书校验
- Origin 头需为 `https://fxg.jinritemai.com`

**消息协议**：JSON，每条含 `cmd` + `requestID`，响应用同一 `requestID` 回传。

| cmd | 用途 |
|---|---|
| `getPrinters` | 查询打印机列表 |
| `print` | 提交打印任务 |
| `startAutoPrint` | 开启自动打印 |
| `notifyPrintResult` / `notifyTaskResult` / `notifyDocResult` | 组件主动推送的结果通知 |

**getPrinters（验证通过）**：

```json
// 请求
{"cmd":"getPrinters","requestID":"test_2","version":2}

// 响应
{"cmd":"getPrinters","defaultPrinter":"Microsoft Print to PDF",
 "printers":[{"name":"Microsoft Print to PDF"}],"requestID":"test_2"}
```

**print 消息结构**（源码字段 + 验证）：

```js
{
  cmd: "print",
  requestID: "<唯一ID>",
  version: 2,
  isOpen: false,
  previewType: "pdf",
  task: {
    taskID: "<同 requestID>",
    preview: false,
    printConfig: "waybill",
    printer: "<打印机名称>",
    documents: [{
      documentID: "<同 requestID>",
      contents: [{
        templateURL: "<面单模板 XML 的 URL>",
        data: { pdf: { url: "<渲染数据/PDF 的 URL>", cookie: "" } }
      }]
    }]
  }
}
```

**验证结果（2026-11-25）**：

- 组件接受消息并回 `{"cmd":"print","requestID":"...","status":"success"}`
- 随后推 `notifyPrintResult`，其 `printStatus[].detail` 是 base64 编码的渲染错误
- 解码后发现：**模板是 EJS（XML + 嵌入式 JS）**，组件会执行模板代码，
  需要正确的 `_data`（订单数据）才能渲染
- 传无效 PDF URL 时，模板在 `_data.receiverInfo` 处报 TypeError

**关键边界**：`print_data`（取号响应返回的 base64）不是 PDF，而是**加密的打印数据**。
把它转换成 `documents` 结构的那段逻辑在前端 SDK 的 `mW()` 函数里，
是打印链路唯一还没搞清的一环。

**MVP 建议**：

- 方案 A'：取号后不自己打印，用抖店页面「补打面单」（方案 C 变体）
- 方案 A''：分析 `mW()` 的数据转换，完整接管打印
- 方案 B：自渲染 100×150 PDF，不依赖组件模板

实现步骤：

1. 启动时用 `getPrinters` 探测组件是否可用，并缓存打印机列表
2. 取号成功后，用响应里的 `print_data` 组装打印任务
3. 发送 `print` 并等待 `notifyPrintResult` 回执；超时视为失败
4. 失败 → 方案 B；仍失败 → 标记 `print_failed`

优点：模板、尺寸、快递要求与商家现状完全一致。
注意：组件版本可能变化，需记录版本号，并可在启动时做一次自检打印（可选）。

**多店打印调度**：打印机是本机资源，所有店铺共享同一列表。
建议做「店铺 × 默认打印机」配置，避免多店同时打单时抢占同一台打印机。

### B. 自渲染面单 + 系统打印（兜底）

- 将面单数据渲染为 100×150mm PDF，交 Windows 打印子系统。
- 优点：不依赖官方组件。
- 缺点：模板需自行适配，可能与快递要求有偏差。

### C. 仅取号，手动打印（保底）

- 软件只负责取号与发货回传，打印由用户在抖店后台手动完成。
- 作为兜底，不影响全流程闭环。

**部署位置**：软件最终运行在**出单机**（登录、打印均为本机动作）。开发在开发机完成，交付时整体拷贝。

**开发机环境**：已安装官方打印组件（CloudPrintClient.exe），
13888/13999 端口正常监听，`getPrinters` 验证通过（当前仅 1 台虚拟打印机
`Microsoft Print to PDF`）。真实出单机需验证实际热敏打印机的打印效果。

---

## 11. 技术栈与目录结构

> 定位：**完整的抖店多店铺后台管理系统**（不是单点履约脚本）。
> 前端只做界面与交互，所有抖店交互由本机后端代理完成。

### 11.1 前端技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 框架 | React 19 + TypeScript | |
| 构建 | Vite | 开发 `localhost:5173`，生产构建后由后端托管 |
| 样式 | Tailwind CSS 4 + Arc `foundation.css` | Arc 的设计令牌（`--background` / `--surface` / `--foreground` 等） |
| 组件库 | **Arc Free（122 组件）+ Arc Pro（121 组件）** | 个人组件库 `uiarc-system`，本地已就绪 |
| 区块 | **Arc Pro blocks（130+）** | 直接复用的页面级区块 |
| 模板起点 | **`arc-crm`（Pro，20 个文件）** | 完整 CRM 模板，可作为 app shell 参考 |
| 图表 | Free：`bar-chart` / `line-chart` / `donut-chart` / `sparkline` / `gauge` / `treemap`；Pro：`funnel-chart` / `radar-chart` / `race-bar-chart` | |
| 数据层 | TanStack Query（服务端状态）+ 局部 useState | 不引入 Redux 类重方案 |
| 路由 | React Router | |
| 表格 | `sortable-data-table`（Free） | 订单/商品/库存列表通用 |

### 11.2 后端技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.12 | |
| 框架 | FastAPI + uvicorn | 接口 + 静态资源托管 |
| HTTP 协议层 | `curl_cffi`（Chrome TLS 指纹） | 浏览器外调抖店接口 |
| 签名执行（按需） | `py_mini_racer`（V8） | 仅当写接口强制 `a_bogus` 时启用 |
| 登录/兜底 | Playwright（Python） | 扫码登录、导出全量 cookie |
| 打印 | `websockets` 连接本地打印组件（`wss://localhost:13999`） | |
| 存储 | SQLite（WAL 模式） | 单机 5~50 店足够 |
| 调度 | asyncio + 每店串行队列 | 不引入重框架 |
| 打包 | 启动脚本；后续可做 PyInstaller/Nuitka | |

### 11.3 页面 → Arc 组件映射

| 页面 | Arc 组件 / blocks | 模块依据 |
|---|---|---|
| **App Shell**（侧边栏 + 顶栏） | `workspace-sidebar` 或 `sidebar-rail`（Pro） | — |
| 登录 | `login-split`（Pro）/ `sign-in`（Free block） | 7.1 登录流程 |
| 首页仪表盘 | `metrics-dashboard`（Pro）+ `metric-card` + `bar-chart` | 多店经营概览 |
| 订单管理 | `sortable-data-table` + `filter-toolbar` + `pagination` | 附录 C |
| 打单台 / 发货台 | `sortable-data-table` + `hold-to-confirm`（危险操作确认） | 7.3 / 7.5 |
| 售后聚合 | `inbox-triage`（Pro）+ `tabs` + `timeline` | 附录 E |
| 商品管理 | `sortable-data-table` + `product-listing`（Pro） | 附录 D |
| 库存管理 | `sortable-data-table` + `usage-meter` + `range-histogram-slider` | 附录 D |
| 资金看板 | `billing-overview`（Pro）+ `revenue-explorer`（Pro）+ `wallet-card` | 附录 F |
| 跨店对账 | `sortable-data-table` + `empty-states`（Free block） | 附录 G |
| 店铺 / 设置 | `settings-page`（Pro）+ `team-members`（Pro）+ `two-factor-setup` | 5.1 会话管理 |
| 通知 / 异常 | `notification-center` + `toast-stack` | 8 异常处理 |

**Arc 使用约定**：Arc 优先于自建；Free 优先于 Pro；同一控件不混用两套库；
Pro 组件API 以源码导出的 TypeScript interface 为准，不猜 props。

### 11.4 目录结构

```
doudian-multishop-admin/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口、静态资源托管
│   │   ├── api/                 # shops / orders / aftersale / fund / reconcile / labels / shipping
│   │   ├── service/             # 业务编排：session_manager / base_data / order_sync / labeling / printing / shipping / reconcile
│   │   ├── adapter/             # 外部世界的薄封装，无业务逻辑
│   │   │   ├── doudian/         # client.py / endpoints.py / error_codes.py / enums.py / signing/（按需启用）
│   │   │   ├── print/           # 打印组件 WebSocket 客户端（端口常量 ports.py）
│   │   │   └── browser/         # Playwright 登录与兜底渠道
│   │   ├── store/               # SQLite 连接、迁移、仓储
│   │   ├── domain/              # 状态机、枚举、纯函数，无 IO
│   │   └── shared/              # 跨模块工具（必须配单测）
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/              # shadcn 基础件
│   │   │   ├── arc/             # Arc Free / Pro 源码（安装进去，不外部 import）
│   │   │   └── custom/          # 项目组合层（跨模块拼装写这里）
│   │   ├── pages/               # 仪表盘 / 订单 / 打单 / 售后 / 商品 / 库存 / 资金 / 对账 / 设置
│   │   ├── lib/                 # api client、格式化、hooks
│   │   └── main.tsx
│   ├── tailwind.config.ts
│   └── package.json
├── artifacts/                   # 接口记录样本、面单样本（不入库）
├── cookies/                     # 每店会话（不入库、不提交）
├── docs/                        # 设计文档与工程规范
└── scripts/                     # 启动、备份、部署脚本
```

> 目录命名以 `engineering-rules.md` 2.2 为准；本文档其余章节出现的
> `service/`、`adapter/`、`store/`、`domain/` 均对应此结构。

### 11.5 Arc 安装

```bash
# Free 组件
npx shadcn@latest add @uiarc/<id>

# Pro 组件（本地源码可直接复制到 components/arc）
npx shadcn@latest add @uiarc-pro/<id>
```

- 组件库源码在 `C:\Users\Administrator\.claude\skills\uiarc-system\`（`vendor/uiarc`、`vendor/uiarc-pro`）
- 组件目录索引：`references/catalog-free.md`、`references/catalog-pro.md`
- 不要把 uiarc-system 仓库作为运行时 import 路径，安装进项目后从 `components/arc` 引用
- 不改 `vendor/` 源码来适配项目；需要调整时在 `components/custom` 里组合

---

## 12. 测试策略

| 层级 | 内容 | 方式 |
|---|---|---|
| 单元测试 | 状态机流转、幂等键、DTO 解析、地址校验 | pytest，使用 `raw_json` 真实样本 |
| 集成测试 | 渠道接口 → 服务层 → 数据库 | 录制回放：mock 抖店响应 |
| 契约测试 | `protocol` 与 `browser` 两个渠道行为一致 | 同一组用例跑两个实现 |
| 真实环境验证 | 拉单已在浏览器外验证；取号/发货待真验证试订单 | 用测试店铺真实执行 |
| 手工验收 | 2 个店各 1 单全流程；错单/掉线/作废场景 | 人工按验收清单执行 |

**重点测试项**：

- 重复点击"取号"不会产生两张有效面单。
- 重复点击"确认发货"不会重复发货。
- 会话失效时只影响该店。
- 面单作废后订单能回到 `pending_label`。
- 对账能发现人为制造的三类异常。
- 地址未解密的订单不会进入取号批次。
- 模板/地址缺失时，取号前即被拦截。
- 打印组件未启动时，订单不会被标记为已打印。

---

## 13. 里程碑

| 阶段 | 交付物 | 状态 |
|---|---|---|
| **M0 技术验证** | 拉单接口已跑通（浏览器外免签名）；只读接口 第一轮验证 7 项已验证；打印协议已识别；取号/发货写接口待真实订单验证 | **部分完成** |
| **M1 登录 + 基础数据 + 拉单** | 扫码登录、Cookie 导出、地址/模板/快递同步、订单入库 | 待开始 |
| **M2 订单池 + 地址解密 + 取号** | 聚合界面、筛选勾选、批量取号 | 待开始 |
| **M3 打印** | 官方组件 `wss://localhost:13999` 接通；PDF 兜底 | 待开始 |
| **M4 发货前检查 + 发货 + 对账** | `sendcheck`、`batchDeliverGoodsByEES`、每日对账 | 待开始 |
| **M5 多店聚合（只读）** | 售后 / 商品 / 库存 / 资金四类聚合服务与数据表 | 待开始 |
| **M6 前端后台** | Arc 组件搭完整后台，九个页面（见 11.3） | 待开始 |
| **M7 打磨** | 掉线重登、异常处理、日志、限速、备份、演练模式 | 待开始 |

---

## 14. 验收标准

1. 至少 **2 个不同主体店铺**各完成 1 单全流程（拉单 → 取号 → 打印 → 发货）。
2. 取号成功率 > 98%（分母 = 已进入取号批次且预检通过的订单；超区/地址异常/余额不足等业务拒绝类不计入分母）。
3. 连续点击"取号"/"确认发货"各 5 次，无重复面单、无重复发货。
4. 手动使某店会话失效，系统在 5 分钟内标记 `needs_login`，其他店不受影响。
5. 对账能发现人为制造的三类异常。
6. 所有外部调用均可在审计日志中追溯。
7. 软件在出单机上双击启动即可使用，无需命令行操作。
8. 基础数据（地址 / 模板 / 快递）能自动同步，并在取号时正确匹配到本店配置。
9. 加密收货地址能自动解密，面单上打印出完整明文地址。
10. 打印组件未启动时，界面明确提示，且**不会**把订单标记为已打印。
11. 演练模式（dry-run）下不产生任何真实取号或发货请求。

---

## 15. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 写接口强制签名 | 取号/发货需分析 bdms SDK | 先做双对照验证；必要时启用签名引擎或降级浏览器渠道 |
| 平台风控关联判定 | 账号受限 | 限速、独立指纹、工作时段、操作留痕；异常即停 |
| 官方打印组件接口变化 | 打印失败 | 保留 PDF 兜底（方案 B）与手动打印（方案 C） |
| 地址解密接口变更 | 无法打印明文地址 | 保留原始密文；解密失败转 `exception` 并提示 |
| 抖店后台改版 | 接口失效 | `adapter/doudian/` 与 `adapter/doudian/signing/` 隔离，替换适配器 |
| 登录频繁过期 | 运维负担 | 重登流程简化（一键弹窗）+ 到期提醒 |
| 开发机无打印机/打印组件 | 无法本地验证打印 | 打印在出单机验证；开发期用 dry-run + PDF 预览 |

---

## 16. M0 技术验证清单

> 在写正式代码之前完成。任何一项失败，先调整方案再继续。

- [x] 登录抖店并导出 cookie（`document.cookie` 覆盖只读接口所需；建议 `context.cookies()` 取全量）
- [x] 用 `curl_cffi` + `impersonate="chrome"` 在浏览器外访问需登录接口（订单列表，200）
- [x] 确认 `a_bogus` / `msToken` / `verifyFp` 非只读接口鉴权必需（三组对照）
- [x] 拉取待发货订单列表（含完整响应结构）
- [x] 识别取号接口与请求体（`/api/order/batchFetchTrackingNos`）
- [x] 识别发货接口与请求体（`/api/order/batchDeliverGoodsByEES`，按运单号发货）
- [x] 探明官方打印组件协议（`wss://localhost:13999`）
- [x] 请求/响应样本落盘（`artifacts/`，不入库）
- [x] 为真实订单取号（2026-11-25，运单号 `79209902836406`）
- [x] 执行真实发货回传（2026-11-25，订单状态转「已发货」）
- [x] 确认 `send_type` 枚举值（电子面单 = `"3"`）
- [x] 确认写接口是否强制签名（批量备注 / 取号 / sendcheck / 发货 均不强制）
- [ ] 在出单机验证打印组件（开发机已验证 `getPrinters`；真实热敏打印机待出单机验证）

### 第一轮验证补充验证（2026-11-24 完成）

- [x] 发货地址 / 面单模板 / 快递公司 三个基础数据接口的路径、方法与返回结构
- [x] 收货地址解密接口的参数约定与明文返回
- [x] 会话探测接口选型（`tabcnt` 可用，`session_check` 不可用）
- [x] 订单列表分页边界（0-based，pageSize=100 可用）
- [x] 上述接口均验证为**浏览器外免签名**可调
- [ ] 取号模板参数（`customTempCode` vs `parentTempCode`）—— 需真实取号确认

---

## 附录 A：接口清单（只读已验证 / 写接口待定）

> 详细证据：`artifacts/`（本地留存，不入库）

### A.0 验证状态总览（2026-11-24）

| 模块 | 只读接口 | 写接口 | 数据样本 |
|---|---|---|---|
| 会话 | ✅ 探测 / cookie 导出 | — | ✅ |
| 订单 | ✅ 列表 / 筛选（8 项）/ 计数 / 地址解密 | ✅ 取号 / 发货前检查 / 发货 / 批量备注；⏳ 改物流 / 面单作废 | ✅ 18 单 + 新店 529 单 |
| 商品 | ✅ 列表 / 计数 / 分组 / 类目树 | ⏳ 创建提交 | ✅ 6 个商品 |
| 库存 | ✅ 列表 / 仓库列表 | ⏳ 库存修改 | ✅ |
| 售后 | ✅ 列表 / 计数 / 详情 | ⏳ 同意退款 / 填运单号 / 延长收货 | ✅ 8 单 |
| 资金 | ✅ 待结算 / 账单 / 保证金 | — | ⚠️ 待结算 7 条；账单 0 条 |
| 对账 | ✅ 基于订单列表 | — | ✅ 18 单 |
| 店铺 | ✅ 画像 / 管理人 / 绑定账号 | — | ✅ |
| 打印 | — | ⏳ 组件协议（wss://localhost:13999） | ❌ 需出单机 |

**仍未确认的三项（客观条件卡住，非技术难点）**：

1. 商品创建提交的请求体 —— 需真实创建一个测试商品
2. 打印组件实际回执 —— 需装了官方客户端的出单机
3. 资金账单金额字段 / 保证金金额单位 —— 样本店账单为 0、保证金为 0，需有数据的店校准

### A.1 只读接口

| 用途 | 方法 | 路径 | 备注 |
|---|---|---|---|
| 待发货订单 | GET | `/api/order/searchlist?tab=stock_up&order_status=stock_up&scene=1` | page **0-based**；pageSize 100 验证可用 |
| 打单台列表 | GET | `/api/order/searchCombineOrder` | |
| 状态计数（会话探测） | GET | `/api/order/tabcnt` | **未登录返回 `code:10008`**，推荐作健康探测 |
| 快递公司 | **POST** | `/api/order/expressList` | GET 返回 `404 路由错误`；无业务参数 |
| 发货地址列表 | GET | `/shopuser/tshopuser/getAfterSaleList` | page **1-based**；`is_send_default=1` 为默认发货地址 |
| 面单模板列表 | GET | `/shopuser/power/searchTemplates` | parentTempList / customTempList |
| 取号前置检查 | GET | `/api/order/getAftersaleAddressAndLogisticsTemplate` | 返回 4 个布尔位 |
| 包裹列表 | GET | `/api/order/searchPackageList` | |
| 包裹配置 | GET | `/api/order/getPackageConfig` | |
| 合单灰度 | GET | `/api/order/queryCombineOrderGrayShopStatus` | |
| 公告 | GET | `/api/order/getNotice` | |
| 收货信息解密 | GET | `/api/order/receiveinfo` | 参数名 `order_id`，**值传 `shop_order_id`**；返回明文 |
| 店铺资质画像 | GET | `/center/qualification/shop/info` | 资质 ID / 地址 / 类目 / 审核状态 |
| 店铺管理人 | GET | `/byteshop/shopuser/getAdminV2` | 手机号脱敏 |
| 绑定账号 | GET | `/byteshop/accountbind/getbindlist` | |
| 菜单 | GET | `/byteshop/menu/list/v2` | |
| 登录校验 | GET | `/ecomauth/loginv1/session_check` | ⚠️ **不可用**：无 cookie 也返回 `check_code:0` |

### A.2 写接口（部分已验证）

> 批量备注、取号、发货前检查、发货（打单台）四项已于 2026-11-25 完成真实调用验证，
> 请求体结构与响应见下方各小节。其余接口（订单页发货、改物流、售后处理等）仍待验证。
>
> 未验证接口的必查项：
> 1. 是否强制 `a_bogus` / `msToken` 签名（已验证的 4 个写接口均不强制）
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
| 发货（订单页） | POST | `/order/torder/batchsend` | ⏳ 待定（打单台不走这条） |
| 取号+发货一体 | POST | `/api/order/batchFetchTrackingNosAndDeliverGoods` | 🔶 源码发现，未验证 |
| 改物流 | POST | `/order/torder/modifyLogistic` | ⏳ 待定 |
| 售后同意退款 | POST | 未抓（按钮 code `refund_audit`） | ⏳ 待定 |
| 售后代填运单号 | POST | 未抓（按钮 code `fill_logistics`） | ⏳ 待定 |
| 售后延长收货 | POST | 未抓（按钮 code `exchange_logistics_extend`） | ⏳ 待定 |
| 商品创建提交 | POST | 未抓（表单提交，需建测试商品） | ⏳ 待定 |
| 面单作废 | POST | 未抓 | ⏳ 待定 |
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

**取号前置链路（验证顺序）**：

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
**不是** M0 笔记里记录的 `/order/torder/batchsend`（后者可能是订单页发货的路径，待对比）。

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

1. **`send_type: "3"`（字符串）** —— 设计文档 7.5 一直标「待已确认」的枚举值，
   电子面单发货场景下就是 `"3"`
2. **按「运单号」发货**，不需要订单 ID 列表 —— 只要 `快递编码 + 运单号`
3. 响应按 **package 维度**返回成功/失败（一个包裹可含多单）
4. 请求体极简，无 `deliverType`/`send_list` 等字段（与 batchsend 的设计不同）

**完整发货链路（验证）**：

```
1. POST /api/order/sendcheck                 发货前检查（可选，界面会先调）
2. POST /api/order/batchDeliverGoodsByEES    按运单号发货
```

### A.2.5 取号 + 发货一体（源码结构已知，未验证）

打单台「待打单」行的「**打单并发货**」按钮调用：

```
POST /api/order/batchFetchTrackingNosAndDeliverGoods
Content-Type: application/json
```

**请求体**（源码 2245\.\*.js 第 3881-3894 行）：

```json
{
  "send_type": "3",
  "fetch_type": 0,
  "logistics_company_code": "zhongtong",
  "logistics_template_code": "C1m77ow4c2qrrd",
  "address": { 同取号 },
  "transport": "{\"expType\":\"defaultProductType\"}",
  "...dynamicValues 展开",
  "added_services": [],
  "shop_order_list": [ 同取号 ],
  "is_davinci": true,
  "version": 0,
  "printer": "<打印机名>"
}
```

即：**取号字段 + `send_type`（发货枚举）+ `added_services`**。

**价值**：一次请求完成「取号 + 发货」，省掉 `batchFetchTrackingNos` + `batchDeliverGoodsByEES` 两次调用，
也避免了中间态（已取号未发货）。

**未验证原因**：需要一笔待发货订单；样本店当前待打单为 0。
**注意**：该接口一次完成不可逆的发货动作，验证时应先用测试单确认响应结构。

**写接口的一般性判断**：抖店只读接口全部免签名（已验证 20+ 个），
写接口属于未知区域。若某写接口强制签名，方案是用 Playwright 在页面内执行 fetch
（浏览器渠道兜底），业务代码不需改动。

### A.3 页面路径

| 功能 | 路径 |
|---|---|
| 订单管理 | `/ffa/morder/order/list` |
| 打单发货 | `/ffa/morder/logistics/ewaybill-delivery` |
| 手工打单 | `/ffa/morder/logistics/ewaybill-delivery-manual` |
| 电子面单 | `/ffa/logistics-project/eBill/landing` |
| 发货 | `/ffa/morder/logistics/delivery` |
| 批量发货 | `/ffa/morder/logistics/combine-delivery` |
| 批量导入发货 | `/ffa/morder/delivery/upload` |

### A.4 关键结论

- 只读接口：Cookie + `__token` 即可（浏览器外已验证 200）；第一轮验证 7 项全部通过。
- `a_bogus` / `msToken` / `verifyFp`：风控打分参数，只读接口非必需。
- 会话探测用 `/api/order/tabcnt`（未登录 = `code:10008`）；
  `/ecomauth/loginv1/session_check` 不可用（无 cookie 也返回 `check_code:0`）。
- 分页基准不统一：`searchlist` 为 0-based，`getAfterSaleList` 为 1-based。
- 列表返回的收货信息为**脱敏值**（`辛*` / `1**********`），取号/打印前必须调 `receiveinfo` 解密。
- 写接口鉴权强度：待真实订单验证。
- 打印：官方组件本地 WebSocket（默认 13999）。

---

## 附录 B：能力分级

### B.1 MVP 必修（研究已暴露、设计原缺）

1. 发货地址列表
2. 面单模板列表
3. 快递公司列表
4. 收货地址解密
5. 发货前检查
6. 打印组件协议
7. 写接口鉴权验证

### B.2 阶段二（低成本高价值）

| 能力 | 依赖 |
|---|---|
| 物流轨迹跟踪 | `logistics_status` / `latest_logistic_info` |
| 异常订单看板 | 多 tab 查询 + `exp_ship_time` |
| 一键改物流 | `/order/torder/modifyLogistic` |
| 批量备注 | `/api/order/addremarks` |
| 面单作废/重打 | 作废接口 + 重取号 |
| 合单发货 | `searchCombineOrder` / `searchPackageList` |
| 打印自检与重试 | 13999 端口探测 + 回执 |
| 通知通道 | 掉线/打印失败/超时未发 |
| 电子面单余额 | `/ffa/logistics-project/eBill/detail/list` |
| 多店经营汇总 | `tabcnt` + `searchlist` 聚合 |

### B.3 工程能力

| 能力 | 说明 |
|---|---|
| 会话健康看板 | 每店登录状态 + 一键重登 |
| 演练模式 | 不产生真实写请求 |
| 断点续跑 | 崩溃后可恢复中间态 |
| 每日对账 | 本地 vs 平台三类异常 |
| 本地备份 | SQLite 每日快照 |
| 接口探活 | 抖店改版第一时间发现 |
| 操作审计 | 全链路可追溯 |
| 限速与工作时段 | 降低风控关联风险 |

---

## 附录 C：订单管理页 UI → 接口字段映射（2026-11-24 验证）

> 目的：把抖店「订单管理」页面上可见的每一块内容，映射到可编程的数据来源。
> 结论：**展示层零缺口**；筛选参数 6/8 已确认；写操作类见 B 档。

### C.1 顶部 tab 计数

单接口覆盖全部 tab：`GET /api/order/tabcnt?tabcnt_version=v1&tab=all`

| UI tab | 响应字段 | 样本值 |
|---|---|---|
| 全部订单 | `all` | 18 |
| 待支付 | `unpaid` | 0 |
| 待发货 | `stock_up` | 0 |
| 24h需发货及揽收 | `exp_ship` | 0 |
| 超时未发货及揽收 | `ship_delay` | 0 |
| 已发货 | `on_delivery` | 6 |
| 售后中 | `in_aftersale` / `have_aftersale` | 2 |
| 已完成 | `received` | 1 |
| 已关闭 | `closed` | 11 |

附加可用字段（UI 未直接展示，做看板有价值）：
`under_sure`（待确认）、`handling`（处理中）、
`ship_and_logistics_delay` / `exp_ship_and_logistics`（发货+揽收超时组合）、
`cnt_report`（分组统计子对象）。

### C.2 订单列表字段分组（`searchlist` 单条 116 字段）

| UI 区域 | 关键字段 |
|---|---|
| 订单标识 | `shop_order_id`、`order_id_for_show`、`user_id` |
| 订单状态 | `order_status`（数字）、`order_status_info.order_status_text`、`order_type_desc` |
| 商品信息 | `product_item[]`：`item_order_id`、`product_id`、`product_name`、`sku_spec[]`、`img`、`quantity` |
| 金额（整数分） | `pay_amount`、`total_goods_amount`、`post_amount`、`promotion_amount`、`actual_receive_amount_int`（商家收入） |
| 时间 | `create_time`、`pay_time`、`exp_ship_time`（承诺发货）、`ship_time`、`receipt_time` |
| 收货信息 | `receiver_info`（**脱敏**：`辛*` / `1**********`）、`address_tag`、`receive_type` |
| 物流 | `latest_logistic_info.tracking_no`、`company_code`、`track`；`way_bill_url`；`logistics_status` |
| 买家 | `user_nickname`（脱敏）、`user_is_auth` |
| 操作按钮 | `operation_actions`、`action_map`、`button`（前端据此渲染按钮，可用于判断可用动作） |

**注意**：`receiver_info` 是脱敏值不是密文；要拿明文（打印面单必需）调
`GET /api/order/receiveinfo?order_id=<shop_order_id>`。

### C.3 筛选项 → 参数映射

| UI 筛选项 | 接口参数 | 验证 |
|---|---|---|
| 订单编号 | `order_id` | ✅ 已确认 |
| 物流单号 | `tracking_no` | ✅ 验证命中 1 单 |
| 达人ID | `author_id` | ✅ 验证过滤生效 |
| 搜索买家 | `buyer` | ✅ 验证过滤生效 |
| 承诺发货时间 | `exp_ship_time_start` / `exp_ship_time_end` | ✅ 验证 total 18→14 |
| 发货时间（接口支持，UI 未展示） | `ship_time_start` / `ship_time_end` | ✅ 验证 total 18→6 |
| 订单状态 | `order_status` + `tab`（**字符串枚举**） | ✅ 六值全部验证与 `tabcnt` 一致 |

**订单状态的枚举**（重要：筛选参数是**字符串**，而订单数据里的 `order_status` 字段是数字）：

| UI 选项 | `tab` / `order_status` 值 | 验证订单数 | tabcnt 对照 |
|---|---|---|---|
| 全部 | `tab=all`（order_status 留空） | 18 | 18 ✅ |
| 待支付 | `unpaid` | 0 | 0 ✅ |
| 待发货 | `stock_up` | 0 | 0 ✅ |
| 已发货 | `on_delivery` | 6 | 6 ✅ |
| 已完成 | `received` | 1 | 1 ✅ |
| 已关闭 | `closed` | 11 | 11 ✅ |

> ⚠️ 两套枚举不要混用：
> - **筛选参数**用字符串（`unpaid` / `stock_up` / `on_delivery` / `received` / `closed`）
> - **订单响应里的 `order_status`**是数字（3=已发货、4=已关闭、5=已完成）
> - 对账判定（附录 G.2）用的是数字口径，筛选用的字符串口径，两者需在代码里分别建模
| 商品ID | **`product`** | ✅ 验证：`product=<商品ID>` → total 18→14 |
| 商品名称/商家编码 | **`product_name_code`** | ✅ 验证：选中联想商品后 → total 14 |

**商品ID 筛选验证记录**（2026-11-24）：页面手动输入商品ID 后发出
`product=3853991770601947295`，返回 14 单且全部包含该商品，确认参数名为 `product`
（此前试过的 `product_id` / `product_ids` / `product_id_list` 等 25 个候选名均无效）。

**商品名称/商家编码 的机制**（验证）：

1. 输入框输入文字 → 触发联想接口
   `GET /shopuser/power/searchProductDigest?productNameOrId=<输入>`
2. 从下拉选中某个商品后 → 查询请求带上 **`product_name_code=<商品ID>`**
3. 也就是说：UI 上写的是「商品名称/商家编码」，实际传的是**选中商品的商品ID**

补充：该店 6 个商品的 `out_product_id`（商家编码）**全部为空**，
所以「按商家编码筛选」在本店无法产生真实数据，机制以商品ID等价处理。

**时间筛选的完整参数形态**（页面实际发出）：

```
compact_time[select]=create_time_start,create_time_end
```

`compact_time[select]` 声明时间用哪两个字段，再配合对应起止参数；
未选具体时间时该参数常驻但不生效。

另需确认：UI 提示「多个单号用 / 空格隔开」时，接口是接收拼接字符串还是数组
（尚未测多值场景）。

### C.4 批量操作按钮 → 接口/页面

| UI 按钮 | 类型 | 目标 | 状态 |
|---|---|---|---|
| 批量备注 | 写接口 | `POST /api/order/addremarks` | ✅ 已验证（A.2.1） |
| 批量导入发货 | 页面 | `/ffa/morder/delivery/upload` | 跳转 |
| 打单发货 | 页面 | `/ffa/morder/logistics/ewaybill-delivery` | 跳转 |
| 在线寄件 | 页面 | 菜单内跳转 | 未识别 |
| 批量采购 | 写接口 | 未识别 | ❌ |
| 批量上传序列号 | 写接口 | 未识别 | ❌ |
| 表格配置 | 配置 | `GET /api/order/getPackageConfig?config_key=...` | 已识别 |

### C.5 实现注意

1. `page` 从 0 开始；`pageSize` 验证 100 可用（更大会被截断，需验证上限）。
2. 筛选值为空时浏览器会带上空占位参数（`product_spec_desc=`、`search_condition_list=` 等），
   协议层可以省略，但保留空串更贴近页面行为。
3. 多店聚合时，`tabcnt` 与 `searchlist` 需按店分别拉取后在本地合并（跨店无统一接口）。
4. `operation_actions` / `action_map` 可用于判断某订单能否执行某操作，
   避免在界面渲染不可用按钮。

---

## 附录 D：商品 / 库存模块 UI → 接口映射（2026-11-24 验证）

> 与附录 C 同源验证，覆盖「商品管理 / 商品创建 / 库存管理」三个页面。
> 结论：**展示层零缺口**；商品创建止步于表单配置（发布为写接口，未验证）。

### D.1 商品管理（`/ffa/g/list`）

#### 列表与计数

| 用途 | 方法 | 接口 | 备注 |
|---|---|---|---|
| 商品列表 | GET | `/product/tproduct/list` | **单条 192 字段**；`page` 0-based |
| 状态计数 | GET | `/product/tproduct/aggsProductCount` | 见下表 |
| 商品分组 | GET | `/product/tproduct/getProductGroupList` | `pageSize=100` |
| 类目树 | GET | `/product/tproduct/categoryOptionsN?cid=0` | 逐级下钻 |
| 经营指标 | GET | `/product/tproduct/listTractionItems` | 曝光/点击等 |
| 整改信息 | GET | `/product/tproduct/rectifyInfo` | 违规整改 |
| 质量分诊断 | GET | `/product_diagnose/tproduct/get_diagnose_quality_score_version` | 商品诊断 |
| 灰度开关 | GET | `/product/tproduct/isInAllowlist` | 一次性查大量 feature flag |

#### 状态计数（`aggsProductCount`）

| 字段 | 含义 | 样本 |
|---|---|---|
| `onsale` | 在售 | 6 |
| `audit` | 审核中 | 0 |
| `unpass` / `unpass_new` | 未通过 | 0 |
| `draft` | 草稿 | 0 |
| `forbidden` | 禁售/下架 | 0 |
| `sell_out_new` | 售罄 | 0 |

#### 列表筛选参数（`product/tproduct/list`）

`page`（0-based）、`pageSize`、`tab`（`onSale` 等）、`check_status`、`status`、
`draft_status`、`group_id`、`sku_type`、`supply_status`、`comment_percent`、
`order_field`、`sort`、`business_type`、`is_online`、`from_mng`、
`need_auto_rectify_info`、`need_pay_no_stock_skus`

#### 商品条目关键字段（192 中选摘）

| 分组 | 字段 |
|---|---|
| 标识 | `product_id`、`publish_id`、`out_product_id` |
| 名称图片 | `name`、`img`、`pics`、`product_url`、`product_url_for_copy` |
| 状态 | `status`、`check_status`、`tab`、`put_status`、`is_not_for_sale` |
| 价格 | `market_price`、`price_lower`、`price_higher`、`discount_price` |
| 库存 | `stock_num`、`self_sell_stock_num`、`promotion_stock_num`、`lock_stock_num`、`channel_stock_num` |
| SKU | `skus[]`、`spec_id`、`sku_price_read_only` |
| 类目 | `first_cid`、`second_cid`、`third_cid`、`category_leaf_id`、`category_name` |
| 运营 | `sell_num`、`sell_num_30d`、`collect_num`、`comment_num`、`comment_percent`、`quality_score` |
| 操作 | `operations`（可用操作列表，用于按钮渲染） |

### D.2 库存管理（`/ffa/morder/stock-manage/list`）

| 用途 | 方法 | 接口 | 备注 |
|---|---|---|---|
| 库存列表 | **POST** | `/stock/manage/list` | ⚠️ **`page` 1-based**；`_bid=ffa_order` |
| 仓库列表 | GET | `/stock/index/warehouse_list` | 多仓 |
| 操作权限 | GET | `/stock/manage/op_control` | 可否改库存 |
| SKU 诊断 | POST | `/stock/manage/sku_stock_diagnose` | 库存健康 |
| 增量排除 | GET | `/stock/increase/exclude` | 增量配置 |
| 编辑黑名单 | GET | `/stock/index/edit_black` | 不可编辑项 |

**请求体**（已验证）：

```json
{"page":1,"pageSize":10,"sort":0,"page_size":10,
 "appid":1,"__token":"...","_bid":"ffa_order","aid":4272,"_lid":"..."}
```

**响应顶层统计**：

| 字段 | 含义 |
|---|---|
| `total` | 商品数（样本 6） |
| `stock_alarm_cnt` | 库存预警数 |
| `sold_out_cnt` | 售罄数 |
| `stock_subscribe_cnt` | 到货订阅数 |
| `activity_stock_occupy_cnt` | 活动占用库存 |
| `channel_stock_occupy_cnt` | 渠道占用库存 |
| `advised_increase_spot_cnt` | 建议补货 |

**单条商品库存字段**（27 个中选摘）：

`total_stock_num`（总库存）、`spot_stock_num`（现货）、`future_stock_num`（未来库存）、
`total_occupied_stock_num`（占用）、`total_unoccupied_stock_num`（未占用）、
`skus[]`（SKU 级明细）、`warehouse_num`（仓数）、`is_alarming`（预警标位）、
`stock_type`、`shipping_mode`、`operations`、`stock_occupy_infos`

### D.3 商品创建（`/ffa/g/create`）

| 用途 | 方法 | 接口 | 状态 |
|---|---|---|---|
| 可创建检查 | GET | `/product/tproduct/canCreateGood?is_create=1` | ✅ 已识别 |
| 类目选择 | GET | `/product/tproduct/categoryOptionsN?cid=0` | ✅ 已识别 |
| 素材工具配置 | GET | `/material_api/product_material/check_gray` | ✅ 已识别 |
| 发布校验配置 | GET | `/product_diagnose/tproduct/diagnose_filed_config` | ✅ 已识别 |
| 类目属性模板 | — | 选完类目后加载 | ❌ 未触发（未选类目） |
| **提交发布** | — | 写接口 | ❌ 未触发，需真实提交一次 |

> 商品创建页的可展示部分 = 表单配置（类目树、属性 schema、素材工具）。
> 真正的「发布商品」是写接口，和订单的取号/发货同属 B 档验证范围。

### D.4 实现注意

1. **三处分页基准不同**（最易踩坑）：
   - `searchlist`（订单）：0-based
   - `product/tproduct/list`（商品）：0-based
   - `stock/manage/list`（库存）：**1-based**
   仓储层需按接口配置 `page_base`，禁止全局假设。
2. **现货与未来库存必须分开展示**：`spot_stock_num` 与 `future_stock_num` 是两套库存，
   简单相加会得出错误的"总可售"。
3. 三个模块的 `_bid` 不同：订单 `ffa_order`、商品 `ffa_goods`；
   库存接口虽挂在订单域（`ffa_order`）下，但路径是 `/stock/manage/`。
4. `operations` / `operation_actions` 字段可直接驱动按钮可用性，
   避免渲染平台不允许的操作。
5. 商品创建页未选类目时不会加载属性 schema，做「创建商品」功能时需按
   类目 → 属性 → 提交三段式实现，每段都有独立接口。

---

## 附录 E：售后聚合模块 UI → 接口映射（2026-11-24 验证）

> 覆盖「售后工作台 / 售后管理 / 售后详情」。目标：多店售后聚合看板 + 待办提醒。
> 结论：**只读层完整可用**；处理动作（同意退款/填运单号）为写接口，待真实操作验证。

### E.1 售后列表

```
POST /after_sale/pc/list   (_bid=ffa_aftersale)
```

**请求体（验证）**：

```json
{"pageSize":10,"page":1,"order_by":["status_deadline asc"],
 "conf_version":"v13","search_receiver":"","after_sale_status":"",
 "after_sale_type":"","order_flag":[],"order_logistics_state":[],
 "shop_hit_gray_info":{"list_v1":{"hit":true}}}
```

- `page` **1-based**
- `order_by: ["status_deadline asc"]` 即按处理截止时间排序（做待办列表用这个）
- 筛选：`after_sale_status`、`after_sale_type`、`search_receiver`（买家）
- `conf_version: "v13"` 需保留，可能是接口契约版本

**响应**：`total` + `data.items[]`，每项 9 个分组：

| 分组 | 内容 |
|---|---|
| `after_sale_info` | 售后主数据（40+ 字段，见下） |
| `order_info` | 订单号、关联订单明细、买家收货（脱敏） |
| `buttons` | 可用操作按钮（`button` code + 文案 + disabled） |
| `text_part` | 展示文案（状态/类型/原因/物流，全部现成） |
| `metrics` | `platform_intervene`（平台是否介入） |
| `seller_logs` | 商家备注日志 |
| `show_infos` | 需要展示的区块（如物流） |
| `extra` / `summary_info_list` | 附加数据 |

**`after_sale_info` 关键字段**：

`after_sale_id`、`related_id`（关联订单号）、`shop_id`、
`after_sale_type` / `after_sale_status`（数字枚举）、
`refund_amount`（分）、`refund_post_amount`、`after_sale_quantity`、
`apply_time` / `create_time` / `update_time`（秒）、
**`status_deadline`（处理截止时间）**、`left_node_time`（剩余秒数）、
`arbitrate_status`（仲裁状态）、`risk_decision_code`（风控决策）、
`encrypted_buyer_info`（昵称脱敏）、`detail_link`（详情页 URL）、
`return_logistics_code`、`after_sale_tags`、`reason_second_labels`

### E.2 状态计数

```
GET /shopuser/aftersale/counts?fields=<逗号分隔的状态名>
    &appid=1&_bid=ffa_aftersale&aid=4272&aftersale_platform_source=fxg
```

- `fields` 参数显式声明要查哪些状态（不传可能返回全量或报错，需验证）
- 验证返回 **50+ 状态位**，关键分组：

| 分组 | 字段 |
|---|---|
| 待审核 | `all_audit`、`refund_audit`（退款）、`return_audit`（退货）、`exchange_audit`（换货）、`resend_audit`（补发）、`repair_audit`（维修）、`presale_all_audit` |
| 时效预警 | `urge_audit`（催审）、`approaching_deadline_audit`（临近超时）、`audit_ddl_in_one_day` |
| 待收货/发货 | `return_for_receive`（待商家收货）、`exchange_for_receive`、`wait_user_delivery`（待消费者发货）、`wait_for_receive_and_delivery` |
| 待签收 | `wait_user_sign`、`all_wait_user_sign`、`exchange_wait_user_sign`、`resend_wait_user_sign` |
| 仲裁 | `arbitrate_pending`、`arbitrate_pending_negotiation`、`arbitrate_pending_evidence`、`arbitrate_shop_evidence`、`arbitrate_unsettled` |
| 自动审核 | `auto_audit_pre_sale_fast_refund`、`auto_audit_return_fast_refund`、`auto_audit_thunder_return` |
| 聚合 | `urgent_aggregate_count`、`wait_shop_audit_aggregate_count`、`wait_shop_receive_or_send_aggregate_count`、`wait_user_deal_aggregate_count`、`dispute_aggregate_count`、`platform_auto_deal_aggregate_count` |
| 其他 | `logistics_abnormal`、`suspected_violation`、`appeal_todo`、`govern_auto_agree`、`negotiate_close` |

样本值：`total=8` 单售后单中 `return_for_receive=1`、`all_audit=1`、`wait_user_delivery=1`。

### E.3 售后详情

```
GET /v1/aftersale/pc/detail?after_sale_id=<id>
    &extra={"detail_upgrade_hit":"new","proof_record_show":"new"}
    &appid=1&_bid=ffa_aftersale&aid=4272&aftersale_platform_source=fxg
```

返回 `data` 20 个区块：

| 区块 | 内容 |
|---|---|
| `title_info` | 标题、倒计时、处理状态、背景色 |
| `actions` | **可执行动作**（见 E.4） |
| `after_sale_info` | 售后基础信息、备注、物流、日志、单据 |
| `order_info` | 商品、买家、订单、物流信息 |
| `linked_info` | 仲裁证据模板、责任依据、用户账号 |
| `progress_node` | **进度节点数组**（文本 + 时间 + 状态 0/1/2） |
| `refund_records` | 退款记录、打款记录、补偿记录、剩余可退金额 |
| `token` | JWT（写操作可能需携带，待验证） |
| `detail_header_info` | 商品头图、价格、换货 SKU 快照 |
| `contact_list` / `metrics` / `notice` / `extra` | 联系人、平台介入、公告、灰度 |

**进度节点样本**：用户申请退货 → 同意申请 → 买家寄回 → 商家退款 → 售后完成

### E.4 操作按钮与写接口

**列表行按钮**（`buttons[].button`）：

| code | 文案 | 类型 |
|---|---|---|
| `urge_sms_return` | 提醒发货 | 写 |
| `refund_audit` | 同意退款 | 写 |
| `fill_logistics` | 代填运单号 | 写 |
| `im_contact_user` | 联系买家 | 跳转 IM |
| `order_ship_logistics` | 正向发货查看物流 | 只读 |
| `return_logistics` | 退货查看物流 | 只读 |
| `money_tracking` | 钱款去向 | 只读 |
| `exchange_logistics_extend` | 延长收货 | 写 |
| `handle` | 查看详情 | 跳转 |

**详情页动作**（`actions[].id`）：

| id | 文案 | server_url | 说明 |
|---|---|---|---|
| `im_contact_user` | 联系买家 | IM 工作台 URL | 直接跳转可用 |
| `return_refund_agree` | 已收到货，退款 | 空 | 写接口，前端另调（待抓） |
| `fill_logistics_for_user` | 代买家填写退货运单号 | 空 | 写接口（待抓） |

> ⚠️ 写接口 URL 在构建产物 中拼接，`server_url` 为空。需真实点击一次接口记录确认
> （属 B 档，且涉及资金动作，必须在测试单上操作）。

### E.5 辅助只读接口

| 用途 | 方法 | 接口 |
|---|---|---|
| 售后会话（协商记录） | GET | `/as/help/get_after_sale_conv?after_sale_id=&order_id=` |
| 消息盒 | GET | `/v1/aftersale/get_msg_box?msg_box_scene=1` |
| 列表展示配置 | GET | `/shopuser/aftersale/getAfterSaleListShowConfig` |
| 引导文案 | POST | `/aftersale/get_guide` |
| 灰度 | GET | `/v1/aftersale/grayHit?scene=list_v1` |
| 平台公告 | GET | `/common/index/alerts?from_day_before=7` |

### E.6 售后聚合实现建议

1. **多店聚合的数据源**：每店调一次 `counts`（轻量）+ 一次 `list`（分页），
   按 `status_deadline` 升序合并，形成跨店待办队列。
2. **优先级排序**：用 `left_node_time`（剩余秒数）做倒计时，
   `approaching_deadline_audit` / `audit_ddl_in_one_day` 做红色预警。
3. **状态展示直接用 `text_part`**：`after_sale_status_text` / `after_sale_type_text` /
   `reason_text` 都是平台下发的成品文案，不需要自己维护枚举映射表。
4. **按钮渲染用 `buttons[].button` + `disabled`**：与订单页 `operation_actions` 同思路，
   避免展示平台不允许的操作。
5. **详情页区块按需加载**：列表已含足够信息（商品、金额、状态、截止时间），
   详情接口在用户点开后再调，降低请求量。

### E.7 对设计文档的影响

- 第 2.2 节把「售后单、退款单、换货单处理」列为阶段三非目标 → **只读部分可提前到 MVP 后**，
  写操作仍留在阶段三（需 B 档验证）。
- 第 6.2 节数据模型建议新增 `aftersale` 表（字段参考 E.1 `after_sale_info`）：
  `after_sale_id`（PK）、`shop_id`、`order_no`、`type`、`status`、`refund_amount_cents`、
  `status_deadline`、`apply_time`、`detail_json`、`synced_at`。
- 第 5.8 节对账可扩展：对账时同时比对售后单状态，发现「平台已退款、本地无记录」异常。

---

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

- 样本店为**零保证金店铺**（`payable=0, balance=0, govern_stage=PayableEnough`），
  **金额单位（元/分）无法从 0 值判断，待有余额的店铺校准**
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
| 保证金（`payable/info_v2`） | `payable` / `balance` / `withdrawable_amount` | ⚠️ 样本全为 0，单位（元/分）待确认 |

资金账单条目的候选字段表（拿到首笔账单前使用，命中即按约定换算）：

1. 明确为分的字段：`amount_cents`
2. 候选（整数按分、带小数点按元）：`amount` / `bill_amount` / `order_amount` / `settle_amount` / `settlement_amount` / `total_amount` / `charge_amount` / `fee`
3. 全部未命中时记 0，界面标注「金额字段待探明」，**不要用猜测值冒充事实**

### F.5 多店资金看板建议

1. 每店一次 `query_item`（近 30 天），汇总条数与金额，单店失败不影响其他店
2. 上游不可用时回退本地缓存，并明确标注数据来源与错误
3. 资金数据只读；提现 / 转账等资金操作不纳入工具范围

---

## 附录 G：跨店对账逻辑（2026-11-24 验证校准）

> 对应正文 5.8 对账模块。本文档补充验证得到的**状态语义**与**异常判定细节**。

### G.1 数据源

| 用途 | 接口 | 说明 |
|---|---|---|
| 订单列表 | `GET /api/order/searchlist` | `page` 0-based，`pageSize=100` 验证可用，`tab=all` 拉全部状态 |
| 运单号 | 订单响应 `latest_logistic_info.tracking_no` | 未发货订单该字段为 `null` |
| 快递公司 | 同上 `latest_logistic_info.company_code` | |
| 收货人 | 订单响应 `receiver_info.post_receiver` | 脱敏值（如「张*」） |

对账**不需要额外接口**，全部基于订单列表 + 本地快照。

### G.2 订单状态语义（验证枚举）

| `order_status` | 含义 | 对账口径 |
|---|---|---|
| 3 | 已发货 | **视为已发货** |
| 5 | 已完成 | **视为已发货**（完成必然经历过发货） |
| 4 | 已关闭 | 视为未发货 |

**关键**：`order_status = 4` 的订单**仍可能携带运单号**（发货后被关闭）。若只把 3 当已发货，
「已发货 → 买家确认收货（变 5）」会被每天误报成状态回滚。

样本店状态分布：`3 × 6 单`、`4 × 11 单`、`5 × 1 单`（合计 18）。

### G.3 三类异常判定

| 异常 | 条件 | 业务含义 |
|---|---|---|
| `local_shipped_platform_not` | 快照已发货（或有运单），平台当前不是已发货 | 发货回传后被撤销 / 平台状态回滚，**最危险** |
| `platform_shipped_local_not` | 平台已发货，快照无记录或未标记发货 | 可能人工在后台发货，工具未同步 |
| `waybill_mismatch` | 两边都已发货，但运单号不同（含一方为空） | 运单被修改或换单 |

每单最多产出一类异常，避免同一原因重复上报。

### G.4 快照对比法

对账不依赖正式的订单同步模块，改用自建快照表：

1. 建 `orders_snapshot(shop_id, shop_order_id)` 唯一键，保存平台最近一次同步的
   `order_status / tracking_no / company_code / pay_time / ship_time / raw_json`
2. 每次对账在**同一事务**内：先逐单读旧快照 → 比较 → 全部读完再统一 upsert
   （保证比较基准是本次同步之前的快照）
3. `first_seen_at` 首次写入后不再更新，`last_synced_at` 每次刷新

### G.5 时间窗口

- 默认窗口 7 天，按 `create_time` 或 `pay_time` 任一落在窗口内即纳入
- **边界注意**：样本中 6 单已发货里最老的一单创建于 **7.1 天前**，
  严格 7 天窗口只覆盖 5 单。生产建议默认 30 天，或按 `exp_ship_time` 辅助判定
- 分页拉全后按窗口过滤，不依赖平台的时间筛选参数

### G.6 首次对账的预期行为

**首次运行时快照为空，所有已发货订单都会报 `platform_shipped_local_not`**——
这是建立基线的正常行为，不是故障。界面应提示「首次对账，正在建立基线」。

第二次起运行的异常才是真实差异。样本验证：

| 批次 | 窗口 | 订单数 | 异常 |
|---|---|---|---|
| 首次 | 7 天 | 12 | 5 条（5 个已发货单建立基线） |
| 同窗口重跑 | 7 天 | 12 | 0 条（幂等验证通过） |
| 扩到 30 天 | 30 天 | 18 | 2 条（第 6 个已发货单 + 1 个已完成单） |

### G.7 与正式订单模块的关系

`orders_snapshot` 是**对账专用快照**，不是订单主表。M1 完成正式订单同步后：

- 对账应改为「平台数据 vs `orders` 表」比对
- `orders_snapshot` 可保留为对账历史，或迁移合并
- 避免两套订单数据长期并存

---

## 附：术语表

| 术语 | 含义 |
|---|---|
| 取号 | 向平台/快递申请电子面单，得到运单号 |
| 面单 | 贴在包裹上的快递单据（通常 100×150mm） |
| 回传 | 把运单号填回平台订单，使订单变为"已发货" |
| 会话 | 登录后得到的凭证（cookie 等） |
| 渠道 | 与抖店通信的方式（协议直连 / 浏览器） |
| 对账 | 本地记录与平台数据的一致性核对 |
