# 飞鸽客服（IM）接口与协议

> 2026-11-26 实测（两轮：一次早期实验，一次实施计划 Task 0）。飞鸽是阶段三功能，本文件只记录已验证事实与未解决问题，**不含实现**，不含任何真实 ID、昵称、消息、token。

## 1. 工作台入口

| 项 | 值 |
|---|---|
| 工作台地址 | `https://im.jinritemai.com/pc_seller_v2/main/workspace`（**不需要** `selfId`，Task 0 实测不带参数即可正常接待） |
| 注意 | `/pc_seller_v2/main/chat` 是**空壳**（只渲染侧边栏，无会话区），不要用 |
| 客服账号 ID | 页面自己请求 `GET pigeon.jinritemai.com/backstage/currentuser` 的响应 `data.CustomerServiceInfo.id` 里有；本系统用不到 |
| 登录态 | 复用抖店后台 SSO（扫码登录后的资料目录），打开即已登录 |

## 2. HTTP 接口

会话列表（页面自己在加载时请求一次，GET，cookie 鉴权）：

```
GET https://pigeon.jinritemai.com/chat/api/backstage/conversation/get_current_conversation_list
    ?biz_type=4&PIGEON_BIZ_TYPE=2&pageNo=0&pageSize=...&_pms=1&device_platform=web&FUSION=true（页面另带 a_bogus 等签名）
```

- 返回标准 JSON：`{"code":0,"data":[...],"total":n}`；没有「当前会话」时 `data` 为空，有时非空（U1 已确认，早期实验的 `total:0` 只是当时没有当前会话）
- `data[]` 字段：`subConversationId`（会话键）、`parentConShortId`、`unreadCount`、`coreInfo.versionTime`、`coreInfoMap.open_time / countdown / countdown_time`、`securityBizConversationId`、`msgList`（实测为空）；**没有昵称和预览**
- `unreadCount` 实测一直为 0，**不能当未读数用**
- **必须打到 `pigeon.jinritemai.com`**：用相对路径会落到 `im.jinritemai.com`，返回 200 + HTML 首页（不报错，最坑）

消息相关（都是页面自己发的，protobuf body）：

| 用途 | 路径 | 何时出现 |
|---|---|---|
| 初次加载历史 | `POST fxg.jinritemai.com/pigeon_im/v1/message/get_message_by_init` | 加载时 |
| 增量拉取 | `POST fxg.jinritemai.com/pigeon_im/v3/message/get_user_message` | **每 30 秒一次**（三个收件箱各一次），也在收到 504 通知后立即拉；响应体结构见 §3「增量拉取响应」 |
| 按会话取 | `POST fxg.jinritemai.com/pigeon_im/v1/message/get_by_conversation` | 打开会话时 |
| 标记已读 | `POST fxg.jinritemai.com/pigeon_im/v3/conversation/mark_read` | 长连接上的已读请求没有回应时的兜底（见 §4） |
| 会话打开 | `POST fxg.jinritemai.com/pigeon_im/v2/conversation/create` | 自动打开会话时 |

其他：`GET /backstage/getConversationSummary`、`GET /backstage/data/conversationAreaRealtimeData`、`GET /backstage/onlineservice`（客服在线状态，加载时只读）。

## 3. WebSocket

### 连接

```
wss://ws.fxg.jinritemai.com/ws/v2?token=<token>&aid=1383&fpid=92&device_id=...&access_key=...
    &device_platform=web&version_code=10000&pigeon_source=web&PIGEON_BIZ_TYPE=2&pigeon_sign=<sign>
```

另有一条 `wss://frontier.snssdk.com/ws/v2`，只有文本 `hi` 心跳，与消息无关。

### 帧结构（明文 protobuf，不加密、不压缩）

外层帧：

| 字段 | 含义 |
|---|---|
| 1 | seq |
| 2 | logid / 时间戳 |
| 3 | service（业务帧 10001；平台提醒为 1） |
| 4 | method（业务帧 1；平台提醒为 5） |
| 5 | headers（重复的 `{1: key, 2: value}`；回执帧带 `is_ack` / `code`） |
| 7 | payload 编码：`pb` 或 `json` |
| 8 | payload |

业务帧的 payload（`pb`）：字段 1 = **cmd**，下行时字段 6 = 推送体（`{cmd: {...}}`），上行时字段 8 = 请求体。

| cmd | 方向 | 含义 |
|---|---|---|
| 16001 | 上行 + 回执 | 页面自己每 30 秒发的心跳 |
| 2000 | 上行 + 回执 | 打开会话后每 10 秒一次 |
| 500 | 下行 | **新消息推送**（含系统命令消息，见下） |
| 504 | 下行 | 新消息通知（消息类型 58002，只带会话与消息编号，不带正文；页面随后自己拉取） |
| 2002（请求体 604） | 上行 | **标记已读** |
| 2031 | 上行 | 输入状态（`{"input_status":0}`），打开会话时发 |
| 609 / 610 / 618 | 上行 | 打开会话时取参与者、会话信息 |

### cmd 500 消息体

路径：payload 字段 6 → 字段 500 → 字段 5。

| 字段 | 含义 |
|---|---|
| 3 | 服务端消息 ID |
| 5 | 会话 short ID（与会话列表 `parentConShortId` 对应） |
| 6 | 消息类型：**1000 = 聊天消息**；50001 / 50002 = 系统命令（会话变更、已读通知），不是聊天内容 |
| 7 | 发送方 uid（买家消息为空） |
| 8 | 正文（类型 1000 实测为纯文本，含表情占位如 `[点赞]`；其他类型待补） |
| 9 | 扩展键值（重复 `{1: key, 2: value}`） |
| 10 | 创建时间（毫秒） |

发送方判定（U11）看扩展键 `sender_role`：`1` 买家、`2` 人工客服、`4` 智能客服（同时有 `biz_sender=robot`、`robot_auto_answer=1`）；没有 `sender_role` 的为系统消息（如「客服 xx 接入」）。**客服在别的设备回复时，本页也会收到这条 500 推送**（类型 1000、`sender_role=2`）。

已读通知：类型 50001、扩展键 `s:command_type=1`，正文 JSON 含 `read_index`、`read_badge_count`、`conv_unread_union`，发送方是**做了已读的那一方**。

### 增量拉取响应（冒烟实测 2026-11-26）

`get_user_message` 的响应体与业务帧 payload 同构：字段 1 = cmd **12048**，字段 6 = `{12048: {...}}`，其中：

- 字段 1（重复）：`{1: 游标, 2: {1: 会话 short ID, 2: 消息体（重复）}}`，消息体字段与 cmd 500 完全相同（含扩展键 `sender_role`，另有买家昵称 `uname`）
- 字段 2：`{1: 消息体（重复）}`，实测都是系统命令（类型 50002）

**哪些消息只从这里来**：长连接因已读拦截断开期间、以及重连之后的买家消息，服务端只推 504（类型 58002 或 50013，不带正文），正文要靠页面随后的拉取。新会话人工接入前的第一条也是这样。所以只听 cmd 500 会漏消息，必须同时读页面自己收到的拉取响应。

### 平台等待提醒（payload 编码 `json`）

```
{"data":{"attention_content":"用户已等待超1分钟，请尽快回复","attention_time":60,"security_biz_conversation_id":"...","worker_id":<客服uid>,...}}
```

人工接待中的会话，从等待满 1 分钟起**每 30 秒**推一次（60、90、120 秒……）。智能客服接待时没有。

### 早期实验（已废弃的方向）

浏览器抓到建连帧后从 Python 外连重放，能收到推送；外连发出的消息帧无回显；页面内改写发送帧可以送达。**按所有者决定不实施**：本系统不构造、不重放、不发送任何帧。会话列表接口出现过 `code:11001`（「飞鸽版本过低，浏览器用户请刷新页面」），刷新后恢复。

## 4. 已读（所有者裁定，2026-11-26）

- **页面会自动打开会话**：当前会话列表只有一个买家时，工作台默认打开它（所有者观察，Task 0 录到 `get_by_conversation` 与 `conversation/create`）。
- **打开着的会话，每来一条买家消息，页面约 1 秒后自动标记已读**（上行 cmd 2002），服务端随即推来发送方为本客服的已读通知。买家与真人客服都会看到「已读」。
- **智能客服接待时，平台自己也会标已读**，与本页无关（关掉机器人后才能区分）。
- **拦截办法（已验证）**：
  1. 页面加载前注入脚本，包装 `WebSocket.prototype.send`（用 `Proxy`，`toString` 仍显示原生），只丢掉发往 `ws.fxg.jinritemai.com`、cmd 为 2002 的帧；
  2. 页面等不到回执，约 3 秒后改用 HTTP `pigeon_im/v3/conversation/mark_read` 兜底（连续两次），用 Playwright `context.route` 直接 `abort`。
  3. 结果：服务端没有推已读通知，消息保持未读。
- **副作用（所有者接受）**：每来一条买家消息，页面会主动断开长连接，3 到 12 秒后重连；之后的消息走 504 通知 + 页面拉取，本系统读拉取响应补上（§3），不丢消息。
- 输入状态（cmd 2031）同样拦掉，**未单独验证页面对此的反应**，在实施冒烟里确认。
- Playwright `page.route_web_socket` **不能用**：接管后页面不再建立长连接，只剩 30 秒拉取。

## 5. 实测结论（Task 0）

| 编号 | 问题 | 结论 |
|---|---|---|
| U1 | 页面自己的会话列表 XHR 能否返回数据 | **成立**：有当前会话时 `data` 非空；但只有会话键和时间，没有昵称、预览，`unreadCount` 一直为 0 |
| U2 | 11001 出现后刷新能否恢复 | Task 0 期间未出现；按早期实验，刷新一次恢复 |
| U3 | 哪些下行帧表示新消息 | **成立**：cmd 500（类型 1000）与 cmd 504；心跳是 16001 / 2000 的回执 |
| U4 | DOM 未读徽标与稳定会话 ID | 未取（有 U9 后不需要）；会话元素仍有 `data-kora="conversation"` |
| U5 | 只打开不点击是否会标已读 | **成立**，用 §4 的拦截解决（所有者接受副作用） |
| U6 | 是否把客服登记为在线、影响分流 | 测试店只有一个客服账号，加载时只读在线状态、不改；人工接入照常分给该账号。多客服账号的店未验证 |
| U7 | `selfId` 能否从页面读出 | 不需要：工作台不带 `selfId` 即可用 |
| U8 | 是否需要主动心跳；`offscreen` 时连接是否保持 | 页面自己每 30 秒发心跳；`offscreen` 未测（Task 0 用可见窗口） |
| U9 | 哪些下行帧携带正文 | **成立**：cmd 500 类型 1000，字段见 §3 |
| U10 | 不点击时页面是否自己按会话取消息 | 页面自动打开会话后会取（`get_by_conversation`，protobuf）；有 U9 后不解析 |
| U11 | 发送方能否区分、别处回复本页能否收到 | **成立**：`sender_role` 1 / 2 / 4；别处回复本页收得到 |
| U12 | `offscreen` 窗口能否移回屏幕并置前 | **成立**（2026-11-26）：同一浏览器连接经 CDP `Browser.setWindowBounds` 先恢复 `normal` 再设位置，`bring_to_front` 后可见；会话元素没有会话编号属性，按买家昵称（`uname`）文本定位；点开只打开会话，输入框为空 |
| U8 补充 | macOS 上屏幕外坐标会被挪回屏幕内 | 后台窗口其实一直露在桌面。macOS 改为启动后最小化，加 `--disable-renderer-backgrounding`、`--disable-background-timer-throttling`；实测最小化 14 分钟页面仍判为可见、心跳与消息照常（断连后的消息经拉取约 25 秒到）。Windows 的屏幕外窗口未在 Windows 上实测 |
