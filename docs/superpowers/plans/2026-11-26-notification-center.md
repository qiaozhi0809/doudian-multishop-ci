# 通知中心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用右上角铃铛 + 持久化通知 + 三档提醒取代侧栏「任务」，并新增新订单 / 新售后检测。

**Architecture:** 后端新增 `notification` 与 `sync_baseline` 两张表。`NotificationService` 是唯一的写入口（`emit` / `raise_state` / `resolve_state`）。`NotificationFeed` 订阅现有事件总线，把已有事件翻译成通知，业务服务基本不改；只有新订单、新售后需要在同步处比对后发新事件。前端 `components/custom/notification-center` 负责铃铛、面板、顶部横条、弹窗、提示音与系统通知，并接管原任务中心的进度状态机。

**Tech Stack:** FastAPI + SQLAlchemy Core + Alembic + SQLite；React 19 + TanStack Query + SSE（`lib/use-events.ts`）+ 浮动提示（`components/custom/notice`）。

**Spec:** [2026-11-26-notification-center-design.md](../specs/2026-11-26-notification-center-design.md)

## Global Constraints

- 档位固定：强 = 新售后 / 退货（含仅退款）、登录失效、出口异常（不通 / IP 变化 / IP 重复）、风控暂停、临近发货超时；中 = 新订单、批量操作有失败、同步失败；弱 = 批量全部成功、对账完成、手动同步完成、「已恢复」。
- 强档：顶部横条（未解决不消失、不可手动关）、右下弹窗不自动关、提示音、页面在后台时发系统通知；中档弹窗 5 秒自动关；弱档不弹。
- 状态类每个 `state_key`（`login:{shop}` `egress:{shop}` `risk:{shop}` `deadline:{shop}`）同时最多一条未解决记录；恢复后 30 分钟内再犯 = 重开原记录、静默（不响铃不发系统通知、不写新的「已恢复」）。
- 新订单 / 新售后：该店该类没有 `sync_baseline` 时只入库不提醒；第一次**完整**同步成功后建基线（结果为 0 条也建）。新售后只提醒状态属于待办的单。
- 不为检测新增额外抖店请求，除了售后计数（每轮一次，计数变化才完整同步）。
- 已读且超过 30 天的事件类通知随每日备份清理；未解决状态类不清理。
- 通知正文只写事实（店名、数量、原因），不写说明长句；不得含账号密码、cookie、完整手机号、卡号。
- 单操作员：`read_at` 全局一份。
- 迁移编号 `0011`（当前最新 `0010_shop_profile_manual.py`）。
- 文件长度：`*.py` ≤ 400、`*.ts/tsx` ≤ 300、页面 `index.tsx` ≤ 80；四层分层（engineering-rules 2.1）。
- 每个任务一个提交，提交信息末尾 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。

## Review Focus

1. **状态来回切换**：出口每 5 分钟在 ok / unreachable 之间切换 → 只有第一次响铃，之后静默重开、横条随状态出现消失，不产生成串「已恢复」。→ Task 3。
2. **断线重连漏消息**：SSE 断开期间产生的通知 → 重连后重新拉 summary 与列表，铃铛数字正确。→ Task 7。
3. **刷新页面后强提醒仍可见**：未解决的强档状态在刷新后由 summary 恢复出横条；已出现过的强档弹窗不在刷新后重复弹。→ Task 7。
4. **系统通知权限被拒或浏览器不支持**：不报错，只是不发系统通知；提示音被浏览器自动播放策略拦截时静默失败。→ Task 8。
5. **新店第一次同步**：刚加的店第一次同步出 30 单 → 不发「新增 30 单」；第二轮新增 1 单 → 发。→ Task 4。

---

### Task 1: 表结构与存储

**Files:**
- Create: `backend/migrations/versions/0011_notification.py`
- Modify: `backend/app/store/schema.py`（或新建 `notification_schema.py` 并在 `migration_test` 的导入里注册，参照 `backup_schema.py`）
- Create: `backend/app/store/notification_store.py`、`backend/app/store/sync_baseline_store.py`
- Test: `backend/tests/store/notification_store_test.py`、`backend/tests/store/migration_test.py`（TABLES 加两张表）

**Interfaces:**
- Produces:
  - 表 `notification`：`id, kind TEXT NOT NULL, level TEXT NOT NULL, shop_id INTEGER NULL FK shop.id, title TEXT NOT NULL, body TEXT, link TEXT, count INTEGER NOT NULL DEFAULT 1, state_key TEXT NULL, resolved_at TEXT NULL, read_at TEXT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL`；索引 `idx_notification_unread (read_at, created_at)`；部分唯一索引 `uq_notification_open_state (state_key) WHERE state_key IS NOT NULL AND resolved_at IS NULL`
  - 表 `sync_baseline`：`shop_id INTEGER FK, kind TEXT, established_at TEXT`，主键 `(shop_id, kind)`
  - `notification_store`：`insert(conn, **fields) -> int`；`get(conn, id)`；`update(conn, id, now, **fields)`（白名单 `title body link count level resolved_at read_at`）；`open_state(conn, state_key) -> Mapping | None`；`last_resolved_state(conn, state_key) -> Mapping | None`（`resolved_at` 最新的一条）；`latest_unread_event(conn, shop_id, kind) -> Mapping | None`；`list_page(conn, *, unread_only: bool, offset: int, limit: int) -> (rows, total)`（`updated_at` 倒序）；`unread_count(conn) -> int`；`open_strong_states(conn) -> list`；`mark_read(conn, id, now)`；`mark_all_read(conn, now)`；`purge_read_events_before(conn, cutoff) -> int`
  - `sync_baseline_store`：`has(conn, shop_id, kind) -> bool`；`establish(conn, shop_id, kind, now) -> None`（已存在不改）

- [ ] **Step 1: 写失败测试**：插入 / 读取往返；同一 `state_key` 两条未解决 → `IntegrityError`；一条已解决 + 一条未解决可共存；`list_page(unread_only=True)` 只返回未读、按 `updated_at` 倒序；`purge_read_events_before` 不删未读、不删 `state_key` 非空且未解决的；`establish` 幂等
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/store/notification_store_test.py tests/store/migration_test.py` → FAIL
- [ ] **Step 3: 实现迁移 0011 与两个 store**（`down_revision="0010"`，`downgrade` 抛 `NotImplementedError`）
- [ ] **Step 4:** 同上命令 → PASS
- [ ] **Step 5: 提交** `feat(store): 通知与同步基线表（迁移 0011）`

---

### Task 2: 通知规则（纯函数）

**Files:**
- Create: `backend/app/domain/notification_rules.py`
- Test: `backend/tests/domain/notification_rules_test.py`

**Interfaces:**
- Produces:
  - `Kind = Literal["new_order","new_aftersale","login_expired","egress_unreachable","egress_changed","egress_duplicate","risk_paused","ship_deadline","batch_done","batch_failed","sync_failed","sync_done","reconcile_done","recovered"]`
  - `LEVEL_BY_KIND: dict[Kind, Literal["strong","medium","weak"]]`（照 Global Constraints）
  - `REOPEN_SILENT_WITHIN = timedelta(minutes=30)`
  - `state_key(kind_family: Literal["login","egress","risk","deadline"], shop_id: int) -> str`
  - `link_for(kind: Kind, shop_id: int | None) -> str`：`new_order` → `/orders?shop=<id>`；`new_aftersale` → `/aftersale?view=todo&shop=<id>`；`ship_deadline` → `/orders?filter=overdue&shop=<id>`（筛选参数名以全部订单页现有 URL 参数为准）；`login_expired` / `egress_*` / `risk_paused` → `/shops?shop=<id>`；`batch_*` → `/labeling`；`sync_*` 按同步类型对应页面；`reconcile_done` → `/reconcile`
  - `title_for(kind, *, shop_name: str | None, count: int, detail: str | None) -> str`：例「店A 新增 5 单待发货」「店A 新增 2 个售后」「店A 登录失效」「店A 出口不通」「店A 出口 IP 已变化」「店A 出口 IP 与其他店重复」「店A 风控暂停」「店A 3 单临近发货超时」「打单完成：成功 12，失败 1」「店A 已恢复：出口不通」

- [ ] **Step 1: 写失败测试**：每个 kind 都有 level 与 link；`title_for` 上述样例逐字一致；`state_key("egress", 3) == "egress:3"`
- [ ] **Step 2:** `uv run pytest -q tests/domain/notification_rules_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(domain): 通知分档、标题与跳转规则`

---

### Task 3: NotificationService

**Files:**
- Create: `backend/app/service/notifications.py`
- Modify: `backend/app/service/events.py`（新增 `NOTIFICATION = "notification"`）
- Test: `backend/tests/service/notifications_test.py`

**Interfaces:**
- Consumes: Task 1 store、Task 2 规则
- Produces:
  - `NotificationService(engine, events: EventBus, clock=...)`
  - `emit(kind: Kind, *, shop_id: int | None, count: int = 1, detail: str | None = None) -> int`：该店同 kind 最近一条仍未读则累加 `count`、重写标题、`updated_at=now`（合并），否则新建
  - `raise_state(family, kind: Kind, *, shop_id: int, count: int = 1, detail: str | None = None) -> None`：已有未解决 → 只更新正文 / count，不提醒；无未解决但 `last_resolved_state` 在 30 分钟内 → 清 `resolved_at` 重开、静默；否则新建并提醒
  - `resolve_state(family, *, shop_id: int) -> None`：有未解决 → 置 `resolved_at`；若这次问题不是静默重开出来的，再 `emit("recovered", detail=原标题问题部分)`
  - `list(*, unread_only: bool, page: int, page_size: int = 50) -> dict`、`summary() -> {"unread": int, "strong_open": [{"shop_id","shop_name","kinds":[...],"link"}]}`（按店聚合）、`mark_read(id)`、`mark_all_read()`、`purge(now)`
  - 每次写入后 `events.publish(NOTIFICATION, {"action": "created"|"updated"|"resolved"|"read", "item": <行>, "alert": bool})`；`alert` 仅在新建或非静默重开时为 True

- [ ] **Step 1: 写失败测试**
  - 同店同 kind 未读期间两次 `emit` → 一条，`count` 累加，标题「店A 新增 7 单待发货」
  - `raise_state` 两次 → 一条；第二次 `alert=False`
  - `resolve_state` 后 10 分钟再 `raise_state` → 同一条重开、`alert=False`、没有第二条 `recovered`（Review Focus 1）
  - `resolve_state` 后 31 分钟再 `raise_state` → 新的一条、`alert=True`
  - `summary()`：店A 登录失效 + 出口不通 → `strong_open` 一项、`kinds` 含两者；已解决的不出现
  - `mark_all_read` 后 `unread == 0`，并发布 `action="read"`
- [ ] **Step 2:** `uv run pytest -q tests/service/notifications_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(service): 通知服务（合并、状态重开与恢复）`

---

### Task 4: 新订单 / 新售后检测与售后定时检查

**Files:**
- Modify: `backend/app/store/order_store.py`（`existing_order_nos(conn, shop_id, order_nos) -> set[str]`）、`backend/app/store/aftersale_store.py`（`existing_ids(conn, shop_id, ids) -> set[str]`）
- Modify: `backend/app/service/order_sync.py`、`backend/app/service/aftersale.py`
- Modify: `backend/app/service/events.py`（`ORDERS_NEW = "orders_new"`、`AFTERSALES_NEW = "aftersales_new"`）
- Modify: `backend/app/main.py`（lifespan 增加售后检查定时任务，间隔 `ORDER_SYNC_INTERVAL_S`）
- Test: `backend/tests/service/order_sync_test.py`、`backend/tests/service/aftersale_test.py`（补）

**Interfaces:**
- Produces:
  - 订单同步：每页入库前用 `existing_order_nos` 算出新单；整轮结束且 `complete` 时：有基线 → 新单数 > 0 发 `ORDERS_NEW {shop_id, count}`；无基线 → `establish(shop, "orders")`，不发
  - 售后：`AftersaleService.check_new(shop_id, actor="system") -> int`：调 `counts`（有 60 秒缓存），待办合计与上次记录（内存字典 per shop）不同才调 `_sync_shop`；`_sync_shop` 用 `existing_ids` 算新单，只统计状态属于待办的（以现有 `pending_total` / 待办状态集合为准）；`complete` 时有基线发 `AFTERSALES_NEW {shop_id, count}`，无基线建基线
  - 手动「同步售后」也走同一比对（同一个 `_sync_shop`）

- [ ] **Step 1: 写失败测试**
  - 新店第一次同步 30 单 → 不发 `ORDERS_NEW`、建了基线；第二次多 1 单 → 发 `count=1`（Review Focus 5）
  - 同步中途失败（`complete=False`）→ 不建基线、不发
  - 售后：计数没变 → 不调列表接口；变了 → 同步并只对待办状态的新单计数；已关闭的新单不计
  - 有订单但从未同步过售后的店：第一次售后同步建基线；之后第一笔售后能发
- [ ] **Step 2:** `uv run pytest -q tests/service/order_sync_test.py tests/service/aftersale_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS；`uv run pytest -q` 全量 → PASS
- [ ] **Step 5: 提交** `feat(sync): 识别新订单与新售后，售后定时检查`

---

### Task 5: 事件翻译（NotificationFeed）、接口与接线

**Files:**
- Create: `backend/app/service/notification_feed.py`、`backend/app/api/notification.py`、`backend/app/api/notification_schemas.py`
- Modify: `backend/app/wiring.py`、`backend/app/main.py`（启动 feed 订阅任务；每日备份后调用 `purge`）、手动同步接口所在服务（订单、售后、商品、库存、资金的手动同步结束处发布 `SYNC_RESULT = "sync_result" {kind, shop_id, ok, error}`，定时同步不发「完成」）
- Test: `backend/tests/service/notification_feed_test.py`、`backend/tests/api/notification_api_test.py`

**Interfaces:**
- Consumes: Task 3 服务；事件 `SHOP_STATUS_CHANGED` `SHOP_LOGIN_FAILED` `LABEL_DONE` `SHIP_DONE` `PRINT_DONE` `RECONCILE_DONE` `SHIP_DEADLINE_WARNING` `ORDERS_NEW` `AFTERSALES_NEW` `SYNC_RESULT`
- Produces:
  - `NotificationFeed(engine, notifications: NotificationService)`；`handle(event: str, data: dict) -> None`（同步、可测）；`async run(bus: EventBus, stop: asyncio.Event)`（订阅循环，异常只记日志不退出）
  - 状态对账 `reconcile_shop(shop_id)`：读该店当前行与会话 → `status == needs_login` 且该店有过会话（`session_store.load` 非空）→ `raise_state("login","login_expired")`，否则 resolve；`egress_status` 为 `unreachable/changed/duplicate` → 对应 kind，`ok/unchecked` → resolve；`paused_reason` 以风控前缀开头 → `risk_paused`，否则 resolve。`SHOP_STATUS_CHANGED`、`SHOP_LOGIN_FAILED` 都只调用它
  - `SHIP_DEADLINE_WARNING`：按店分组 → 有单的店 `raise_state("deadline", count=n)`，其余有未解决 deadline 的店 resolve
  - `*_DONE`：`failed > 0` → `emit("batch_failed")`，否则 `emit("batch_done")`；标题区分打单 / 发货 / 打印
  - 接口：`GET /api/notifications?unread=0|1&page=1`、`GET /api/notifications/summary`、`POST /api/notifications/{id}/read`、`POST /api/notifications/read-all`
- 导出 openapi 并 `pnpm gen:api`（命令见 `docs/superpowers/plans/2026-11-25-proxy-pool.md` Task 7 第 5 步）

- [ ] **Step 1: 写失败测试**：`SHOP_STATUS_CHANGED{egress_status:"unreachable"}` → 未解决 egress 通知；再来 `ok` → 已解决 + `recovered`；从未登录过的新店 `needs_login` → 不报登录失效；`LABEL_DONE{failed:1}` → `batch_failed`；`SHIP_DEADLINE_WARNING` 两店有单 → 两条，下一次只剩一店 → 另一店 resolve；接口 4 个路由状态码与响应体，未登录 401
- [ ] **Step 2:** `uv run pytest -q tests/service/notification_feed_test.py tests/api/notification_api_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS；全量 `uv run ruff check . && uv run pytest -q` → PASS
- [ ] **Step 5: 提交** `feat(api): 通知接口与事件翻译`

---

### Task 6: 前端通知数据层（迁移任务中心逻辑）

**Files:**
- Create: `frontend/src/components/custom/notification-center/logic/notification-view.ts`、`logic/progress.ts`（由 `task-center/logic/task-log.ts` 迁来，只保留「进行中」部分）、`hooks/use-notifications.ts`、`hooks/use-progress.ts`（由 `task-store.ts` / `use-task-center.ts` 迁来）
- Modify: `frontend/src/lib/query-keys.ts`（`notifications(unreadOnly, page)`、`notificationSummary()`）
- Test: 各自 `*.test.ts(x)`

**Interfaces:**
- Consumes: Task 5 接口与 SSE `notification` 事件
- Produces:
  - `useNotifications()` → `{ items, unread, strongOpen, page, setPage, unreadOnly, setUnreadOnly, markRead(id), markAllRead(), loading }`；收到 `notification` 事件时失效 `notificationSummary` 与列表；SSE 重连后同样失效（Review Focus 2）
  - `useNotificationAlerts(onAlert: (item) => void)`：只对 `alert === true` 且本会话未处理过的 id 回调（id 记在 `sessionStorage`，刷新不重复弹，Review Focus 3）
  - `useProgress()` → 进行中批量任务列表（原任务中心进度逻辑，事件同前），结束后从列表移除（结果由后端通知承担）
  - `levelTone(level) -> "danger" | "warning" | "info"`、`groupForPanel(items) -> { open: [...], recent: [...] }`

- [ ] **Step 1: 写失败测试**：重连事件触发重新拉取；同一 alert id 第二次不回调；进度在 `*_done` 后移除；`groupForPanel` 未解决状态在前
- [ ] **Step 2:** `cd frontend && pnpm test src/components/custom/notification-center` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(frontend): 通知数据层，迁移任务进度逻辑`

---

### Task 7: 铃铛、面板、顶部横条、弹窗

**Files:**
- Create: `frontend/src/components/custom/notification-center/components/bell.tsx`、`panel.tsx`、`strong-banner.tsx`、`index.tsx`、`notification-center.module.css`
- Modify: `frontend/src/components/custom/app-shell/index.tsx`（右上角放铃铛、页面顶部放横条，去掉 `tasks={<TaskCenter />}` 与侧栏「任务」）、`components/side-nav.tsx`
- Delete: `frontend/src/components/custom/task-center/`
- Modify: 店铺管理页支持 `?shop=<id>` 高亮并滚动到该行
- Test: 组件测试 + `app-shell/index.test.tsx` 更新

**Interfaces:**
- Consumes: Task 6 hooks；`useNotice()` 浮动提示
- Produces:
  - 铃铛：纯图标按钮（无背景），未读徽标，强档未解决时红色；`aria-label="通知"`
  - 面板（Popover 右上展开）：「进行中」→「待处理」（未解决状态类）→ 通知列表（未读加粗，点击已读并跳转 `link`）→「全部已读」；「只看未读」切换；提示音开关
  - 顶部横条：`strongOpen` 一店一行「店A：登录失效、出口不通」，超过 3 家合并「N 家店需要处理」（点击打开面板）；点击按第一项问题的 `link` 跳转；无关闭按钮
  - 弹窗：`alert` 强档 → `useNotice` 常驻（不自动关）；中档 5 秒；弱档不弹

- [ ] **Step 1: 写失败测试**：summary 有两店问题 → 横条两行；四店 → 一行「4 家店需要处理」；中档 alert 5 秒后消失、强档不消失；侧栏不再有「任务」；`/shops?shop=2` 高亮第 2 店
- [ ] **Step 2:** `pnpm test src/components/custom` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS；`pnpm lint && pnpm exec tsc -b && pnpm test && pnpm build` → PASS
- [ ] **Step 5: 提交** `feat(frontend): 右上角通知中心与强提醒横条`

---

### Task 8: 提示音与系统通知

**Files:**
- Create: `frontend/src/components/custom/notification-center/logic/alert-channel.ts`、`hooks/use-alert-channel.ts`、`frontend/public/sounds/alert.mp3`（自行生成的短提示音，≤ 1 秒，不用版权素材）
- Test: `logic/alert-channel.test.ts`

**Interfaces:**
- Produces: `notifyStrong(item, { muted, documentHidden }) -> { played: boolean, shown: boolean }`：未静音时播放提示音（`play()` 被拒时吞掉）；`documentHidden` 且 `Notification.permission === "granted"` 时 `new Notification(title, { body, tag: String(item.id) })`；`Notification` 不存在或权限被拒时不报错（Review Focus 4）；第一次需要时 `requestPermission()`；静音开关存 `localStorage` 键 `notify.muted`

- [ ] **Step 1: 写失败测试**：`Notification` 未定义 → 不抛；权限 `denied` → `shown=false`；`play` reject → `played=false` 不抛；静音 → 不播放
- [ ] **Step 2:** → FAIL
- [ ] **Step 3: 实现并接到 Task 7 的强档弹窗回调**
- [ ] **Step 4:** → PASS；前端全量 → PASS
- [ ] **Step 5: 提交** `feat(frontend): 强提醒的提示音与系统通知`

---

### Task 9: 文档与全量回归

**Files:**
- Modify: `docs/design/backend.md`（通知服务与事件翻译、售后定时检查）、`docs/design/data-model.md`（两张表）、`docs/design/local-api.md`（4 个接口、SSE `notification`）、`docs/design/frontend.md`（铃铛、横条，删「任务」）

- [ ] **Step 1: 改文档**
- [ ] **Step 2:** `cd backend && uv run ruff check . && uv run pytest -q`；`cd frontend && pnpm lint && pnpm exec tsc -b && pnpm test && pnpm build` → 全部通过
- [ ] **Step 3:** 浏览器实测：铃铛、横条（可在开发库把某店 `egress_status` 改成 `unreachable` 后发一次状态检查触发）、强档弹窗与提示音、刷新后横条仍在且弹窗不重复
- [ ] **Step 4: 提交** `docs: 通知中心写入设计文档`
