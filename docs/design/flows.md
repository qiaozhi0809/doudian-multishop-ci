# 核心流程

> 登录、拉单、取号（含地址解密额度）、打印、发货、对账、异常处理、风控、打印方案。
> 章节号沿用原 `architecture.md` 第 7~10 节。索引见 [docs/README.md](../README.md)。

## 7. 核心流程

### 7.1 登录流程

```
添加店铺 → 配置该店固定出口（direct / 独享静态代理）→ 出口检查通过（IP 可达且不与其他店重复，backend 5.17）
        → 经该出口打开该店的持久化浏览器用户目录（Playwright + 系统 Edge）→ 人工扫码
        → 检测到登录成功
        → 导出 cookies（用 context.cookies() 取全量；document.cookie 只含 20/37，
          缺 HttpOnly 的 sessionid / sid_tt / uid_tt / sid_guard / ttwid）
        → 获取 __token（从页面请求 URL 提取）
        → cookies + __token + device_params 加密写入 session 表
        → 探测轻量接口（GET /api/order/tabcnt；未登录返回 code=10008）
        → 同步基础数据：发货地址 / 面单账户 / 面单模板 / 快递公司
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
| `_lid` | 12 位数字；生成规则未确认，**读写接口均不校验（已实测）**，可随机生成 | 单次请求 |

- `__token` 在扫码登录成功后即可获取并保存，浏览器外协议直连时从会话文件读取
- **`_lid` 证据（API-01 追加）**：10 个样本（2026-11-24 ~ 11-25）全部 12 位、
  单调递增（`331325398959` → `380214583677`），同一时刻的两次请求相差约 5000。
  与标准时间戳位数不符（秒 10 位 / 毫秒 13 位 / 微秒 16 位）。
  - ⚠️ 「同一时刻相差约 5000」与「计数器」矛盾（计数器相邻值应差 1），
    更像某种时钟取 12 位（例如微秒级时钟截断）。**生成规则未确认。**
  - 对实现真正重要的是**服务端是否校验 `_lid`**。
  - **验证结果（2026-11-25，只读接口三组对照）**：同一会话、同一接口
    `getEbillAccountListByExpress`，三组各请求一次：

    | 组 | `_lid` | 结果 |
    |---|---|---|
    | ① | 页面真实值 `380215000001` | HTTP 200 / `code=0` / 1 个账户 |
    | ② | 随机 12 位数 `123456789012` | HTTP 200 / `code=0` / 1 个账户 |
    | ③ | 不带 `_lid` | HTTP 200 / `code=0` / 1 个账户 |

    → **只读接口不校验 `_lid`**，可省略或随机生成。
  - **写接口验证（2026-11-25，测试单 `6919927348895297368`）**：
    - 取号（随机 `_lid`）→ 接口正常处理（返回业务错误「重复取号」而非参数错误）
    - 发货（随机 `_lid`）→ `code: 0` 成功
    → **写接口同样不校验 `_lid`**。只读与写接口均可随机生成 12 位数字。

### 7.2 拉单流程

```
触发（手动/定时）
  → 遍历 active 店铺（受全局并发限制）
  → channel.list_orders(shop, tab, page) 分页拉取（0-based，pageSize ≤ 200）
  → 归一化 DTO
  → upsert orders / order_items（覆盖 platform_status，不覆盖本地 status；平台已关闭 → 本地 cancelled，见 backend 5.4）
  → 更新同步游标
```

### 7.3 取号流程

**打单发货页提供两种操作，对齐官方交互、二者并存**：

| 操作按钮 | 接口 | 订单终态 | 适用场景 |
|---|---|---|---|
| **打面单** | `batchFetchTrackingNos` | `label_obtained`（已取号，待发货） | 半自动：人工核对面单后再发货 |
| **打单并发货** | `batchFetchTrackingNosAndDeliverGoods` | `shipped`（已发货） | 全自动：单量大、面单模板稳定 |

两种操作共用同一个打单发货页界面与预检流程，只是最后一步调用的接口不同。
默认推荐「打面单」（保留中间态可核对），「打单并发货」作为快捷选项。

下面是「打面单」的完整流程（「打单并发货」前面相同，最后一步改调一体接口，见 [api/write.md](../api/write.md) A.2.5）：

```
人工勾选订单 → 预览（两步提交第①步，backend 5.11）
  → 预检：会话 / 发货地址 / 模板 / 订单 platform_status 为待发货
     GET /api/order/getAftersaleAddressAndLogisticsTemplate
     一次返回 has_aftersale_address / has_template / has_logistics_service / has_printer
  → 补齐取号参数（按店）：
     ① 订单取号字段：combine_id / sku_order_id / 实际 sku_id / product_id / product_cnt
        （searchlist 的 sku_id 可能为 0；⏳ 来源接口待定 gaps API-04）
     ② 面单账户：ebill_id / net_code，按 5.9 选择规则（⏳ DEC-05），余额为 0 即拦截
     ③ 产品类型：POST /api/order/query_added_services_and_product_types → expType（默认 selectedValue）
     ④ 发货前检查：POST /api/order/sendcheck（页面会先调；⏳ 取号前是否必经未验证，gaps API-21）
  → 用户按住确认（第②③步）
  → 按店分组，逐店串行
  → POST /api/order/batchFetchTrackingNos
      { logistics_company_code, logistics_template_code, address,
        transport: "{\"expType\":...}", net_code, ebill_id,
        shop_order_list, fetch_type: 1, is_davinci: true, order_type: 0, version: 1, printer }
  → 成功：写 waybills(active, seq)，订单 → label_obtained
  → 业务拒绝（超区 / 模板 / 余额 / 地址）：订单 → exception + 原因
  → 「不存在可取号商品」或超时：任务 → verifying，查回运单号（backend 5.5 / 5.12），不转 exception
  → 会话失效：暂停该店并提示重登
```

**取号前置条件（缺一不可）**：

1. 会话有效；
2. 该店已配置默认发货地址（`shop_address.is_default`，平台侧标位为 `is_send_default=1`）；
3. 已选择快递公司，且存在对应面单模板（`waybill_template`）。

> **取号不解密（DEC-06，2026-11-25 所有者决定）**：取号与官方组件打印都**不**调用 `receiveinfo`。依据：
> ① 取号请求体（A.2.2）没有任何收件人字段，只有订单 ID 与**发货**地址；
> ② 官方订单页「打单发货」链路（A.2.7 四步）全程没有调用 `receiveinfo`；
> ③ 官方组件打印用的 `print_data` 是平台加密数据，收件人由组件渲染。
> 解密按次消耗当日额度并会触发风控（见下方「地址解密额度」），因此**只在两种场景按需解密**：
> 用户在界面上手动查看某单收件人；打印走自渲染 PDF（第 10 节方案 B）。

第 2~3 项可由 `GET /api/order/getAftersaleAddressAndLogisticsTemplate` 一次性预检
（`has_aftersale_address` / `has_template` / `has_logistics_service`）；
`has_printer` 反映打印组件侧配置，不影响取号本身。

**地址解密额度（2026-11-25 实测 + 官方页面确认）**：

抖店的收货信息解密是**配额制**，不是无限调用。官方页面在
「店铺设置 → 订单信息解密额度」：

| 项 | 含义 |
|---|---|
| 剩余解密次数 | 当日还能解密多少单（样本店实测剩 8 次） |
| 已解密总次数 | 当日已用额度（含抖店后台、服务商应用分别统计） |
| 剩余提额次数 | 「申请提额」的可用次数 |
| 解密环境风险数 | 当日风险检测结果 |

**额度消耗规则**：

- 每次 `receiveinfo` 成功返回明文计 1 次；**重复解密同一订单每次都计**
- 多次解密「已取消 / 已发货 / 已完成」订单会触发官方警告：
  「请停止非必要的解密（包含但不限于多次解密已取消、已发货、已完成等状态订单）」
- **频率风控**（实测）：连续约 13 次、间隔 0.5~0.8s 返回 `602502151`「您的账户存在安全风险，请稍后再试」。
- **状态禁止**（实测）：同一码在订单状态不允许解密时返回「基于消费者隐私保护，该订单状态禁止查看」（如刚付款的待发货订单）。
  这是**调用过快**触发的，与「当日额度用完」是两种限制
- 「3 小时自动恢复」：⏳ **出处待注明（gaps API-10）**——两次提交只隔 2 分钟，不可能是等待实测，
  应注明来自官方页面还是推断
- ⏳ **额度用完时的返回**（错误码 / 提示）未知（gaps API-10）

**实现约束（必须遵守）**：

1. **解密前判状态**：只对「待发货 / 待打单」订单解密；已发货 / 已完成 / 已取消不解密
2. **明文不入库，只在内存缓存**：解密结果按订单号缓存在后端进程内存中，到平台返回的 `expire_time` 为止；
   缓存期内再次查看不再调 `receiveinfo`（不重复扣额度）。进程重启或到期后，再查看会重新解密。
3. **限速**：单店连续解密间隔 ≥ 2 秒（⏳ 2 秒为估计值，未验证安全；只知 0.5~0.8s 会触发）
4. **额度感知**：捕获 `602502151` 后标记店铺「解密冷却中」，只暂停该店的**解密**请求，**不暂停取号**（取号不依赖解密，DEC-06），
   提示用户「约 3 小时后恢复」或引导到官方页面申请提额
5. **只按需解密**：拉单、取号、官方组件打印都不解密；只在用户查看收件人或自渲染 PDF 时逐单解密（DEC-06）

### 7.4 打印流程

```
按「店 + 快递」分组生成打印批次
  → 按第 10 节当前启用的打印路径执行
     （MVP：先用 P3 手动补打保底；P1 借页面打印验证通过后切为默认）
  → 组件回执成功：waybills.printed，订单 → printed
  → 失败：print_job.status=failed，订单停在 label_obtained，界面提示重试或手动补打
  → 重打不重复取号
```

- **不自动降级到自渲染 PDF（方案 B）**：方案 B 需要先解密收件地址（消耗额度、有风控，7.3），
  且自渲染面单是否符合平台隐私面单要求未确认（⏳ gaps API-22）。只允许用户对单张面单手动触发。
- 打印组件未就绪或回执失败时，**不得**把订单标为已打印（验收标准第 10 条）。

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

**一体路径**：「打单并发货」（打单发货页）与订单页「打单发货」都走
`batchFetchTrackingNosAndDeliverGoods`，一步完成取号与发货（见 A.2.5 / A.2.7）。

**`/order/torder/batchsend`**：电子面单的两条发货路径上都未出现，**本工具不使用**。
订单页「自行寄件发货」（手填运单号）是否走它未核查；本工具只做电子面单，不影响 MVP（gaps API-14）。

### 7.6 对账流程

```
每日定时 → 拉取平台最近 N 天已发货订单（N 待 DEC-02：当前 7，[附录 G.5](../api/reconcile.md) 建议 30）
  → 与本地比对
  → 产出 reconcile_findings
  → 界面展示，支持标记已处理 / 导出
```

---

## 8. 异常处理

| 类型 | 例子 | 策略 |
|---|---|---|
| 瞬时故障 | 网络超时、502、限流 | 按操作区分（backend 5.12）：只读与发货退避重试最多 3 次；**取号 / 一体不重试，先查回** |
| 会话失效 | 返回未登录/验证码页 | 暂停该店队列，提示重登，重登后断点继续 |
| 业务拒绝 | 超区、地址异常、余额不足、模板未配 | 不重试，转 `exception`，人工处理 |
| 数据问题 | 订单已取消/已发货 | 同步最新状态，关闭本地任务 |
| 程序错误 | 解析失败、字段缺失 | 保留 `raw_json`，告警，不重试 |

原则：**单笔失败不阻塞批次；单店失败不影响其他店。**

**已记录的错误码**：

| 错误码 | 含义 | 归入类型 | 备注 |
|---|---|---|---|
| `10008` | 未登录 | 会话失效 | — |
| `10001010A` | 当前环境存在风险，请稍后重试 | 风控拦截 | 无签名的 `searchPackageList` 直连触发（2026-11-25） |
| `602502151` | ① 您的账户存在安全风险，请稍后再试<br>② 基于消费者隐私保护，该订单状态禁止查看 | 风控拦截 / 状态禁止 | ① 地址解密连续 13 次触发<br>② 订单当前状态不允许解密（如刚付款 / 已完结）（2026-11-25） |
| `310011` | 合并ID为空 | 请求错误 | 取号 `combine_id` 必填 |
| `602500705` | 系统异常，请联系客服咨询 | 请求错误 | `searchlist` 参数不全时返回（需 `tab` + `order_status` 同时传，且为 GET） |
| `602502051` | （分页超限） | 请求错误 | `searchlist` 的 `pageSize` ≥ 201 |
| —（`fail_msg`） | 不存在可取号商品，请刷新后重试 | 待核实 | 取号重复或已发货；按 backend 5.12 查回，不当作业务拒绝 |
| `100000` | 成功（字符串） | — | 与其他接口的 `0` 并存 |

---

## 9. 风控与合规策略

> 本工具仅用于管理商家**自有店铺**，登录态来自商家本人扫码授权。

| 措施 | 说明 |
|---|---|
| TLS 指纹模拟 | `curl_cffi` `impersonate="chrome"` |
| 每店独立环境 | 每店独立浏览器 profile + 固定独立出口 IP（backend 5.17）；不使用轮换代理池 |
| 设备参数一致 | 不伪造指纹；协议通道的 UA 等与该店扫码浏览器一致 |
| 出口异常即停 | 出口不通 / IP 变化 / IP 重复时暂停该店，绝不退回直连 |
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

**documents 真实结构（2026-11-25 从页面源码解开，gaps API-07 已解决）**：

```js
documents: data.map(e => ({
  documentID: e.trackNo || "",
  standard: {
    signature: e.sign || "",          // 签名
    encryptedData: e.printData || "", // 加密数据原样放，组件自己解密
    templateURL: e.templateUrl || "", // 面单模板 XML URL
    params: e.OAuth || "",            // OAuth 参数
  },
  custom: e.customTemplateUrl
    ? { data: e.customPrintData, templateURL: e.customTemplateUrl }
    : undefined,
}))
```

**关键结论**：`print_data` 不是 PDF、也不需要本地解密 —— 组件直接接收
「签名 + 加密数据 + 模板 URL」，自己解密并渲染。之前在 A.2.4 里推测的
「需要逆向 `mW()` 做数据转换」不成立，实际只是**字段映射**。

**打印数据来源（两条路）**：

| 场景 | 来源 |
|---|---|
| 首次打印（取号后） | 取号响应 `success_list[]` 的 `print_data` / `sign` / `template_url` / `custom_print_data` / `custom_template_url` |
| 补打面单 | `POST /shopuser/olSend/batchGetPrintInfos`，body `{"trackInfos":["<运单号>"],"templateCode":"","appid":1}` |

注意：取号响应无 `OAuth` 字段（`params` 可能为空），补打接口返回 `OAuth`。

**验证结果（2026-11-25）**：

- 组件接受消息并回 `{"cmd":"print","requestID":"...","status":"success"}`
- 随后推 `notifyPrintResult`，`printStatus[].detail` 是 base64 编码的渲染结果（失败时含错误原因）
- `env` 取值 `"prod"`（生产）/ `"boe"`（测试环境）

**print 消息完整结构**：

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
    documents: [ /* 上述 standard/custom 结构 */ ]
  }
}
```

**打印路径（已更新）**：

| 路径 | 做法 | 状态 |
|---|---|---|
| **P1 直连组件**（默认） | 后端组装 documents → `wss://localhost:13999` | ✅ 结构已解开，可行 |
| P2 借页面打印 | Playwright 调页面打印逻辑 | 备用（改版时保底） |
| P3 手动补打 | 抖店后台「补打面单」 | 保底 |

**MVP 策略**：P1 为主。启动时用 `getPrinters` 探测组件并缓存打印机列表；
`print` 后等待 `notifyPrintResult`，超时视为失败；失败重试一次后转 P3 提示人工补打。

**组件未启动的强制约束（2026-11-25 确认）**：

抖店官方打印组件（CloudPrintClient）**必须在本机运行**，否则：

- 抖店页面里的「打印快递单」「打印并发货」按钮**置灰不可点**
- 我们自己的打单按钮同样必须置灰，并在悬浮提示里给出原因与引导

实现约定：

- **探测**：对 `wss://localhost:13999` 发起 `getPrinters`，超时（建议 2 秒）或连接失败即视为未启动
- **探测时机**：进入打单发货页时、组件状态缓存过期（建议 30 秒）、点击打单前各一次
- **界面**：组件不可用时，打单按钮 disabled + 提示「请先启动抖店官方打印组件」，
  附「下载 / 启动」引导（组件名「抖店官方打印组件」，安装后常驻托盘）
- **降级**：组件长期不可用时，用户可选 P3 手动补打，流程不被阻塞

**恢复面单无法本地打印（2026-11-25 M2 交接）**：

取号超时后走 `getOrderLogistics` 查回恢复的面单，**只有运单号，平台不返回 `print_data` / `sign`**。
官方打印组件无法渲染这类面单。

M3 打印实现必须区分两类面单：

| 来源 | 有 `print_data` / `sign` | 打印方式 |
|---|---|---|
| 正常取号 | ✅ | P1 直连组件 |
| `getOrderLogistics` 恢复 | ❌ | P2 借页面打印 / P3 平台手动补打 |

`waybills.print_data` 为空是**正常情况**，不要假设每张面单都能本地打印。
打单发货页 UI 需对「无打印数据的面单」给出明确标识与引导。

**多店打印调度**：打印机是本机资源，所有店铺共享同一列表。
建议做「店铺 × 默认打印机」配置，避免多店同时打单时抢占同一台打印机。

**M3 实现（2026-11-25，P1 直连组件）**：

- `adapter/print/`：`wss://localhost:13999`（跳过自签校验，`Origin: https://fxg.jinritemai.com`）；
  `getPrinters` 2 秒探测；`print` 后等 `notifyPrintResult`（20 秒超时），回执无法判断成败时**不当作成功**。
- `service/printing.py`：每次提交每张面单一条 `print_job`；组件失败重试一次，仍失败 → `failed`
  并提示「到抖店后台手动补打」；成功才把 `waybills.status=printed`、订单 `label_obtained → printed`。
- **模板 URL 的来源**：`waybills` 只存 `logistics_template_code`（6.2 ⑤），取号响应的 `template_url`
  未入库。因此打印前按运单号调 `batchGetPrintInfos` 取 `templateURL` / `OAuth`（A.2.10）；
  接口失败时用本地 `print_data` / `sign` 兜底，`templateURL` 为空，交给组件回执定成败。
- **恢复面单**（`print_data` 为空）：打印时先经 `batchGetPrintInfos` 补取，取到即回写
  `waybills.print_data` / `sign`；仍无数据 → `print_job.result_code=no_print_data`，
  界面标「需手动补打」，**不自动降级到自渲染 PDF**（方案 B 仍需按需解密，7.4）。
- 组件未启动：`GET /api/print/status` 返回 `available=false`，打单发货页打印按钮置灰 + 启动引导。
- 多店并发：同一时刻只允许一个打印批次（后台任务同名），批次内逐张串行，避免抢占打印机。

### B. 自渲染面单 + 系统打印（仅手动触发）

- 将面单数据渲染为 100×150mm PDF，交 Windows 打印子系统。
- 需要明文收件地址 → 按需解密（7.3），受额度限制；不作为自动兜底。
- ⏳ 是否符合平台隐私面单 / 电子面单规范未确认（gaps API-22）。
- 优点：不依赖官方组件。
- 缺点：模板需自行适配，可能与快递要求有偏差。

### C. 仅取号，手动打印（保底，即上表 P3）

- 软件只负责取号与发货回传，打印由用户在抖店后台手动完成。
- 作为兜底，不影响全流程闭环。

**部署位置**：软件最终运行在**出单机**（登录、打印均为本机动作）。开发在开发机完成，交付时整体拷贝。

**开发机环境**：已安装官方打印组件（CloudPrintClient.exe），
13888/13999 端口正常监听，`getPrinters` 验证通过（当前仅 1 台虚拟打印机
`Microsoft Print to PDF`）。真实出单机需验证实际热敏打印机的打印效果。
