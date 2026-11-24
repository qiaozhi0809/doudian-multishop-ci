# 整体方案（前后端设计 · 本地接口 · 技术栈）

> 日期：2026-11-24
> 定位：补充 [architecture.md](architecture.md) 第 4 节（总体架构）与第 11 节（技术栈与目录结构），
> 把「抖店接口能调通」推进到「系统怎么搭」。
> 目录与分层以 [engineering-rules.md](engineering-rules.md) 为准；与 architecture.md 冲突处以本文为准，
> 直到 architecture.md 按 [gaps.md](gaps.md) 修订完毕。
> 本文只定方向与边界，不含实现代码；标 🔶 的地方依赖 gaps.md 中的验证项。

---

## 1. 运行形态

单机、单进程、本地访问。软件运行在**出单机**（Windows 10/11）。

```
┌─────────────────────────── 出单机 ───────────────────────────┐
│                                                               │
│  浏览器 ──HTTP/SSE──► 后端进程（FastAPI + uvicorn，127.0.0.1:8787）│
│                         │  ├─ 托管前端静态文件（Vite 构建产物）     │
│                         │  ├─ 本地 API /api/*                   │
│                         │  └─ 后台任务（每店串行队列 + 定时器）     │
│                         │                                       │
│        ┌────────────────┼──────────────────┬─────────────────┐  │
│        ▼                ▼                  ▼                 ▼  │
│   SQLite (WAL)    curl_cffi 协议直连   Playwright + Edge   打印组件  │
│   data/app.db     ──► fxg.jinritemai   每店独立用户目录      wss://localhost:13999
│                                       （扫码 / 兜底 / 借页打印）  │
└───────────────────────────────────────────────────────────────┘
```

**本机数据目录**（全部不入库）：

| 路径 | 内容 |
|---|---|
| `data/app.db` | SQLite 主库 |
| `data/profiles/<shop_id>/` | 每店独立的浏览器用户目录（登录态 + 指纹隔离） |
| `data/backups/` | 每日数据库快照 |
| `logs/` | 运行日志（已脱敏） |

**约束**：后端只监听 `127.0.0.1`，不对局域网开放；本工具不设账户体系（architecture.md 2.2）。

---

## 2. 后端设计

### 2.1 分层与模块

按 engineering-rules 2.2：`api → service → adapter / store / domain`，禁止反向依赖。

| 层 | 模块 | 职责 |
|---|---|---|
| `api/` | `shop` `order` `label` `print` `shipping` `task` `event` `aftersale` `catalog` `fund` `reconcile` `audit` `setting` | 路由 + pydantic I/O schema，只调 service |
| `service/` | `session_manager` `base_data` `order_sync` `labeling` `printing` `shipping` `reconcile` `aftersale` `catalog` `fund` `scheduler` | 业务编排、事务、状态机推进 |
| `adapter/doudian/` | `client` `endpoints` `bid` `error_codes` `enums` `signing/` | 抖店 HTTP 协议的唯一出口 |
| `adapter/browser/` | `login` `channel` `page_print` | Playwright：扫码登录、兜底 fetch、借页面打印 |
| `adapter/print/` | `component` `ports` | 官方打印组件 WebSocket |
| `store/` | 按表分文件 | SQLite CRUD，无业务判断 |
| `domain/` | `order_status` `aftersale_status` `money` `idempotency` `reconcile_rules` | 纯模型与纯函数，无 IO |
| `shared/` | `time_bj` `redact` | 跨模块工具，配单测 |

### 2.2 抖店适配层（`adapter/doudian`）

**接口注册表**：每个抖店接口在 `endpoints.py` 里声明一次，业务代码只引用名字。

| 声明项 | 例 |
|---|---|
| `method` / `path` | `POST` / `/api/order/batchFetchTrackingNos` |
| `bid` | `ffa_order` / `ffa_goods` / `ffa_aftersale` |
| `body` | `json` / `form`（批量备注是 form） |
| `page_base` | `0` / `1` / `None` |
| `success_code` | `0` / `"100000"` |
| `write` | 是否写接口（决定是否受演练模式拦截、是否必须带幂等键） |
| `channel` | `protocol` / `browser`（逐接口声明，未验证免签名的写接口默认 `browser`） |

**客户端职责**：注入公共参数（`appid` / `__token` / `_bid` / `aid` / `_lid`，🔶 来源见 API-01）→ 发请求 → 归一化成功码 → 把失败归入下表五类异常，业务层只按类型处理。

| 异常类型 | 判定 | 上层处理 |
|---|---|---|
| `SessionExpired` | `code=10008` 等 | 暂停该店队列、标记 `needs_login`，重登后从断点继续 |
| `BizRejected` | 超区 / 余额不足 / 地址异常等 | 不重试，订单转 `exception` 并记录原因 |
| `RiskBlocked` | 🔶 待 API-11 | 暂停该店全部自动化，提示人工检查 |
| `Transient` | 超时 / 5xx / 限流 | 指数退避，最多 3 次 |
| `ParseError` | 字段缺失 / 结构变化 | 保留原始报文、告警、不重试 |

**可替换的发送层**：客户端依赖一个 `Transport` 接口，生产用 curl_cffi（`impersonate="chrome"`），测试用回放实现读取录制样本。原因：respx 等常见 mock 工具只支持 httpx，拦不住 curl_cffi。

**两个通道同一接口**：`protocol`（curl_cffi）与 `browser`（Playwright 页面内 `fetch`）实现同一个 `ShopChannel` 协议（architecture.md 5.2）；单次失败可降级一次。契约测试用同一组用例跑两个实现。

### 2.3 会话管理

- **每店一个持久化浏览器用户目录**（`data/profiles/<shop_id>/`），用 `launch_persistent_context`。登录态和指纹天然隔离，重登只需重开该目录。
- **浏览器用系统自带 Edge**（`channel="msedge"`），Windows 10/11 预装，不必把 Chromium 打进安装包。
- 扫码成功后用 `context.cookies()` 导出全量 cookie 给协议通道（engineering-rules 8.1）。
- cookie 只存一处（数据库 `session` 表），用 Windows DPAPI 加密后存储；废弃 `cookies/` 目录（DM-08）。
- 探测：每 30 分钟 `GET /api/order/tabcnt`；协议响应若下发新 cookie 则回写（🔶 API-02）。

### 2.4 调度与任务

- **每店一条 `asyncio.Queue` + 一个 worker**：同店请求绝不并发。
- **全局 `asyncio.Semaphore(3)`**：同时最多 3 个店在跑（可配置）。
- 同店请求间隔 300~1200ms 随机；工作时段外不跑定时任务。
- 任务落 `tasks` 表（architecture.md 6.2），进程重启时把 `running` 改回 `queued` 续跑。
- 定时任务（拉单 5 分钟、售后 5 分钟、商品库存 15 分钟、资金 30 分钟、每日对账）用进程内 asyncio 循环实现，不引入 Celery / APScheduler。

### 2.5 写操作：两步提交

所有写接口（取号、发货、作废、批量备注，以及阶段二的售后 / 商品 / 库存写操作）走同一套流程：

```
① POST /api/<写操作>/preview
     后端做预检，生成将要发出的每个请求（按店分组）、预计影响的订单数，
     返回 preview_id（短期有效）。不发出任何写请求。
② 前端展示预览 → 用户按住确认（hold-to-confirm）
③ POST /api/<写操作>/execute { preview_id }
     后端按预览内容入队执行；每个请求带幂等键，已执行过的直接返回上次结果。
④ 通过 SSE 推送逐单进度；结束后写审计日志。
```

- **演练模式** = 只允许第①步，第③步直接拒绝（engineering-rules 8.3）。
- 幂等键规则放在 `domain/idempotency.py`：
  - 取号：`label:{shop_id}:{shop_order_id}`，配合 `uq_active_waybill`
  - 发货：`ship:{shop_id}:{courier_code}:{tracking_no}`（已按验证接口改为运单维度）
- 预览与执行之间若订单状态变了（例如被平台关闭），执行时重新校验并跳过该单。

### 2.6 打印：三条路径

打印是履约闭环里唯一没打通的一环（🔶 API-07）。按可行性排序：

| 路径 | 做法 | 优点 | 风险 / 前提 |
|---|---|---|---|
| **P1 借页面打印** | 在该店的 Playwright 页面（打单发货页）里，调用抖店前端自带的打印逻辑，把 `print_data` 交给页面完成转换与发送 | 不用逆向 `mW()`；模板与官方完全一致 | 🔶 需验证页面打印函数能否从外部调用；依赖页面结构，改版需跟进 |
| P2 直连打印组件 | 后端解析 `print_data` 后直接发 `wss://localhost:13999` | 不依赖浏览器页面 | 需要逆向 `mW()` 的转换逻辑，成本高 |
| P3 手动补打（保底） | 本工具只取号与发货，面单由用户在抖店后台「补打面单」 | 零风险，闭环不被阻塞 | 多一步人工操作 |

**MVP 策略**：先以 P3 保底让闭环跑通，同时验证 P1；P1 验证通过后成为默认路径，P2 不做。
不论哪条路径，打印组件未就绪或回执失败时**不得**把订单标为已打印（验收标准第 10 条）。
多店共用本机打印机，配置「店铺 × 默认打印机」。

### 2.7 存储

- SQLite WAL 模式，单库；表结构以 architecture.md 6.2 为基础，补齐 gaps.md 第三节各项。
- 访问层用 **SQLAlchemy 2 Core**（只用 SQL 表达式，不用 ORM），迁移用 **Alembic**。
- 金额一律整数分、时间一律 ISO-8601 UTC（architecture.md 6.3）；平台秒级时间戳在 adapter 边界转换。
- 写库集中在 service 的事务里；只读聚合查询可直接走 store。

### 2.8 日志与审计

- 结构化日志（structlog），统一挂脱敏处理器：cookie、手机号、收件人、详细地址一律打码（engineering-rules 8.1）。
- `audit_log` 记录每次外部调用的动作、请求摘要、响应摘要、结果、耗时；写操作保存完整请求与响应（脱敏后）。

### 2.9 实时推送

`GET /api/events` 用 SSE 推送：任务进度、店铺会话状态变化、打印回执、告警。前端收到后让对应查询失效重取。不用 WebSocket，因为只需服务端单向推送。

---

## 3. 前端设计

### 3.1 结构

- **App Shell**：侧边栏导航 + 顶栏。顶栏常驻三样：**店铺筛选器**（全局，可多选）、**任务中心**（批量操作进度）、**会话健康指示**（任一店掉线即亮红点，点开可一键重登）。
- **页面**：仪表盘、订单、打单台、发货台、售后、商品、库存、资金、对账、店铺与设置（与 architecture.md 11.3 一致，打单台与发货台分开）。
- **模块四层**：每个页面按 engineering-rules 2.1 拆 `logic/` `hooks/` `components/` `index.tsx`。

### 3.2 数据层

- 服务端状态全部用 TanStack Query；查询 key 统一带上店铺筛选条件，如 `['orders', shopIds, filters]`。
- SSE 事件 → 对应 query key 失效；不手写轮询。
- **类型从后端生成**：用 openapi-typescript（或 orval）读 FastAPI 自动产出的 OpenAPI 描述，生成 `src/lib/api-types.ts`。前后端类型只有一个来源，后端改字段前端编译即报错。

### 3.3 表格

订单、商品、库存列表是核心。多店聚合后订单可能上千行，且需要**跨页勾选**后批量取号。
先确认 Arc `sortable-data-table` 是否支持虚拟滚动与受控选择；不支持则底层用 TanStack Table + TanStack Virtual，外观沿用 Arc 样式（放在 `components/custom/`）。

### 3.4 危险操作交互

写操作统一用「预览 → 按住确认」组件（`hold-to-confirm`），预览里按店分组列出将发出的请求和影响订单数；演练模式下确认按钮置灰并有明显标识。

---

## 4. 本地 API 草案

**约定**：

- 前缀 `/api`，JSON；金额字段统一以 `_cents` 结尾；时间为 ISO-8601 字符串。
- 分页：本地 API 统一 `page`（从 1 开始）+ `page_size`；抖店各接口的 0/1 基准差异只在 adapter 里处理，不外泄。
- 多店查询用 `shop_ids` 参数（逗号分隔，省略 = 全部启用店铺）。
- 错误统一结构：`{ "error": { "type": "BizRejected", "message": "...", "shop_id": 1, "detail": {...} } }`。
- 跨店聚合结果每店附 `source: upstream | local_db` 与失败原因，单店失败不让整个请求失败。

| 分组 | 方法 + 路径 | 用途 |
|---|---|---|
| 店铺与会话 | `GET /api/shops` | 店铺列表 + 会话健康 |
| | `POST /api/shops` | 新增店铺（随后发起扫码） |
| | `POST /api/shops/{id}/login` | 打开浏览器扫码 / 重登 |
| | `POST /api/shops/{id}/probe` | 立即探测会话 |
| | `POST /api/shops/{id}/sync-base` | 同步地址 / 模板 / 快递 / 面单账户 |
| | `GET /api/shops/{id}/base` | 查看本店基础数据 |
| | `PATCH /api/shops/{id}` | 改名、停用、切换通道、默认打印机 |
| 订单 | `GET /api/orders` | 跨店列表（筛选、排序、分页） |
| | `GET /api/orders/counts` | 跨店 tab 计数 |
| | `GET /api/orders/{id}` | 详情（含商品行、面单历史） |
| | `POST /api/orders/sync` | 立即拉单 |
| | `POST /api/orders/{id}/receiver` | 按需解密单个订单的收件人（用户查看时；不在取号链路，DEC-06；受额度与限速约束，见 architecture 7.3） |
| 取号 | `POST /api/labels/preview` · `POST /api/labels/execute` | 两步提交取号 |
| | `POST /api/labels/void/preview` · `POST /api/labels/void/execute` | 两步提交作废（🔶 API-08） |
| 打印 | `GET /api/print/status` | 打印组件是否在线 + 打印机列表 |
| | `POST /api/print/jobs` | 提交打印批次 |
| | `GET /api/print/jobs/{id}` | 打印回执 |
| 发货 | `POST /api/shipping/precheck` | 发货前检查（`sendcheck`） |
| | `POST /api/shipping/preview` · `POST /api/shipping/execute` | 两步提交发货 |
| 备注 | `POST /api/remarks/preview` · `POST /api/remarks/execute` | 两步提交批量备注 |
| 任务与事件 | `GET /api/tasks` · `GET /api/tasks/{id}` | 任务列表与进度 |
| | `POST /api/tasks/{id}/retry` · `POST /api/tasks/{id}/cancel` | 重试 / 取消 |
| | `GET /api/events` | SSE 推送 |
| 售后（只读） | `GET /api/aftersale` · `GET /api/aftersale/counts` · `GET /api/aftersale/{id}` | 跨店待办队列、计数、详情 |
| 商品 / 库存（只读） | `GET /api/catalog/products` · `GET /api/catalog/products/counts` · `GET /api/catalog/stock` | 列表、计数、库存概览 |
| 资金（只读） | `GET /api/fund/summary` · `GET /api/fund/unsettled` · `GET /api/fund/margin` | 多店概览、待结算、保证金 |
| 对账 | `POST /api/reconcile/runs` · `GET /api/reconcile/runs` | 触发 / 查看对账批次 |
| | `GET /api/reconcile/findings` · `PATCH /api/reconcile/findings/{id}` | 异常列表、标记已处理 |
| | `GET /api/reconcile/findings/export` | 导出 |
| 系统 | `GET /api/audit` | 审计日志查询 |
| | `GET /api/settings` · `PATCH /api/settings` | 限速、工作时段、演练模式、对账窗口等 |
| | `GET /api/health` | 后端、数据库、打印组件、各店会话的总体健康 |

详细 schema 待补（gaps.md ENG-01）。

---

## 5. 技术栈（修订版）

### 5.1 后端

| 用途 | 选型 | 相对 architecture.md 11.2 的变化 |
|---|---|---|
| 语言 | Python 3.12 | — |
| Web 框架 | FastAPI + uvicorn + Pydantic v2 | 明确 Pydantic v2 |
| 抖店协议 | curl_cffi（`impersonate="chrome"`），经可替换 Transport 调用 | 增加 Transport 抽象 |
| 浏览器 | Playwright（Python）+ 系统 Edge（`channel="msedge"`），每店持久化用户目录 | 改用系统 Edge |
| 签名 | py_mini_racer | **降为备用**：已验证的写接口免签名，不进 MVP 主路径 |
| 打印组件 | `websockets`，`wss://localhost:13999` | 改为 wss |
| 数据库 | SQLite WAL + SQLAlchemy 2 Core + Alembic | 新增访问层与迁移工具 |
| 调度 | asyncio（每店队列 + 全局信号量 + 进程内定时循环） | — |
| 日志 | structlog + 统一脱敏处理器 | 新增 |
| 凭证加密 | Windows DPAPI | 新增 |
| 测试 | pytest + pytest-asyncio + 录制回放 Transport | 明确回放方式 |
| 打包 | PyInstaller 单目录模式 + 启动脚本 | 🔶 细节见 ENG-04 |

### 5.2 前端

| 用途 | 选型 | 变化 |
|---|---|---|
| 框架 / 构建 | React 19 + TypeScript + Vite | — |
| 样式 / 组件 | Tailwind CSS 4 + Arc（Free 优先，Pro 补充） | — |
| 服务端状态 | TanStack Query | — |
| 路由 | React Router | — |
| 表格 | Arc `sortable-data-table`；不满足时 TanStack Table + TanStack Virtual | 新增备选 |
| 接口类型 | openapi-typescript（或 orval）从后端生成 | 新增 |
| 实时 | 原生 `EventSource`（SSE） | 新增 |
| 测试 | Vitest（logic / hooks）+ Playwright（关键流程端到端） | 新增 |

---

## 6. 里程碑调整建议

architecture.md 第 13 节把整个前端放在 M6，会导致 M1~M5 做完无法人工验收。建议**每个里程碑带上它自己的页面**：

| 阶段 | 后端 | 同时交付的前端 |
|---|---|---|
| M0 补验证 | gaps.md 中所有 P0 的 API 项 | — |
| M1 | 会话、基础数据、拉单 | App Shell、店铺与设置页、订单列表（只读） |
| M2 | 取号（两步提交，不解密，DEC-06）；按需查看收件人 | 打单台 |
| M3 | 打印（P3 保底 + P1 验证） | 打印状态、任务中心 |
| M4 | 发货前检查、发货、对账 | 发货台、对账页 |
| M5 | 售后 / 商品 / 库存 / 资金聚合 | 对应四个页面 + 仪表盘 |
| M6 | 打磨：掉线重登、限速、备份、演练模式、打包 | 通知中心、整体走查 |

---

## 7. 依赖 gaps.md 的部分

| 本文位置 | 依赖 |
|---|---|
| 2.2 公共参数注入 | API-01 |
| 2.2 `RiskBlocked` 判定 | API-11 |
| 2.3 cookie 回写 | API-02 |
| 2.5 作废两步提交 | API-08 |
| 2.6 打印默认路径 | API-07、ENG-03 |
| 4 本地 API 详细 schema | ENG-01 |
| 5.1 打包 | ENG-04 |
