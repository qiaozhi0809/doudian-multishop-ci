# 飞鸽消息聚合（只读）实施计划 · 第一阶段：实测、采集与提醒

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 开启「接收飞鸽消息」的店铺，在本系统里只读拿到消息记录、按会话的待回复数，有新消息、买家等待超 3 分钟时经通知中心提醒。不提供发送。消息页（接口与界面）在第二阶段：`2026-11-26-flybird-messages-page.md`。

**Architecture:** 每家开启的店用该店自己的 CloakBrowser 资料目录，经**浏览器登记表**（`Purpose.IM`）调用 `launch_cloak` 与该店出口，常驻一个飞鸽工作台页面（有头 + `offscreen=True`，每天重启一次）。只被动监听页面自己的 WebSocket 下行帧（`framereceived`）：cmd 500 类型 1000 的帧解析成消息（Task 0 已确认字段），会话与待回复数由消息推出；页面自己的会话列表 XHR 只用来对齐会话键。页面加载前注入一段只丢弃「标记已读」「输入状态」两种上行帧的脚本，并 `abort` 已读的 HTTP 兜底请求（flybird.md §4）。启动与重启都经 `ShopRunner`，另有全局常驻页上限、按店退避、刷新限额与审计。会话快照在内存；消息写 `im_message`（保留 30 天）。未读变化发 `IM_UNREAD_CHANGED`，等待超时变化发 `IM_WAIT_CHANGED`，由 `NotificationFeed` 翻译成 `new_message` 事件与 `im_waiting` 强状态。

**Depends on:** 分支 `feat/browser-lifecycle`（提交 `f01f22e`、`77ebb00`，浏览器登记表与关闭原因回调）**先合并到 main**，之后才开始 Task 3、5、7、9。本计划用它的现有接口（`backend/app/adapter/browser/browser_registry.py`）：

```python
class Purpose(StrEnum): LOGIN = "login"; SCRAPE = "scrape"; IM = "im"
MAX_AGE_S: dict[Purpose, float]          # IM = 24 * 3600：到期由巡检关闭，持有方重新打开 = 每日重启
class BrowserRegistry:
    def open_cloak(self, profile_dir: Path, purpose: Purpose, proxy: dict | None, *,
                   offscreen: bool = False, max_age_s: float | None = None)  # async 上下文管理器，交出 Playwright 上下文
    async def close_shop(self, shop_id: int, reason: str) -> bool  # 关闭该店已登记的浏览器
    def list(self) -> list[BrowserInfo]; async def close_all(self, reason: str) -> None
```

同一资料目录已登记时 `open_cloak` 抛 `cloak_launch.CloakUnavailable(PROFILE_IN_USE)`；退出时限时关闭，超时强杀进程树。启动清理、5 分钟巡检、退出时 `close_all("shutdown")` 由该分支接进 lifespan，实例在 `app.state.browsers`（wiring 键 `"browsers"`，`Overrides.browsers`）；登记表按资料目录名识别 `shop_id`，所以目录必须是 `profiles_dir / str(shop_id)`。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy Core / Alembic / asyncio；CloakBrowser（Playwright 持久化上下文）；React 19 + TanStack Query + 现有 SSE（`lib/use-events.ts`）。

**Spec:** `docs/api/flybird.md`（实测记录、实现方向、未验证项 U1 到 U12）；通知约定见 `docs/superpowers/specs/2026-11-26-notification-center-design.md`、`docs/design/backend.md` §5.17 / §5.18。

## Global Constraints

- **只读**：不构造、不重放、不发送任何 WebSocket 帧；不用 `page.request`、页面内 `fetch` 等伪造请求；后台流程不点击任何会话、不输入任何内容。唯一例外是第二阶段的「在飞鸽中回复」：只在所有者点击时，在 `adapter/flybird/focus.py` 里把窗口置前并点开该会话，仍不输入、不发送。`adapter/flybird/` 有静态守卫测试（Task 2）。
- **不标已读（所有者裁定 2026-11-26）**：页面在只有一个买家时会自动打开会话，并对新消息自动标已读。`adapter/flybird/read_guard.py`（Task 3）是唯一允许拦截的地方：注入脚本包装 `WebSocket.prototype.send`，只丢弃发往 `WS_HOST`、cmd 属于 `DROP_CMDS`（2002 已读、2031 输入状态）的帧；`context.route` 只对 `MARK_READ_PATH` 执行 `abort`。不改写、不伪造任何帧或响应。副作用：每来一条买家消息页面会断开长连接约 12 秒再重连，所有者已接受。
- **出口与浏览器**：常驻页只经浏览器登记表打开，即 `browsers.open_cloak(profiles_dir / str(shop_id), Purpose.IM, playwright_proxy(runner.proxy_for(shop_id)), offscreen=True)`（`max_age_s` 不传，用 `MAX_AGE_S[Purpose.IM]`），继承 `launch_cloak` 的种子指纹、WebRTC 限制、预下载检查，以及登记表的 pid 登记、限时关闭与孤儿清理。不用无头，不加 `--window-size` 等指纹参数，不另开直连。出口不可用就停，**绝不退回直连**。
- **ShopRunner**：每次启动或重启都经 `runner.run(shop_id, job, actor=...)`：precheck（未暂停、出口就绪、会话有效）+ 该店串行队列。扫码登录、同步收款信息需要资料目录时，先经 `browsers.close_shop` 让出常驻页（Task 5）。
- **选店**：`shop.status == "active"`、未暂停、`shop.im_enabled == 1`。与 `channel` 无关。开关默认关。
- **不需要 selfId**：工作台不带参数即可用（Task 0 U7），不存、不填客服账号 ID。
- **不刷屏**：退避按原因指数增长、有上限；每店每天启动 ≤ 24 次（含每日重启）；页面刷新每店间隔 ≥ 10 分钟且每天 ≤ 6 次；读取去抖为前沿 + 尾沿、间隔 ≥ 30 秒。
- **通知**：`new_message` 中档、按店合并、数量变多再提醒；每次启动后的第一次读取只建基线不提醒。`im_waiting` 强状态 `im_wait:{shop_id}`（横幅 + 声音），该店没有等待超 3 分钟的会话时解决；所有者可改为中档，只改 `notification_rules.LEVEL_BY_KIND` 一行。都经事件总线，不另开 SSE 通道。
- **数据**：买家昵称、会话预览只在内存快照；消息正文只写 `im_message` 表，**不进日志、审计、事件载荷与通知标题**（事件只带数量）。`im_message` 保留 30 天，在每日清理里删除。测试数据一律虚构（`测试买家`、`在吗`、`conv-test-1`、`msg-test-1`）。
- 迁移编号 `0012`（main 最新为 `0011_notification.py`），包含 `shop.im_enabled` 与 `im_message` 表。
- 文件长度：`*.py` ≤ 400、`*.ts/tsx` ≤ 300、页面 `index.tsx` ≤ 80；四层分层（engineering-rules 2.1）；常量集中在 `adapter/flybird/endpoints.py`（5.1）。
- 文案：中文、简短、无破折号，不放解释性小字；只有开关确认弹窗写一句说明。
- 测试命令统一 `cd backend && uv run pytest -q ...`、`cd frontend && pnpm test`。每个任务一个提交，信息末尾 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。

## Review Focus

1. **只读是否真的只读**：任何后台路径都不能发帧、发请求、点会话；拦截只丢弃，不改写。看 Task 2 守卫测试、Task 3 的监听器与 `read_guard.py`。
2. **资料目录争用**：常驻页占着资料目录时，扫码登录与同步收款信息能否先经 `close_shop` 让出、结束后按退避回来，且不出现「资料目录正被占用」。→ Task 5、7。
3. **重启风暴**：需要登录、暂停、停用、出口异常、11001、空列表、每日重启时，是否经关卡、按退避，没有快速重连循环。→ Task 4、7。
4. **已读**（U5）：注入脚本与 `abort` 生效后，买家消息在抖店侧保持未读；拦截失效（页面改版）时要能发现。→ Task 3、11 冒烟。
5. **消息正文不外泄**：只进 `im_message`；日志、审计、事件、通知里都没有。→ Task 1、6、7 的断言。
6. **等待计时**：消息来源与「未读起点」兜底两种算法都有测试；强状态只按店一条。→ Task 4、6、8。
7. **多店**：全局常驻页上限生效；任何状态都按 `shop_id` 分开。

---

### Task 0: 实测验证（已完成 2026-11-26，结论：go）

在测试店、该店资料目录与出口下录制了五轮（可见窗口，只被动记录），结论见 `docs/api/flybird.md` §3 到 §5。要点：

- 工作台不需要 `selfId`（U7）；会话列表 XHR 有会话键但没有昵称、预览，`unreadCount` 恒为 0（U1），所以**未读与待回复由消息推出**，不读 DOM（U4 不需要）。
- 新消息帧与正文（U3、U9）：cmd 500 类型 1000；发送方看扩展键 `sender_role`（U11），客服在别处回复本页也收到。
- 自动标已读（U5）：成立，用 `read_guard.py` 拦截解决，所有者接受「每条新消息断开重连一次」。
- 在线接待（U6）：单客服账号的测试店未见影响；多客服账号的店未验证，开关确认弹窗写明。
- 未测：`offscreen` 下连接是否保持（U8，Task 11 冒烟确认）、11001（U2，沿用早期结论）、窗口置前（U12，第二阶段）。

Task 2 的常量按上述结论直接给出，不再留占位。

---

### Task 1: 迁移 0012 与存储

**Files:**
- Create: `backend/migrations/versions/0012_im.py`
- Create: `backend/app/store/im_schema.py`（`im_message` 表，写法同 `notification_schema.py`）
- Create: `backend/app/store/im_message_store.py`
- Modify: `backend/app/store/schema.py`（`shop` 加 `im_enabled`，带「迁移 0012」注释）
- Modify: `backend/app/store/shop_store.py`（`update_fields` 白名单加 `im_enabled`）
- Test: `backend/tests/store/migration_test.py`、`backend/tests/store/migration_0012_test.py`、`backend/tests/store/shop_store_test.py`、`backend/tests/store/im_message_store_test.py`

**Interfaces:**
- Produces（迁移）：`revision = "0012"`，`down_revision = "0011"`；`shop.im_enabled INTEGER NOT NULL server_default "0"`；`downgrade` 按 0010 的写法删列并 `drop_table("im_message")`
- Produces（`im_message`）：`id`；`shop_id INTEGER NOT NULL FK shop.id`；`conversation_id TEXT NOT NULL`；`message_id TEXT NOT NULL`；`sender_role TEXT NOT NULL`（`buyer | agent | robot | platform`）；`text TEXT NOT NULL`；`sent_at`、`captured_at`（`_NOW` 列，`NOT NULL`）；唯一索引 `uq_im_message_shop_msg (shop_id, message_id)`；索引 `idx_im_message_conv (shop_id, conversation_id, sent_at)`、`idx_im_message_captured (captured_at)`
- Produces（`im_message_store.py`）：
  - `insert_ignore(conn, shop_id: int, rows: Sequence[Mapping[str, str]], captured_at: str) -> int`（`ON CONFLICT DO NOTHING`，返回新增条数）
  - `list_for_conversation(conn, shop_id: int, conversation_id: str, *, limit: int = 200) -> list[dict]`（按 `sent_at` 正序，取最近 `limit` 条）
  - `recent_for_shop(conn, shop_id: int, since: str) -> list[dict]`（启动时恢复等待计时用）
  - `purge_before(conn, cutoff: str) -> int`（按 `captured_at`）

- [ ] **Step 1: 写失败测试**
  - `migration_test`：schema 与迁移逐列一致（现有用例自动覆盖新列与新表）
  - `migration_0012_test.py::test_upgrade_adds_im_columns_and_table`：`upgrade_to_head(tmp_path / "app.db")` 后 `shop` 含 `im_enabled` 且默认 0；`im_message` 存在且有唯一索引
  - `migration_0012_test.py::test_existing_shops_default_off`：先升到 `0011` 插一家店，再升到 head，`im_enabled == 0`
  - `migration_0012_test.py::test_downgrade_drops_im_message`
  - `shop_store_test.py::test_update_fields_im_enabled`
  - `im_message_store_test.py`：`test_insert_ignore_dedupes_per_shop`（同店同 `msg-test-1` 两次只一条；另一店同 ID 可写）；`test_list_for_conversation_ordered_and_limited`；`test_recent_for_shop_since`；`test_purge_before_uses_captured_at`
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/store/migration_test.py tests/store/migration_0012_test.py tests/store/shop_store_test.py tests/store/im_message_store_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** 同上 → PASS
- [ ] **Step 5: 提交** `feat(store): 店铺飞鸽开关与消息记录表（迁移 0012）`

---

### Task 2: 飞鸽常量与解析（纯函数）

**Files:**
- Create: `backend/app/adapter/flybird/__init__.py`、`endpoints.py`、`parse.py`
- Create: `backend/tests/fixtures/flybird/conv_list_ok.json`、`conv_list_11001.json`（虚构值）；帧夹具在测试里用小工具按 flybird.md §3 的字段号手工拼（虚构值）
- Test: `backend/tests/adapter/flybird_parse_test.py`、`backend/tests/adapter/flybird_readonly_guard_test.py`

**Interfaces:**
- Produces（`endpoints.py`，值来自 Task 0，见 flybird.md §2 到 §4）：
  - `WORKSPACE_URL = "https://im.jinritemai.com/pc_seller_v2/main/workspace"`（不带参数）
  - `CONV_LIST_HOST = "pigeon.jinritemai.com"`；`CONV_LIST_PATH = "/chat/api/backstage/conversation/get_current_conversation_list"`；`CONV_FIELDS = {"key": "subConversationId", "short_id": "parentConShortId", "last_at": "coreInfo.versionTime"}`
  - `WS_HOST = "ws.fxg.jinritemai.com"`；`ERR_VERSION_TOO_LOW = 11001`
  - 帧：`FRAME_PAYLOAD = 8`；`PAYLOAD_CMD = 1`；`PAYLOAD_PUSH = 6`；`CMD_MESSAGE = 500`；`CMD_NOTIFY = 504`；`NEW_MESSAGE_CMDS = frozenset({500, 504})`
  - 消息体（cmd 500 → 字段 500 → 字段 5）：`MSG_FIELDS = {"message_id": 3, "conversation_id": 5, "type": 6, "text": 8, "ext": 9, "sent_at_ms": 10}`；`CHAT_MSG_TYPE = 1000`（其他类型是系统命令，丢弃）
  - 发送方：`ROLE_EXT_KEY = "sender_role"`；`ROLE_BY_VALUE = {"1": "buyer", "2": "agent", "4": "robot"}`；没有该键 → `platform`
  - 平台等待提醒：外层 `service == 1`、`method == 5`、payload 编码 `json`，`data.attention_time`（秒）；只记录，不作为计时来源
  - 拦截（只给 `read_guard.py` 用）：`DROP_CMDS = frozenset({2002, 2031})`；`MARK_READ_PATH = "/pigeon_im/*/conversation/mark_read"`
- Produces（`parse.py`）：
  - `@dataclass(frozen=True) class ConvListResult: code: int; keys: dict[str, str]`（`short_id → key`）
  - `SenderRole = Literal["buyer", "agent", "robot", "platform"]`
  - `@dataclass(frozen=True) class Message: conversation_id: str; message_id: str; sender_role: SenderRole; text: str; sent_at: str`（`__repr__` 不含 `text`）
  - `is_conv_list_url(url: str) -> bool`（主机必须是 `CONV_LIST_HOST`）
  - `parse_conv_list(payload: dict) -> ConvListResult`（`code != 0` 时 `keys={}`，不抛异常）
  - `frame_cmd(raw: bytes) -> int | None`（payload 字段 1 的 varint；格式不对、payload 不是 `pb` 时返回 `None`）
  - `is_new_message_frame(raw: bytes) -> bool`
  - `parse_message_frame(raw: bytes) -> list[Message]`（只解码；cmd 不是 `CMD_MESSAGE`、类型不是 `CHAT_MSG_TYPE` 或字段缺失返回 `[]`；`sent_at` 由毫秒转 ISO）
  - 不提供任何编码函数

- [ ] **Step 1: 写失败测试**（`flybird_parse_test.py`）
  - `test_conv_list_url_requires_pigeon_host`：`im.jinritemai.com` 同路径 → `False`
  - `test_parse_conv_list_ok`：夹具 → `keys == {"1001": "conv-test-1"}`
  - `test_parse_conv_list_version_too_low`：`code == 11001`，`keys == {}`
  - `test_frame_cmd_reads_payload_field1`：手工拼外层帧（payload 字段 1 = 500）→ 500
  - `test_frame_cmd_garbage_returns_none`：`b"\xff\xff"` → `None`；`json` 编码的平台提醒帧 → `None`
  - `test_new_message_frame_500_and_504`；`test_heartbeat_16001_not_new_message`
  - `test_parse_message_frame_buyer_text`：类型 1000、`sender_role=1`、正文 `在吗` → `Message("1001", "msg-test-1", "buyer", "在吗", ...)`
  - `test_parse_message_frame_roles`：`2` → agent，`4` → robot，无键 → platform
  - `test_parse_message_frame_system_types_dropped`：类型 50001 / 50002 → `[]`
  - `test_parse_message_frame_truncated_returns_empty`
  - `test_message_repr_hides_text`：`"在吗" not in repr(msg)`
- [ ] **Step 2: 守卫测试**（`flybird_readonly_guard_test.py`）
  - `test_flybird_adapter_has_no_write_paths`：读 `app/adapter/flybird/*.py` 源码，断言不含 `.send(`、`encode`、`.request.`、`fetch(`、`.fill(`、`.type(`、`keyboard`、`.press(`、`.dispatch_event(`、`fulfill`、`continue_`
  - `test_route_only_in_read_guard`：`.route(`、`add_init_script` 只允许出现在 `read_guard.py`；`read_guard.py` 里的 route 处理函数只调用 `abort`
  - `test_click_only_in_focus_module`：`.click(`、`bring_to_front`、`setWindowBounds` 只允许出现在 `focus.py`（第二阶段新增；此时该文件不存在，断言其余文件都不含）
- [ ] **Step 3:** `cd backend && uv run pytest -q tests/adapter/flybird_parse_test.py tests/adapter/flybird_readonly_guard_test.py` → FAIL
- [ ] **Step 4: 实现**
- [ ] **Step 5:** → PASS
- [ ] **Step 6: 提交** `feat(adapter): 飞鸽常量与只读解析（会话、消息）`

---

### Task 3: 常驻页面适配器

**前置：** `feat/browser-lifecycle` 已合并。

**Files:**
- Create: `backend/app/adapter/flybird/page.py`、`backend/app/adapter/flybird/read_guard.py`、`backend/app/adapter/flybird/read_guard.js`
- Test: `backend/tests/adapter/flybird_page_test.py`、`backend/tests/adapter/flybird_read_guard_test.py`

**Interfaces:**
- Consumes: `BrowserRegistry.open_cloak` 交出的 Playwright 上下文（本类不自己启动浏览器）；Task 2 的常量与解析
- Produces:
  - `read_guard.py`：`async install(context: BrowserContext) -> None`：`context.add_init_script(path=read_guard.js)`，再 `context.route("**" + MARK_READ_PATH + "*", _abort)`；`_abort` 只做 `await route.abort()` 并计数（`blocked_count() -> int`，不记 URL 参数）
  - `read_guard.js`：用 `Proxy` 包装 `WebSocket.prototype.send`；数据是 `ArrayBuffer` 或 TypedArray、连接主机是 `WS_HOST`、payload 字段 1 的 cmd 在 `DROP_CMDS` 时直接返回，其余原样调用；解析出错一律照常发送。常量由 `read_guard.py` 从 `endpoints.py` 渲染进脚本，JS 里不另写数字
  - `FrameSink = Callable[[bytes], None]`；`ListSink = Callable[[ConvListResult], None]`；`MessageSink = Callable[[list[Message]], None]`
  - `class ImPage`：
    - `@classmethod async attach(cls, context: BrowserContext, *, on_frame: FrameSink, on_list: ListSink, on_messages: MessageSink) -> ImPage`（先 `read_guard.install(context)`，再取或建一个页面、注册监听，最后打开 `WORKSPACE_URL`；`install` 失败就抛错，不打开页面）
    - `async reload() -> None`
    - `page` 属性（只给第二阶段 `focus.py` 用）；`closed: bool`（页面或上下文关闭时为真）
  - 监听：`page.on("websocket")` 只接 `WS_HOST` 的连接，`ws.on("framereceived")` 只处理 `bytes`：先交给 `on_frame`，再 `parse_message_frame` 非空时交给 `on_messages`；`page.on("response")` 只处理 `is_conv_list_url`（→ `on_list`），`json()` 失败忽略。长连接断开重连是常态（flybird.md §4），不当错误
  - 关闭由登记表的上下文管理器负责，本类不调用 `context.close()`

- [ ] **Step 1: 写失败测试**（`FakeContext` / `FakePage` / `FakeWebSocket`，不启动真浏览器）
  - `test_attach_installs_guard_before_navigation`：调用顺序 `add_init_script` → `route` → `goto(WORKSPACE_URL)`
  - `test_guard_install_failure_does_not_open_page`
  - `test_frames_from_other_hosts_ignored`；`test_text_frames_ignored`
  - `test_message_frame_forwarded_to_on_messages`（手工拼的 cmd 500 类型 1000 帧）
  - `test_conv_list_response_parsed_and_forwarded`；`test_non_list_response_ignored`；`test_bad_json_ignored`
  - `test_ws_reconnect_keeps_listening`：第二条连接的帧照样转发
  - `flybird_read_guard_test.py`：`test_route_handler_only_aborts`；`test_script_has_drop_cmds_from_endpoints`；`test_script_drops_mark_read_frame`（用 Node 跑渲染后的脚本，给假的 `WebSocket` 原型：cmd 2002 帧不调用原 `send`，16001 帧调用；没有 Node 时 `skip`）
  - `test_closed_when_page_closes`；`test_does_not_close_context`
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/adapter/flybird_page_test.py tests/adapter/flybird_readonly_guard_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(adapter): 飞鸽常驻页只读监听与已读拦截`

---

### Task 4: 规则（纯函数）

**Files:**
- Create: `backend/app/domain/im_rules.py`
- Test: `backend/tests/domain/im_rules_test.py`

**Interfaces:**
- Produces:
  - `ImState = Literal["off", "queued", "starting", "running", "backoff", "needs_refresh", "stopped"]`；`STATE_LABELS: dict[ImState, str]`（`未开启 排队中 启动中 接收中 稍后重试 需重新连接 已停止`）
  - `StopReason = Literal["error", "version_low", "preempted", "ineligible", "page_closed", "lifetime", "shutdown"]`
  - `pending_counts(msgs_by_conv: Mapping[str, Sequence[Message]]) -> dict[str, int]`：每个会话里「最后一条客服或智能客服消息之后的买家消息数」（未读的替代，flybird.md §2 说明 `unreadCount` 不可用）
  - `backoff_seconds(reason: StopReason, attempt: int) -> float | None`（`None` = 不自动重试）
  - `may_act(history: Sequence[datetime], now: datetime, *, min_gap: timedelta, per_day: int) -> bool`
  - 常量：`START_PER_DAY = 24`；`RELOAD_MIN_GAP = timedelta(minutes=10)`；`RELOAD_PER_DAY = 6`；`DEBOUNCE_S = 30`；`POLL_S = 300`；`VERSION_LOW_MAX = 3`；`WAIT_ALERT = timedelta(minutes=3)`；`WAIT_TICK_S = 30`；`MESSAGE_RETENTION = timedelta(days=30)`
  - `block_reason(shop: Mapping, profile: Mapping | None) -> ImState | None`：未开启 → `"off"`；非 active、已暂停、`egress_status` 属于 `unreachable / changed / duplicate` → `"stopped"`；否则 `None`
  - 等待计时：`waiting_since(msgs: Sequence[Message]) -> str | None`：最后一条客服或智能客服消息之后的第一条买家消息时间；平台消息不计；最后一条非平台消息是客服或智能客服 → `None`。智能客服的回复算「已回复」（智能客服接待中平台不发等待提醒，flybird.md §3）；**所有者可改为只认人工回复**，只改 `REPLY_ROLES` 一行
  - `REPLY_ROLES = frozenset({"agent", "robot"})`
    - `overdue_count(waits: Mapping[str, str | None], now: datetime) -> int`（等待 > `WAIT_ALERT` 的会话数）

- [ ] **Step 1: 写失败测试**
  - `test_pending_counts_after_last_reply`：买家、客服、买家、买家 → 2；智能客服回复后 → 0；只有平台消息 → 0
  - `test_backoff_error_doubles_and_caps`：60、120、240……封顶 3600
  - `test_backoff_version_low_stops_after_max`：`attempt >= VERSION_LOW_MAX` → `None`
  - `test_backoff_preempted_fixed_60`；`test_backoff_lifetime_zero`；`test_backoff_ineligible_none`
  - `test_may_act_gap_and_daily_cap`
  - `test_block_reason_cases`（逐条覆盖上面四种）
  - `test_waiting_since_buyer_after_agent`：客服 10:00、买家 10:01、买家 10:02 → `10:01`
  - `test_waiting_since_agent_last_is_none`；`test_waiting_since_robot_reply_counts`；`test_waiting_since_ignores_platform`（系统消息在最后仍按买家起点算）
  - `test_overdue_count_strictly_over_3_minutes`：恰好 3 分钟不计，3 分 1 秒计
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/domain/im_rules_test.py` → FAIL
- [ ] **Step 3: 实现**（超过 400 行时把等待计时拆到 `im_wait_rules.py`）
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(domain): 飞鸽只读的退避、限额、待回复与等待计时`

---

### Task 5: 资料目录让出（经登记表 `close_shop`）

**前置：** `feat/browser-lifecycle` 已合并。进程登记、最长存活、孤儿清理与巡检**全部用登记表**，本任务不重复做，也**不再新建 `ProfileLease`**：让出就是「`close_shop` 后由常驻页按退避重新打开」。本任务只给两个需要资料目录的流程加一个让出钩子；钩子的实现是 Task 7 的 `ImWatcher.yield_profile`。

**Files:**
- Modify: `backend/app/service/shop_login.py`（`ShopLoginFlow.__init__` 加 `yield_profile: YieldProfile | None = None`；`_scan_job` 返回的 job 开头 `await self._yield_profile(shop_id)`）
- Modify: `backend/app/service/shop_profile.py`（`ShopProfileService.__init__` 加同名参数；`scrape_card` 的 job 开头同上）
- Test: `backend/tests/service/shop_login_flow_test.py`、`backend/tests/service/shop_profile_scrape_test.py`

**Interfaces:**
- Produces: `YieldProfile = Callable[[int], Awaitable[bool]]`（定义在 `shop_login.py`，`shop_profile.py` 从那里导入）；返回值表示是否真的关了一个常驻页
- 让出发生在**已进入该店队列的 job 里**，所以常驻页关闭与扫码 / 抓取浏览器打开之间不会插入别的任务；登记表在 `close_shop` 返回前已注销该目录，随后的 `open_cloak(..., Purpose.LOGIN | SCRAPE, ...)` 不会撞上 `PROFILE_IN_USE`；常驻页之后按 `preempted` 退避（60 秒）经完整关卡回来，若届时扫码还在队列里就排在其后

- [ ] **Step 1: 写失败测试**
  - `shop_login_flow_test.py::test_scan_yields_im_profile_before_browser`：记录调用顺序 `["yield", "scan"]`，`yield` 收到该店 `shop_id`
  - `shop_profile_scrape_test.py::test_scrape_yields_im_profile_before_browser`
  - `shop_login_flow_test.py::test_scan_without_hook_unchanged`（钩子为 `None` 时现有行为不变）
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/service/shop_login_flow_test.py tests/service/shop_profile_scrape_test.py` → FAIL
- [ ] **Step 3: 实现**（钩子为 `None` 时行为与现在一致，现有测试不改）
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(service): 扫码与抓取前让出飞鸽常驻页的资料目录`

---

### Task 6: 单店会话循环（ImSession）

**Files:**
- Create: `backend/app/service/im_session.py`
- Modify: `backend/app/service/events.py`（`IM_UNREAD_CHANGED = "im_unread_changed"`，载荷 `{shop_id, unread, new}`，`unread` 为各会话待回复数之和、`new` 为本次新到的买家消息数；`IM_WAIT_CHANGED = "im_wait_changed"`，载荷 `{shop_id, waiting, overdue}`；`IM_STOPPED = "im_stopped"`，载荷 `{shop_id, state}`）
- Test: `backend/tests/service/im_session_test.py`

**Interfaces:**
- Consumes: `ImPage`（Task 3）、`im_rules`（Task 4）、`EventBus`
- Produces:
  - `@dataclass(frozen=True) class ConvView: conversation_id: str; key: str | None; last_text: str; last_role: SenderRole; last_at: str; pending: int; waiting_since: str | None`（`__repr__` 不含 `last_text`）
  - `class ImSession`：`__init__(self, shop_id: int, page: ImPage, events: EventBus, *, clock: Callable[[], datetime], sleep: Callable[[float], Awaitable[None]] = asyncio.sleep, reload_history: list[datetime], save_messages: Callable[[list[Message]], Awaitable[None]], history: list[Message])`
  - `on_frame(raw: bytes) -> None`：只记「最近一次收到帧」的时间（健康检查用）
  - `on_list(result: ConvListResult) -> None`：合并会话键；`code == ERR_VERSION_TOO_LOW` 时置 `version_low`
  - `on_messages(msgs: list[Message]) -> None`：按 `message_id` 去重后按会话追加到内存尾部（每会话只留最近 50 条），排入 `save_messages`；新到的买家消息数累加进待发的 `new`，置触发
  - `async run() -> StopReason`：等「触发或 `WAIT_TICK_S` 到期」；前沿 + 尾沿去抖（`DEBOUNCE_S` 内多次触发只发一次尾沿事件）；`version_low` 时按 `may_act(reload_history, ...)` 刷新一次，不允许就返回 `"version_low"`；连续 `POLL_S` 秒没有任何帧时刷新一次（同样受限额，超限返回 `"error"`）；页面关闭返回 `"page_closed"`；其他异常返回 `"error"`
  - 启动时用 `history` 建立各会话状态，**不发 `new`**（基线）；之后 `new` 只来自 `on_messages`
  - 未读合计或 `new` 变化时发 `IM_UNREAD_CHANGED`；`waiting` 或 `overdue` 变化时发 `IM_WAIT_CHANGED`；结束时发一次 `overdue=0` 的 `IM_WAIT_CHANGED`（停了就不再声称有人在等）；载荷只有数量
  - `snapshot() -> list[ConvView]`；`unread() -> int`；`stop() -> None`
- `reload_history` 由 watcher 按店持有并传入，重启后不清零；`history` 由 watcher 启动时从 `im_message_store.recent_for_shop(since=now-1d)` 读出

- [ ] **Step 1: 写失败测试**（`FakeImPage`、假时钟、记录式 sleep、真 `EventBus` + `subscribe`，参照 `tests/service/events_test.py`，不读私有队列）
  - `test_history_is_baseline_no_event_new`：`history` 里有 2 条未回复买家消息 → 首个事件 `unread == 2, new == 0`
  - `test_buyer_messages_publish_new`：再来 2 条 → `{"shop_id": 1, "unread": 4, "new": 2}`
  - `test_agent_reply_clears_pending_without_new`：客服消息 → `unread == 0, new == 0`
  - `test_duplicate_message_ids_counted_once`
  - `test_burst_messages_leading_and_trailing_event`：30 秒内 5 批 → 事件 2 次，`new` 合计 5
  - `test_silence_reloads_after_poll_s`
  - `test_version_low_reloads_once_then_returns_version_low`
  - `test_reload_respects_budget`：`reload_history` 已满 → 不刷新直接返回
  - `test_page_closed_returns_page_closed`
  - `test_messages_saved`：`on_messages` 后 `save_messages` 收到同一批
  - `test_wait_tick_publishes_overdue_when_crossing_3_minutes`：买家消息后时钟推进 3 分 1 秒 → `{"shop_id": 1, "waiting": 1, "overdue": 1}`
  - `test_agent_reply_clears_wait`：随后客服消息 → `overdue == 0`
  - `test_history_seeds_wait_after_restart`
  - `test_run_end_publishes_overdue_zero`
  - `test_event_payloads_have_counts_only`：三种事件载荷键集合恰为上面所列，且不含 `测试买家`、`在吗`
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/service/im_session_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(service): 飞鸽单店只读循环（基线、待回复、去抖、11001、等待计时）`

---

### Task 7: 生命周期管理（ImWatcher）

**前置：** `feat/browser-lifecycle` 已合并；Task 5 已完成。

**Files:**
- Create: `backend/app/service/im_watcher.py`
- Modify: `backend/app/config.py`（`im_max_browsers: int = Field(3, ge=1, le=10)`）
- Test: `backend/tests/service/im_watcher_test.py`（复用 `tests/service/support.py` 的 `Env` / `FakeEgress` / `audit_rows`；`FakeRegistry` 记录 `open_cloak` / `close_shop` 参数并交出 `FakeContext`，`close_shop` 会关掉该 `FakeContext`）

**Interfaces:**
- Consumes: `BrowserRegistry.open_cloak` / `close_shop`、`Purpose.IM`、`MAX_AGE_S`、`ShopRunner.run` / `proxy_for`、`ImSession`、`ImPage.attach`、`im_rules`、`periodic.active_shop_ids`、`shop_store`、`im_message_store`、`audit_store`
- Produces:
  - `@dataclass class ImStatus: shop_id: int; state: ImState; since: str; next_retry_at: str | None; last_error: str | None`
  - `class ImWatcher`：`__init__(self, engine, runner: ShopRunner, events: EventBus, browsers: BrowserRegistry, *, profiles_dir: Path, max_browsers: int, clock, sleep=asyncio.sleep, attach=ImPage.attach)`
  - `im_shop_ids() -> list[int]`：`active_shop_ids(engine)` 再筛 `im_enabled`
  - `async start(shop_id: int, *, actor: str, offscreen: bool = True) -> ImStatus`
  - `async stop(shop_id: int, *, reason: StopReason, actor: str) -> None`
  - `async restart(shop_id: int, *, actor: str) -> ImStatus`（手动「重新连接」：清零该店退避计数，仍走全部关卡）
  - `async reconcile(shop_id: int) -> None`：`block_reason` 非空则 `stop(..., "ineligible")` 并记状态；可用且未运行则 `start`
  - `async run(bus: EventBus, stop: asyncio.Event) -> None`：先对 `im_shop_ids()` 逐个 `start`，再订阅 `SHOP_STATUS_CHANGED` → `reconcile`
  - `status(shop_id) -> ImStatus`；`statuses() -> list[ImStatus]`；`snapshot(shop_id) -> list[ConvView]`；`page(shop_id) -> ImPage | None`（第二阶段用）
  - `async yield_profile(shop_id: int) -> bool`（Task 5 的钩子）：该店没有常驻页返回 `False`；有则记「让出中」，`await browsers.close_shop(shop_id, "preempted")`，等该店会话结束后返回 `True`
  - `async shutdown() -> None`：让全部会话结束、退出各自的上下文、取消重试任务（之后 lifespan 里登记表的 `close_all("shutdown")` 兜底）
- 启动流程：`block_reason` → `may_act(start_history, START_PER_DAY)` → 拿全局名额（`asyncio.Semaphore(max_browsers)`，等待期间状态 `queued`）→ `runner.run(shop_id, job, actor=actor)`，job 内：`proxy_for` 为 `None` 且该店 `egress_mode != "direct"` 时抛 `EgressUnavailable`；`browsers.open_cloak(profiles_dir / str(shop_id), Purpose.IM, playwright_proxy(proxy), offscreen=offscreen)` 经该店的 `contextlib.AsyncExitStack.enter_async_context` 进入（栈由 watcher 按店持有，job 返回后页面仍常驻，会话结束时 `aclose()`）；`attach(context, ...)`（内含已读拦截，失败即退出上下文并按 `error` 退避）
  - 停止原因判定：`open_cloak(..., on_close=cb)` 由登记表回传 `CloseReason`（`feat/browser-lifecycle` 77ebb00）：`expired` → `"lifetime"`（每日重启，按 0 秒退避经完整 `start` 重开，计入 `START_PER_DAY`）；`preempted` → `"preempted"`；`shutdown` → `"shutdown"`；`process_gone` 与页面自行关闭 → `"page_closed"`。不再按打开时长推断
  - `save_messages`：`asyncio.to_thread(im_message_store.insert_ignore, ...)`；写失败只记 `im.save_failed` 与条数，**不记正文**
  - `ImSession.run()` 返回后：`aclose()` 该店的栈、清除「让出中」、归还名额、写审计、按 `backoff_seconds` 安排重试（重试再走完整 `start`）；`None` 时：`version_low` → `needs_refresh` 并发 `IM_STOPPED`，`ineligible` → 等状态事件
  - `CloakUnavailable`、`ShopPaused`、`SessionExpired`、`EgressUnavailable`、`NotFound` 都在打开浏览器前或启动时被拦下，记 `last_error`（只记类型名或 `CloakUnavailable` 的面向用户消息）
- 审计：`CallRecord(shop_id, "im.start" | "im.stop", actor, {}, {"reason": reason, "read_blocked": n}, "ok" | "error", 0)`（`n` 为本次会话拦下的 HTTP 已读次数），不含正文

- [ ] **Step 1: 写失败测试**
  - `test_launch_via_registry_purpose_im_offscreen`：`FakeRegistry.open_cloak` 收到 `profiles_dir / "1"`、`Purpose.IM`、`playwright_proxy("http://u:p@127.0.0.1:9")`、`offscreen=True`，未传 `max_age_s`
  - `test_selects_active_enabled_shops_only`：`channel` 不影响结果
  - `test_paused_shop_never_opens_browser`
  - `test_precheck_failure_opens_no_browser`：`FakeEgress` 抛 `EgressUnavailable` → registry 未调用
  - `test_proxy_none_on_proxy_mode_refused`
  - `test_registry_cloak_unavailable_recorded`：`open_cloak` 抛 `CloakUnavailable(PROFILE_IN_USE)` → `last_error` 为面向用户消息、按 `error` 退避
  - `test_start_waits_for_shop_queue`：先占住该店队列，`start` 在其结束前不调用 registry
  - `test_global_cap_limits_open_pages`：3 家店、`max_browsers=2` → 2 个 running、1 个 queued；停一家后第三家启动
  - `test_status_changed_needs_login_stops_page`、`test_status_changed_egress_bad_stops_page`、`test_switch_off_stops_page`
  - `test_backoff_on_error_no_fast_loop`：连续失败 → 记录的 sleep 为 60、120、240
  - `test_version_low_repeated_sets_needs_refresh_and_stops_retrying`
  - `test_lifetime_end_restarts_through_gates`
  - `test_start_limit_per_day`：第 25 次启动被拒，状态 `backoff`
  - `test_attach_failure_closes_context_and_backs_off`
  - `test_yield_profile_closes_shop_and_waits`：`close_shop(1, "preempted")` 被调用，返回前会话已结束；无常驻页时返回 `False` 且不调用
  - `test_preempted_restarts_after_60s_through_gates`
  - `test_close_reason_maps_to_stop_reason`（expired/preempted/shutdown/process_gone 各一例）
  - `test_messages_persisted_and_text_not_logged`：`caplog` / structlog 捕获中不含 `在吗`；`im_message` 有一行
  - `test_audit_on_start_and_stop`：`audit_rows` 有 `im.start`、`im.stop`，摘要里没有正文
  - `test_shutdown_exits_all_contexts`：每个店的栈都已 `aclose`
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/service/im_watcher_test.py` → FAIL
- [ ] **Step 3: 实现**（超过 400 行时把重试安排拆到 `im_retry.py`）
- [ ] **Step 4:** → PASS；`uv run pytest -q` 全量 → PASS
- [ ] **Step 5: 提交** `feat(service): 飞鸽常驻页生命周期（登记表、关卡、名额、退避、审计）`

---

### Task 8: 接入通知中心

**Files:**
- Modify: `backend/app/domain/notification_rules.py`
- Modify: `backend/app/service/notifications.py`（`_ALERT_ON_GROWTH` 加 `new_message`）
- Modify: `backend/app/service/notification_feed.py`（`_handlers` 加三项；`reconcile_shop` 停用 / 删除分支的 family 元组加 `"im_wait"`）
- Test: `backend/tests/domain/notification_rules_test.py`、`backend/tests/service/notifications_test.py`、`backend/tests/service/notification_feed_test.py`

**Interfaces:**
- Produces:
  - `Kind` 加 `"new_message"`、`"im_stopped"`、`"im_waiting"`；`KindFamily` 加 `"im_wait"`（`state_key("im_wait", id)` → `im_wait:{id}`）
  - `LEVEL_BY_KIND`：`new_message`、`im_stopped` 为 `"medium"`；`im_waiting` 为 `"strong"`（**所有者可降为 `"medium"`，只改这一行**）
  - `link_for("new_message" | "im_stopped", shop_id)` → `/messages?shops=<id>`；`link_for("im_waiting", shop_id)` → `/messages?shops=<id>&quick=overdue`（参数名用 `_SHOP_PARAM`，经 `_with_query`）
  - `title_for("new_message", count=n)` → `「{店名} 新增 {n} 条未读消息」`；`title_for("im_stopped", detail=label)` → `「{店名} 飞鸽消息已停止接收：{label}」`；`title_for("im_waiting", count=n)` → `「{店名} {n} 个会话超 3 分钟未回复」`
  - Feed：`IM_UNREAD_CHANGED` → `new > 0` 时 `emit("new_message", shop_id=..., count=new)`；`IM_STOPPED` → `emit("im_stopped", shop_id=..., detail=STATE_LABELS[state])`；`IM_WAIT_CHANGED` → `overdue > 0` 时 `raise_state("im_wait", "im_waiting", shop_id=..., count=overdue)`，否则 `resolve_state("im_wait", shop_id=...)`
  - 现有强状态规则照用：30 分钟内再犯静默重开（`REOPEN_SILENT_WITHIN`），数量变化只更新不再响

- [ ] **Step 1: 写失败测试**
  - `notification_rules_test.py::test_new_message_level_link_title`（店名用 `测试小铺`）
  - `notification_rules_test.py::test_im_stopped_level_link_title`
  - `notification_rules_test.py::test_im_waiting_strong_link_quick_overdue_title`
  - `notifications_test.py::test_new_message_merges_per_shop_and_realerts_on_growth`：两次 `emit` 只有一条未读记录、`count == 5`，第二次 `alert` 为真
  - `notification_feed_test.py::test_im_unread_changed_new_zero_writes_nothing`
  - `notification_feed_test.py::test_im_unread_changed_writes_new_message`
  - `notification_feed_test.py::test_im_stopped_writes_medium_event`
  - `notification_feed_test.py::test_im_wait_overdue_raises_one_state_per_shop`：两次 `overdue` 2→3 只有一条 `im_wait:1`，`count == 3`
  - `notification_feed_test.py::test_im_wait_zero_resolves`
  - `notification_feed_test.py::test_disabled_shop_resolves_im_wait`
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/domain/notification_rules_test.py tests/service/notifications_test.py tests/service/notification_feed_test.py` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS
- [ ] **Step 5: 提交** `feat(notify): 新消息、等待超时与消息接收停止通知`

---

### Task 9: 状态接口、店铺字段、每日清理与组装

**Files:**
- Create: `backend/app/api/im_schemas.py`、`backend/app/api/im.py`
- Modify: `backend/app/api/shop_schemas.py`（`ShopRow` 加 `im_enabled: bool`；`ShopPatch` 加 `im_enabled: bool | None = None`）
- Modify: `backend/app/api/shop.py`（`update(...)` 多传 `im_enabled=body.im_enabled`）
- Modify: `backend/app/service/shop_admin.py`（`update` 接收 `im_enabled`；行数据带出该列；有变化时发 `SHOP_STATUS_CHANGED`）
- Modify: `backend/app/service/im_watcher.py`（`purge_messages(now: datetime) -> int`：`im_message_store.purge_before(now - MESSAGE_RETENTION)`）
- Modify: `backend/app/wiring.py`、`backend/app/main.py`
- Modify: `frontend/openapi.json`
- Test: `backend/tests/api/im_api_test.py`、`backend/tests/api/shop_api_test.py`、`backend/tests/api/openapi_test.py`、`backend/tests/service/shop_admin_test.py`、`backend/tests/service/im_watcher_test.py`、`backend/tests/api/daily_purge_test.py`

**Interfaces:**
- Produces（`im_schemas.py`）：`ImShopStatus`（`shop_id, shop_name, state, state_label, since, next_retry_at, last_error`）
- Produces（`api/im.py`，`router = APIRouter(prefix="/api/im", tags=["im"])`，全部 `Depends(require_admin)`）：
  - `GET /status` → `list[ImShopStatus]`（只列 `im_enabled` 的店）
  - `POST /shops/{shop_id}/restart` → `ImShopStatus`（开关未开 → `InvalidRequest`；店不存在 → `NotFound`）
  - 会话、消息与「在飞鸽中回复」接口在第二阶段
- `wiring.py`：`browsers = ov.browsers or REGISTRY`（该分支已有的写法，提为局部变量复用）；先建 `im = ImWatcher(engine, runner, events, browsers, profiles_dir=settings.profiles_dir, max_browsers=settings.im_max_browsers, attach=ov.im_attach or ImPage.attach, **clock_kw)`，再把 `yield_profile=im.yield_profile` 传给 `ShopProfileService`、`ShopLoginFlow`；返回字典加 `"im": im`；`Overrides` 末尾加 `im_attach: Callable | None = None`
- `main.py`，**只做插入，不改写现有行**：
  - 导入区按字母序插入 `from app.api import im as im_api`
  - 路由元组：在现有最后一项 `notification_api,` 之后追加 `im_api,`
  - lifespan `tasks` 列表追加 `asyncio.create_task(app.state.im.run(app.state.events, stop)),`
  - `finally` 里 `await app.state.tasks.shutdown()` 之前插入 `await app.state.im.shutdown()`（在登记表的 `close_all("shutdown")` 之前）
  - `_daily_backup` 的 `backup()` 里，通知清理的 `try` 块之后插入同样写法的一段：`await asyncio.to_thread(app.state.im.purge_messages, app.state.clock())`，日志 `im.messages_purged`（只记条数）/ `im.messages_purge_failed`，失败不算备份失败

- [ ] **Step 1: 写失败测试**
  - `im_api_test.py`：`test_requires_admin`；`test_status_lists_enabled_shops`；`test_restart_off_shop_rejected`；`test_restart_unknown_shop_404`
  - `shop_api_test.py`：`test_patch_im_enabled_roundtrip`
  - `shop_admin_test.py::test_im_switch_change_publishes_shop_status_changed`
  - `im_watcher_test.py::test_purge_messages_older_than_30_days`：31 天前一条删、29 天前一条留
  - `daily_purge_test.py::test_daily_job_purges_im_messages_after_backup`；`test_im_purge_failure_does_not_fail_backup`
  - `openapi_test.py`：路径集合加 `/api/im/status`、`/api/im/shops/{shop_id}/restart`
- [ ] **Step 2:** `cd backend && uv run pytest -q tests/api/im_api_test.py tests/api/shop_api_test.py tests/api/openapi_test.py tests/service/shop_admin_test.py tests/service/im_watcher_test.py` 及清理测试 → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** → PASS；`uv run ruff check . && uv run pytest -q` → PASS
- [ ] **Step 5: 导出类型**：`cd backend && uv run python -m app.main --export-openapi ../frontend/openapi.json`，再 `cd ../frontend && pnpm gen:api`
- [ ] **Step 6: 提交** `feat(api): 飞鸽状态接口、店铺飞鸽字段与消息清理`（含 `im.py`、`im_schemas.py`、`shop*.py`、`shop_admin.py`、`im_watcher.py`、`wiring.py`、`main.py`、`openapi.json`、`api-types.ts`）

---

### Task 10: 前端店铺开关

**Files:**
- Modify: `frontend/src/pages/shop/components/edit-shop-dialog.tsx`（开关「接收飞鸽消息」）
- Modify: `frontend/src/pages/shop/hooks/use-shop-dialogs.ts`（打开开关时先弹确认，复用 `components/confirm-dialog.tsx`）
- Test: `frontend/src/pages/shop/index.test.tsx`

**Interfaces:**
- 类型一律用生成的 `components["schemas"]["ShopRow" | "ShopPatch"]`，不手写
- 开关确认弹窗：标题「接收飞鸽消息」，正文一句「开启后会在后台常驻该店飞鸽页面，有多个客服账号的店铺尚未验证」，按钮「开启」「取消」
- 消息页、导航与「重新连接」入口在第二阶段

- [ ] **Step 1: 写失败测试**
  - `pages/shop/index.test.tsx::打开飞鸽开关先确认`：点开关出现确认弹窗，点「开启」才发 `PATCH`，载荷含 `im_enabled: true`
- [ ] **Step 2:** `cd frontend && pnpm test` → FAIL
- [ ] **Step 3: 实现**
- [ ] **Step 4:** `pnpm test && pnpm lint && pnpm build` → PASS
- [ ] **Step 5: 提交** `feat(frontend): 店铺飞鸽开关`

---

### Task 11: 文档与检查脚本

**Files:**
- Modify: `docs/superpowers/specs/2026-11-26-notification-center-design.md`（§4 强档加「飞鸽会话超 3 分钟未回复」，中档加「新消息（飞鸽）」「飞鸽消息停止接收」）
- Modify: `docs/design/backend.md`（§5.18 事件翻译表加 `im_unread_changed`、`im_wait_changed`、`im_stopped` 三行；§5.17 加一条「飞鸽常驻页经浏览器登记表（`Purpose.IM`，24 小时到期即每日重启）、`launch_cloak` 与该店出口打开，启动经 ShopRunner，扫码与抓取前经 `close_shop` 让出资料目录」）
- Modify: `docs/design/data-model.md`（加 `im_message` 表与 30 天保留）
- Modify: `docs/engineering-rules.md`（第一节「对外承诺」表加 `adapter/flybird`：飞鸽工作台页面的只读监听、已读拦截、常量与解析）
- Modify: `docs/gaps.md`（DOC-13 残留里补记 `refs/pull/15/head`）
- Modify: `scripts/ci/check-secrets.sh`（扫描范围加 `docs`；新增规则匹配 `selfId=?\s*[0-9]{12,}`、`worker_id"?:\s*[0-9]{12,}`）

- [ ] **Step 1:** 按上面修改；`bash scripts/ci/check-secrets.sh && bash scripts/ci/check-file-length.sh` → PASS
- [ ] **Step 2: 手工冒烟**（所有者，测试店，先关智能客服）：开关打开 → `GET /api/im/status` 为「接收中」；另一账号发 1 条消息 → 铃铛出现「新增 1 条未读消息」，抖店侧该消息**仍为未读**（审计 `read_blocked` ≥ 1，抖店后台无「已读」）；长连接断开后约 12 秒重连，期间页面未报错（2031 拦截后页面无异常提示）；`offscreen` 运行 1 小时连接仍在（U8）；3 分钟不回 → 强提醒横幅与声音；在飞鸽后台回复 → 该强状态解决；对该店点扫码登录 → 常驻页先关、登录完成后约 1 分钟恢复；关掉出口 → 状态「已停止」，日志无重连刷屏、无消息正文
- [ ] **Step 3: 提交** `docs: 飞鸽只读聚合的规则表、通知档位、数据表与检查脚本`

---

## 自检记录

| 审查项 | 处理 |
|---|---|
| B1 真实数据 | 计划与 flybird.md 只用占位与虚构值；Task 11 让 `check-secrets.sh` 扫 `docs/` |
| B2 直连外连 | 不写 Python WS 客户端；常驻页只经登记表与该店出口，无直连回退（Task 3、7） |
| B3 无头 / 绕过 launch_cloak | 只经 `browsers.open_cloak(..., Purpose.IM, ..., offscreen=True)`，内部走 `launch_cloak`，无 `--window-size`（Task 7） |
| B4 未经 ShopRunner | 启动经 `runner.run`；状态事件触发停止；全局名额；审计；经 `close_shop` 让出资料目录（Task 5、7） |
| B5 帧重放 | 不重放、不发送，无编码函数；守卫测试，点击只许在第二阶段 `focus.py`（Task 2） |
| B6 超长 | 本文件与第二阶段文件都 ≤ 600 行 |
| M1 / M2 | 迁移 0012；`upgrade_to_head(path)`；时钟可注入；不读私有队列 |
| M3 / M4 | 不需要 selfId（Task 0 U7）；选店按 active + 开关 |
| M5 | `new_message` 中档、按店合并、增长再提醒、启动基线，经 Feed；`im_waiting` 强状态按店一条 |
| M6 | 所有者改为恢复消息页：`im_message` 只存 cmd 500 推送解析出的消息（Task 0 U9），30 天清理，正文不进日志 |
| M7 | 会话键取消息帧里的会话 short ID，XHR 的 `subConversationId` 只做对齐，不用昵称哈希 |
| M8 | 后台不点击会话；页面自动打开会话时由 `read_guard` 拦下已读（所有者裁定）；开关默认关，确认弹窗一句 |
| M9 | 11001 刷新受限额，超限 `needs_refresh`；空列表长退避；每日启动上限含每日重启 |
| M10 | 不再按触发开浏览器；消息帧驱动；前沿 + 尾沿去抖；长时间无帧才刷新，受限额 |
| M11 | 不再自写 WS 客户端；进程登记、存活上限、孤儿清理、让出都交给登记表（`feat/browser-lifecycle`） |
| M12 / M13 / M14 | pydantic schema + 生成类型；`main.py` 只追加；消息页四层与导航见第二阶段 |
| 建议 | 发送方案「按所有者决定不实施」；补实验出口说明；U6 在线接待；`uv run pytest`；规则表与常量模块；数字预览不当未读 |
