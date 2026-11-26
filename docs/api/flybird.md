# 飞鸽客服（IM）接口与协议

> 2026-11-26 实测。飞鸽是阶段三功能，本文件只记录已验证事实与未解决问题，**不含实现**。

## 1. 工作台入口

| 项 | 值 |
|---|---|
| 工作台地址 | `https://im.jinritemai.com/pc_seller_v2/main/workspace?selfId=<客服账号ID>` |
| 注意 | `/pc_seller_v2/main/chat` 是**空壳**（只渲染侧边栏，无会话区），不要用 |
| `selfId` | 客服账号 ID。形如 16 位数字（真实值不入库，按店配置）；不带时页面能开，但会话列表为空 |
| 登录态 | 复用抖店后台 SSO，打开即已登录 |

## 2. HTTP 接口（已打通）

会话列表（GET，cookie 鉴权，**不需要签名头**）：

```
GET https://pigeon.jinritemai.com/chat/api/backstage/conversation/get_current_conversation_list
    ?biz_type=4&PIGEON_BIZ_TYPE=2&pageNo=0&pageSize=200
    &_pms=1&device_platform=web&FUSION=true
```

- 返回标准 JSON：`{"code":0,"data":[...],"total":n}`
- **必须打到 `pigeon.jinritemai.com`**：用相对路径会落到 `im.jinritemai.com`，返回 200 + HTML 首页（不报错，最坑）
- 页面自身的请求额外带 `msToken` 与 `a_bogus`；不带这两个参数时实测返回 `total:0`，**是否因缺签名被降级尚未确证**

其他已知接口（未逐一验证参数）：

| 用途 | 路径 |
|---|---|
| 会话摘要 | `GET /backstage/getConversationSummary`（带 `security_user_id` / `security_conversation_id`） |
| 实时数据 | `GET /backstage/data/conversationAreaRealtimeData` |
| 消息历史 | `POST https://fxg.jinritemai.com/pigeon_im/v1/message/get_message_by_init`（protobuf body） |
| 消息历史 v3 | `POST /pigeon_im/v3/message/get_user_message` |
| 按会话取 | `POST /pigeon_im/v1/message/get_by_conversation` |

## 3. WebSocket（只读已验证；按所有者决定只被动监听）

### 实测记录（2026-11-26）

一次真实客户会话期间的实验：浏览器抓到建连帧后关闭，再从 Python 外连重放，60 秒内收到数十条含中文的业务帧，内容包括会话昵称、消息预览和平台下发的超时未回复提醒。

```
文本=['<买家消息>', '<买家昵称>', ...]
文本=['<平台提醒>', ...]
```

```
wss://ws.fxg.jinritemai.com/ws/v2?token=<token>&aid=1383&fpid=92
    &device_id=...&access_key=...&device_platform=web&version_code=10000
    &pigeon_source=web&PIGEON_BIZ_TYPE=2&pigeon_sign=<sign>
```

已验证：

- 帧是**明文 protobuf**，没有加密或压缩
- 帧头：字段1=seq(varint)、字段2=时间戳、字段3、字段4=cmd、字段5=headers（`pigeon_source` 等）
- 外连重放建连帧后服务端会推送数据；重复 seq 的重放可能被判为会话异常
- 外连发出的消息帧无回显，服务端只认页面那条连接发出的消息帧
- 页面内改写发送帧可以送达。**已验证可行，按所有者决定不实施**；本系统不构造、不重放、不发送任何帧
- 会话列表接口会返回 `code:11001`（「飞鸽版本过低，浏览器用户请刷新页面」），刷新页面后恢复，旧的签名 URL 不能复用

实验出口：当时的实验未记录出口。若是本机 IP，这家店的会话已在非绑定 IP 上出现过，需观察风控情况。今后的实验一律走该店出口，只在自己的测试会话里做。

### 实现方向（所有者裁定，2026-11-26）

- 不写 Python WebSocket 客户端，不重放任何帧。
- 每家开启「接收飞鸽消息」的店，用该店自己的 CloakBrowser 资料目录（经 `launch_cloak`、该店出口）常驻一个飞鸽工作台页面。
- 只被动监听页面自己的 WebSocket 收到的帧（Playwright `framereceived`），只当「有动静」的信号；会话列表与未读数从页面自己的 XHR 响应或 DOM 读。
- 消息记录（所有者决定，2026-11-26）：只收被动来源。Task 0 确认携带正文的下行帧（U9）与页面不点击就自己发出的按会话取消息 XHR（U10）可写入本系统的 `im_message` 表（保留 30 天，正文不进日志）；都不成立时只保留会话列表上的最新预览。
- 「在飞鸽中回复」：只在所有者点击时把该店常驻窗口置前并点开该会话（U12），不输入、不发送。
- 发送相关的帧结构（消息体字段）不在本文档记录。

## 4. 页面结构

- 会话列表元素：`[data-kora="conversation"]`（埋点属性，比 CSS Module 类名稳定）。
- 代价：每店一个常驻浏览器（300 到 500MB）。
- 点开会话会把消息标为已读。本系统后台不点击任何会话；唯一例外是所有者点「在飞鸽中回复」。

## 5. 未验证项（实施计划 Task 0 负责确认）

| 编号 | 问题 | 影响 |
|---|---|---|
| U1 | 页面自己发出的会话列表 XHR（带页面自己的 `msToken` / `a_bogus`）能否稳定返回数据；无签名时 `total:0` 是否因缺签名被降级 | 决定未读数来源用 XHR 还是 DOM |
| U2 | 11001 出现后，刷新页面一次能否恢复；多久出现一次 | 决定刷新上限与退避参数 |
| U3 | 哪些下行帧（cmd）表示「有新消息」，与心跳、回执、平台提醒如何区分 | 决定触发条件常量 |
| U4 | DOM 里未读徽标的选择器，以及会话元素上是否有稳定的会话 ID | 决定会话键与未读读取 |
| U5 | 只打开工作台、不点会话时，是否会自动打开某个会话或把消息标为已读 | 决定能否默认常驻 |
| U6 | 打开工作台是否会把该客服登记为「在线接待」，影响会话分流或挤掉真人客服页面 | 决定开关确认文案与是否可用 |
| U7 | `selfId` 能否从页面自身（地址跳转、XHR 响应）读出 | 决定自动读取还是手工填写 |
| U8 | 是否需要主动心跳；页面在后台（`offscreen`）时连接是否保持 | 决定健康检查方式 |
| U9 | 哪些下行帧携带消息正文：会话 ID、消息 ID、发送方、正文、时间各在哪个字段；平台提醒如何区分 | 决定 WS 帧能否写入 `im_message` |
| U10 | 不点击会话时，页面自己是否发出按会话取消息的 XHR（§2 的消息历史接口），响应能否解析出同样五项 | 决定 XHR 能否写入 `im_message`；U9、U10 都不成立时会话详情只显示最新预览 |
| U11 | 发送方能否可靠区分买家 / 客服 / 平台；客服在其他设备回复时，本页是否也收到该消息帧 | 决定「待回复」用消息计时还是按未读起点计时 |
| U12 | `offscreen` 窗口能否经同一浏览器连接移回屏幕并置前（CDP `Browser.setWindowBounds`）；点开会话是否只打开、不发送任何内容 | 决定「在飞鸽中回复」直接置前还是以可见窗口重开 |
