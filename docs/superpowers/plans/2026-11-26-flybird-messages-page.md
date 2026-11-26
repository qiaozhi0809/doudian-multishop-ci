# 飞鸽消息聚合（只读）实施计划 · 第二阶段：消息页与接口

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增侧栏「客服 > 消息」（`/messages`）：顶部四张计数卡兼快捷筛选，左栏跨店会话列表（默认按等待时间倒序），右栏只读会话详情，底部「在飞鸽中回复」把该店自己的浏览器窗口置前到该会话，「查看订单」跳到订单页。全站没有输入框，不发送任何内容。

**Architecture:** 会话列表来自第一阶段 `ImWatcher.snapshot()` 的内存快照（跨店合并，白名单排序与快捷筛选在内存里做完再分页）；消息来自 `im_message`。「在飞鸽中回复」经 `ShopRunner` 队列，在该店已登记的常驻页上执行 `adapter/flybird/focus.py`：窗口移回屏幕、置前、点开该会话，这是全系统唯一的页面点击。

**Depends on:** 第一阶段 `2026-11-26-flybird-readonly-im.md` 全部完成（Task 0 已为 go，2026-11-26），以及其依赖的分支 `feat/browser-lifecycle` 已合并。`FOCUS_METHOD`（U12）在本阶段 Task 14 开头实测确定。

**Tech Stack:** 同第一阶段。

**Spec:** `docs/api/flybird.md`（U9 到 U12 的结论）；页面约定见 `docs/design/frontend.md`、`frontend/src/lib/use-quick-filter.ts`、`frontend/src/components/arc/metric-card/metric-card.tsx`。

## Global Constraints

- 第一阶段的全部约束照用：只读、出口只经登记表、启动经 ShopRunner、消息正文不进日志 / 审计 / 事件 / 通知。
- **唯一的点击**：只在所有者点「在飞鸽中回复」时，在 `adapter/flybird/focus.py` 里做窗口置前与一次会话点击；不输入、不按键、不发送。守卫测试锁定（Task 14）。点开会话会把该会话标为已读，这是所有者自己的动作，不产生通知。
- **无输入框**：消息页任何位置都没有文本输入（`textarea`、`input[type=text]`）；测试断言。
- **买家显示名**：消息推送里没有昵称（Task 0），列表与详情显示「买家 · 尾号 xxxx」（会话 short ID 后 4 位）。页面自动打开会话时自己请求的 `backstage/workstation/get_user_card` 响应可能有昵称，作为后续改进，不在本阶段。
- 排序与快捷筛选：白名单 `Literal`，非白名单 422；在内存快照里筛完、排完再分页（快照不落库，见第一阶段）。
- 店铺筛选沿用全站 `shops` 参数（`useShopFilter`，接口参数 `shop_ids`）；快捷筛选沿用 `quick`（`useQuickFilter`）。
- 文件长度、四层分层、文案规则、测试命令、提交格式同第一阶段。测试数据一律虚构（`测试小铺`、`测试买家`、`在吗`、`conv-test-1`）。

## Review Focus

1. **点击只在一处**：`focus.py` 之外没有 `.click(`、`bring_to_front`、`setWindowBounds`；`focus.py` 里只有一次 `.click(`，选择器只拼会话 ID。→ Task 14。
2. **启动前的消息**：常驻页启动前到达、本系统没收到的消息不会出现；详情只显示已采集的消息，不报错、不空白。→ Task 13、15。
3. **等待计时一致**：后端 `wait_seconds` 与前端走秒用同一起点；超 3 分钟的行与「超 3 分钟未回复」卡片数一致。→ Task 12、15。
4. **订单跳转**：订单接口没有买家筛选，只带店铺。→ Task 15。

---

### Task 12: 会话视图规则（纯函数）

**Files:**
- Create: `backend/app/domain/im_view_rules.py`
- Modify: `backend/app/api/list_sort.py`（加 `ImConversationSort = Literal["waiting", "last_at", "unread", "shop_name"]`、`ImQuick = Literal["unread", "waiting", "overdue", "today"]`）
- Test: `backend/tests/domain/im_view_rules_test.py`、`backend/tests/api/list_sort_test.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class ConvRow: shop_id: int; shop_name: str; conversation_id: str; buyer: str; preview: str; unread: int; last_at: str | None; waiting_since: str | None`（由第一阶段 `ConvView` 转来：`preview = last_text`、`unread = pending`、`buyer = buyer_label(conversation_id)`）
  - `buyer_label(conversation_id: str) -> str`：`买家 · 尾号{后 4 位}`
  - `wait_seconds(row: ConvRow, now: datetime) -> int | None`
  - `is_overdue(row, now) -> bool`（`> WAIT_ALERT`，与 `im_rules.overdue_count` 同一判定）
  - `is_today(last_at: str | None, now: datetime) -> bool`（按 `app/shared/time_bj.BEIJING` 的自然日）
  - `matches(row, *, unread_only: bool, quick: ImQuick | None, now) -> bool`：`unread` = `unread > 0`；`waiting` = `waiting_since` 非空；`overdue` = `is_overdue`；`today` = `is_today(last_at)`
  - `counts(rows, now) -> dict[ImQuick, int]`（只按店铺筛选，不受 `quick` 与「只看未读」影响）
  - `sort_rows(rows, sort: ImConversationSort | None, order: SortOrder, now) -> list[ConvRow]`：省略 `sort` = `waiting` 倒序；没有等待的行排在有等待的行之后，再按 `last_at` 倒序；同值按 `(shop_id, conversation_id)` 保证稳定
  - `page_rows(rows, page: int, page_size: int) -> tuple[list[ConvRow], int]`

- [ ] **Step 1: 写失败测试**
  - `test_wait_seconds_none_when_not_waiting`
  - `test_overdue_boundary_3_minutes`：180 秒不算，181 秒算
  - `test_is_today_uses_beijing_day`：UTC 16:30 前一天 = 北京今天 00:30
  - `test_matches_each_quick`；`test_unread_only_and_quick_combine`
  - `test_counts_ignore_quick`
  - `test_default_sort_longest_wait_first_then_last_at`
  - `test_sort_shop_name_and_unread_with_order`
  - `test_sort_stable_ties`
  - `test_page_rows_total`
  - `list_sort_test.py`：新加的两个 `Literal` 与 `im_view_rules` 的排序键一一对应
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/domain/im_view_rules_test.py tests/api/list_sort_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(domain): 飞鸽会话视图的计时、筛选与排序`

---

### Task 13: 会话与消息接口

**Files:**
- Create: `backend/app/service/im_query.py`
- Modify: `backend/app/api/im_schemas.py`、`backend/app/api/im.py`、`backend/app/wiring.py`
- Modify: `frontend/openapi.json`、`frontend/src/lib/api-types.ts`（生成）
- Test: `backend/tests/service/im_query_test.py`、`backend/tests/api/im_api_test.py`、`backend/tests/api/openapi_test.py`

**Interfaces:**
- Produces（`im_query.py`）：`class ImQueryService`：`__init__(self, engine, im: ImWatcher, *, clock)`
  - `rows(shop_ids: list[int]) -> list[ConvRow]`（逐店 `im.snapshot(shop_id)`，店名取 `shop_store`）
  - `conversations(shop_ids, *, unread_only: bool, quick: ImQuick | None, sort, order, page, page_size) -> tuple[list[ConvRow], int]`
  - `counts(shop_ids) -> dict[ImQuick, int]`
  - `thread(shop_id: int, conversation_id: str) -> ImThreadData`：读 `im_message_store.list_for_conversation`；快照与消息表都没有该会话 → `NotFound`
- Produces（`im_schemas.py` 追加）：
  - `ImConversation`（`shop_id, shop_name, conversation_id, buyer, preview, unread, last_at, waiting_since, wait_seconds`）；`ImConversationPage`（`items, total, page, page_size`）
  - `ImCounts`（`unread, waiting, overdue, today`，键名与 `ImQuick` 一致）
  - `ImMessage`（`message_id, sender_role: Literal["buyer", "agent", "robot", "platform"], text, sent_at`）；`ImThread`（`shop_id, conversation_id, items: list[ImMessage]`）
  - `ConversationId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_:.\-]{1,128}$")]`
- Produces（`api/im.py` 追加，全部 `Depends(require_admin)`；店铺范围经 `state.shop_admin.target_ids(parse_shop_ids(shop_ids))`）：
  - `GET /conversations?shop_ids=&unread=false&quick=&sort=&order=desc&page=1&page_size=50` → `ImConversationPage`（`page_size` ≤ 200）
  - `GET /conversations/counts?shop_ids=` → `ImCounts`
  - `GET /conversations/{shop_id}/{conversation_id}/messages` → `ImThread`
- `wiring.py`：`"im_query": ImQueryService(engine, im, **clock_kw)`

- [ ] **Step 1: 写失败测试**
  - `im_query_test.py`（假 `ImWatcher` 快照：`测试小铺` 的 `测试买家` / `在吗`）：`test_rows_merge_shops`；`test_conversations_filter_sort_page`；`test_counts_independent_of_quick`；`test_thread_in_time_order`；`test_thread_known_conversation_without_rows_is_empty`；`test_thread_unknown_conversation_not_found`；`test_buyer_label_last4`
  - `im_api_test.py`：`test_conversations_requires_admin`；`test_conversations_default_sort_waiting_desc`；`test_conversations_bad_sort_or_quick_422`；`test_conversations_shop_filter`；`test_counts_shape`；`test_messages_ok`；`test_messages_bad_conversation_id_422`；`test_messages_unknown_404`
  - `openapi_test.py`：路径集合加 `/api/im/conversations`、`/api/im/conversations/counts`、`/api/im/conversations/{shop_id}/{conversation_id}/messages`
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/service/im_query_test.py tests/api/im_api_test.py tests/api/openapi_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS；`uv run ruff check . && uv run pytest -q` → PASS
- [ ] **Step 5: 导出类型**：`cd backend && uv run python -m app.main --export-openapi ../frontend/openapi.json`，再 `cd ../frontend && pnpm gen:api`
- [ ] **Step 6: 提交** `feat(api): 飞鸽会话列表、计数与消息记录接口`

---

### Task 14: 在飞鸽中回复（置前到会话）

**Files:**
- Create: `backend/app/adapter/flybird/focus.py`
- Modify: `backend/app/adapter/flybird/endpoints.py`（`FOCUS_BOUNDS = {"left": 0, "top": 0, "windowState": "normal"}`；Step 0 的结论 `FOCUS_METHOD: Literal["cdp_bounds", "relaunch_visible"]`、`CONVERSATION_SELECTOR`、`CONV_ID_ATTR`）
- Modify: `backend/app/service/im_watcher.py`（`focus`）
- Modify: `backend/app/api/im.py`、`backend/app/api/im_schemas.py`
- Test: `backend/tests/adapter/flybird_focus_test.py`、`backend/tests/adapter/flybird_readonly_guard_test.py`、`backend/tests/service/im_watcher_test.py`、`backend/tests/api/im_api_test.py`、`backend/tests/api/openapi_test.py`

**Interfaces:**
- Produces（`focus.py`）：`async focus_conversation(page: Page, conversation_id: str) -> bool`
  - `FOCUS_METHOD == "cdp_bounds"` 时：`page.context.new_cdp_session(page)`（同一浏览器连接，不另开连接）→ `Browser.getWindowForTarget` → `Browser.setWindowBounds(FOCUS_BOUNDS)`；随后 `page.bring_to_front()`
  - 定位 `f'{CONVERSATION_SELECTOR}[{CONV_ID_ATTR}="{conversation_id}"]'`（`conversation_id` 先按 `ConversationId` 规则校验，不合规抛 `ValueError`）；找不到返回 `False`；找到则 `.click()` 一次，返回 `True`
  - 不调用 `fill`、`type`、`press`、`keyboard`、`evaluate` 写操作
- Produces（`ImWatcher`）：`async focus(shop_id: int, conversation_id: str, *, actor: str) -> Literal["opened", "not_found"]`
  - 该店没有运行中的常驻页 → `InvalidRequest("该店飞鸽未在接收")`
  - 经 `runner.run(shop_id, job, actor=actor)`；`FOCUS_METHOD == "relaunch_visible"` 时 job 外先 `stop(shop_id, reason="preempted", actor=actor)` 再 `start(shop_id, actor=actor, offscreen=False)`，之后在新页面上 `focus_conversation`（窗口保持可见到下一次每日重启，届时按 `offscreen=True` 重开）
  - 审计 `CallRecord(shop_id, "im.focus", actor, {}, {"result": result}, "ok" | "error", 0)`，不记会话 ID、昵称、正文
- Produces（API）：`POST /conversations/{shop_id}/{conversation_id}/open-in-flybird` → `ImFocusResult`（`result: Literal["opened", "not_found"]`）；未运行 → `InvalidRequest`；店不存在 → `NotFound`

- [ ] **Step 0: 实测（所有者在场，测试店）**：U12，`offscreen=True` 的常驻页经同一浏览器连接移回屏幕并置前是否可行，成立则 `FOCUS_METHOD = "cdp_bounds"`，否则 `"relaunch_visible"`；在 DOM 里找会话元素上与消息帧会话 short ID 对应的属性，填 `CONV_ID_ATTR`（找不到则按会话行文本里的买家标识定位，在本任务里改写定位规则后再实现）；点开自己的测试会话一次，确认只打开、不发送、输入框为空。记录只留本机，结论写进 flybird.md §5。
- [ ] **Step 1: 写失败测试**
  - `flybird_focus_test.py`（`FakePage` / `FakeCdpSession` 记录调用）：`test_cdp_bounds_then_bring_to_front_then_single_click`（调用序列恰为 `getWindowForTarget`、`setWindowBounds`、`bring_to_front`、`click`）；`test_selector_uses_conversation_id_attr`；`test_missing_element_returns_false_without_click`；`test_invalid_conversation_id_rejected`；`test_relaunch_visible_skips_cdp`
  - `flybird_readonly_guard_test.py`：`test_click_only_in_focus_module` 现在 `focus.py` 存在，断言 `.click(` 只在该文件出现且只一次；`bring_to_front`、`setWindowBounds` 只在该文件；全包仍不含 `.fill(`、`.type(`、`keyboard`、`.press(`、`.send(`
  - `im_watcher_test.py`：`test_focus_runs_in_shop_queue`；`test_focus_not_running_rejected`；`test_focus_relaunch_visible_reopens_with_offscreen_false`（`FakeRegistry.open_cloak` 第二次收到 `offscreen=False`）；`test_focus_audit_has_no_conversation_id`
  - `im_api_test.py`：`test_open_in_flybird_ok`；`test_open_in_flybird_not_running_400`；`test_open_in_flybird_requires_admin`
  - `openapi_test.py`：路径集合加 `/api/im/conversations/{shop_id}/{conversation_id}/open-in-flybird`
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/adapter/flybird_focus_test.py tests/adapter/flybird_readonly_guard_test.py tests/service/im_watcher_test.py tests/api/im_api_test.py tests/api/openapi_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS；导出 openapi 并 `pnpm gen:api`
- [ ] **Step 5: 提交** `feat(im): 在飞鸽中回复（置前该店窗口到会话，不发送）`

---

### Task 15: 前端：导航与消息页

**Files:**
- Modify: `frontend/src/components/custom/app-shell/logic/nav-items.ts`（`NavIcon` 加 `"messages"`；在「订单」组之后插入 `{ kind: "group", id: "service", label: "客服", icon: "messages", items: [{ path: "/messages", label: "消息", icon: "messages" }] }`）
- Modify: `frontend/src/components/custom/app-shell/components/side-nav.tsx`（`lucide-react` 导入加 `MessageSquare`；`ICONS` 加 `messages: MessageSquare`）
- Modify: `frontend/src/components/custom/app-shell/logic/nav-items.test.ts`
- Modify: `frontend/src/app.tsx`（`<Route path="/messages" element={<MessagePage />} />`）
- Modify: `backend/app/domain/notification_rules.py`（`link_for` 里 `new_message`、`im_stopped`、`im_waiting` 现暂指 `/shops?shop=<id>`，本阶段改回 `/messages?shops=<id>`，`im_waiting` 加 `quick=overdue`；同步改三处测试）
- Modify: `frontend/src/lib/query-keys.ts`（`imRoot()`、`imStatus()`、`imConversations(shopIds, filters)`、`imCounts(shopIds)`、`imThread(shopId, conversationId)`）
- Create: `frontend/src/pages/message/index.tsx`（≤ 80 行，只装配）
- Create: `frontend/src/pages/message/components/message-page-view.tsx`、`im-metrics.tsx`、`im-status-strip.tsx`、`conversation-list.tsx`、`conversation-row.tsx`、`thread-pane.tsx`、`message-line.tsx`
- Create: `frontend/src/pages/message/hooks/use-message-page.ts`、`use-thread.ts`
- Create: `frontend/src/pages/message/logic/message-page.ts`、`message-page.test.ts`
- Create: `frontend/src/pages/message/message-page.module.css`、`frontend/src/pages/message/index.test.tsx`

**Interfaces:**
- 类型一律用生成的 `components["schemas"]["ImConversation" | "ImConversationPage" | "ImCounts" | "ImThread" | "ImMessage" | "ImShopStatus" | "ImFocusResult"]`，不手写
- `logic/message-page.ts`：
  - `IM_QUICK = ["unread", "waiting", "overdue", "today"] as const`；`type ImQuick = (typeof IM_QUICK)[number]`
  - `waitSecondsAt(waitingSince: string | null, now: Date) -> number | null`；`formatWait(seconds: number | null) -> string`（`""`、`45 秒`、`3 分 10 秒`、`1 小时 5 分`）
  - `isOverdue(seconds: number | null) -> boolean`（> 180）
  - `senderLabel(role) -> "买家" | "客服" | "智能客服" | "平台"`
  - `ordersLink(shopId: number) -> string`（`withShopFilter("/orders", [shopId])`；订单接口没有买家筛选，只带店铺）
  - `selectionParam`：`conv=<shop_id>:<conversation_id>` 的读写；`canRestart(state)`（`needs_refresh`、`backoff`、`stopped`）
- `use-message-page.ts`：`useShopFilter()`；`useQuickFilter(IM_QUICK)`；URL 参数 `unread=1`（只看未读）、`sort`、`order`、`page`（沿用 `use-list-sort`）；查询 `/api/im/conversations`、`/api/im/conversations/counts`、`/api/im/status`；`useEventSubscription` 订阅 `im_unread_changed`、`im_wait_changed`、`im_stopped` 时失效 `imRoot`；每 30 秒重取一次；页面内每秒一个时钟用于走秒
- `use-thread.ts`：按选中项查 `/api/im/conversations/{shop_id}/{conversation_id}/messages`；`openInFlybird()` 调 `POST .../open-in-flybird`，`not_found` 时提示「飞鸽里没找到该会话」
- 页面结构：
  - 顶部一行四张 `MetricCard`：「未读会话」（`info`）、「待回复」（`warning`）、「超 3 分钟未回复」（`danger`）、「今日会话」（`neutral`），`{...cardProps(key)}`
  - 状态条：只列不在「接收中」的已开启店铺，每店一行 `Alert`（店名、`state_label`，`canRestart` 时带「重新连接」）
  - 两栏：左栏工具条只有「只看未读」`Checkbox`（店铺由全局筛选控制）；列表行：买家、店铺、最后一条预览、等待时间、未读数徽标；超 3 分钟的行 `data-overdue` 用 `--danger` 标红；底部 `components/custom/list-pager`；默认按等待时间倒序
  - 右栏：头部买家、店铺、等待时间；正文按时间列消息，每条显示发送方与时间，平台消息用居中弱化的系统行；底部两个按钮「在飞鸽中回复」「查看订单」；**没有输入框**
  - 未选中会话时右栏为空状态「选择一个会话」；列表为空「暂无会话」。不放说明小字，不做导航未读小圆点（铃铛已计数）

- [ ] **Step 1: 写失败测试**
  - `message-page.test.ts`：`formatWait` 各档；`isOverdue` 边界 180 / 181；`waitSecondsAt`；`senderLabel`；`ordersLink(3) === "/orders?shops=3"`；`selectionParam` 读写往返；`canRestart`
  - `nav-items.test.ts`：「客服」组紧跟「订单」组，唯一一项为 `/messages`「消息」；`pageTitle("/messages") === "消息"`
  - `pages/message/index.test.tsx`（假接口，`测试小铺` / `测试买家` / `在吗`）：
    - 渲染四张卡；点「超 3 分钟未回复」后请求带 `quick=overdue`，再点清除
    - 勾「只看未读」后请求带 `unread=true`
    - 超 3 分钟的行带 `data-overdue`
    - 点一行后右栏显示买家、店铺、等待时间与消息；平台消息渲染为系统行
    - 点「在飞鸽中回复」发 `POST .../open-in-flybird`；「查看订单」链接为 `/orders?shops=1`
    - 页面里 `queryAllByRole("textbox")` 为空
    - 收到 `im_wait_changed` 事件后重新请求列表
- [ ] **Step 2:** `cd frontend && pnpm test` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** `pnpm test && pnpm lint && pnpm build` → PASS；`bash scripts/ci/check-file-length.sh` → PASS
- [ ] **Step 5: 提交** `feat(frontend): 客服消息页（计数卡、跨店会话、只读详情、在飞鸽中回复）`

---

### Task 16: 文档与冒烟

**Files:**
- Modify: `docs/design/frontend.md`（导航分组加「客服 > 消息」；消息页两栏结构与「无输入框」约定）
- Modify: `docs/design/backend.md`（§5.17 加一条「`adapter/flybird/focus.py` 是唯一的页面点击，只在所有者点『在飞鸽中回复』时执行」）
- Modify: `docs/api/flybird.md`（§5 U12 链接到 Task 14 的做法）

- [ ] **Step 1:** 按上面修改；`bash scripts/ci/check-secrets.sh && bash scripts/ci/check-file-length.sh` → PASS
- [ ] **Step 2: 手工冒烟**（所有者，测试店）：侧栏「客服 > 消息」；另一账号发 2 条消息 → 「未读会话」「待回复」各 1，行在最上；3 分钟后行变红、「超 3 分钟未回复」为 1、铃铛强提醒；点该行 → 右栏显示 2 条买家消息（兜底时只显示最新预览）；点「在飞鸽中回复」→ 该店浏览器窗口置前并打开该会话，输入框为空、没有发出任何消息；在飞鸽里回复后 → 行不再红、强提醒解决；「查看订单」跳到订单页且只选中该店
- [ ] **Step 3: 提交** `docs: 飞鸽消息页的导航、页面约定与点击边界`

---

## 自检记录

| 审查项 | 处理 |
|---|---|
| 只读 | 后台零点击；唯一点击在 `focus.py`，守卫测试锁定次数与位置；全站无输入框（Task 14、15） |
| 出口 | 置前用同一浏览器连接的 CDP 会话；兜底重开也经登记表与 ShopRunner，无直连 |
| 数据 | 正文只经管理员接口返回，不进日志与审计；`im.focus` 审计不含会话 ID |
| 买家名 | 推送无昵称，统一「买家 · 尾号」，写进规则与测试 |
| 一致 | 计数卡键名 = `ImQuick` = 前端 `IM_QUICK`；排序白名单与 `list_sort_test` 对应 |
| 长度 | 本文件 ≤ 600 行；`index.tsx` ≤ 80 行，组件按区块拆分 |
