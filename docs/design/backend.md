# 后端设计

> 分层、抖店适配层、会话、订单同步、取号、发货、调度、对账、基础数据、聚合、写操作安全、重试、存储与日志。
> 章节号沿用原 `architecture.md` 第 5 节；原 `overall-design.md` 第 2 节并入 5.0 / 5.1 / 5.2 / 5.7 / 5.11~5.15。
> 索引见 [docs/README.md](../README.md)。

## 5. 后端设计

### 5.0 分层与模块

按 engineering-rules 2.2：`api → service → adapter / store / domain`，禁止反向依赖。

| 层 | 模块 | 职责 |
|---|---|---|
| `api/` | `auth` `shop` `order` `label` `print` `shipping` `remark` `task` `event` `aftersale` `catalog` `fund` `reconcile` `audit` `setting` | 路由 + pydantic I/O schema，只调 service |
| `service/` | `session_manager` `base_data` `order_sync` `labeling` `printing` `shipping` `reconcile` `aftersale` `catalog` `fund` `scheduler` | 业务编排、事务、状态机推进 |
| `adapter/doudian/` | `client` `endpoints` `bid` `error_codes` `enums` `signing/` | 抖店 HTTP 协议的唯一出口 |
| `adapter/browser/` | `login` `channel` `page_print` | Playwright：扫码登录、兜底 fetch、借页面打印 |
| `adapter/print/` | `component` `ports` | 官方打印组件 WebSocket |
| `store/` | 按表分文件 | SQLite CRUD，无业务判断 |
| `domain/` | `order_status` `aftersale_status` `money` `idempotency` `reconcile_rules` | 纯模型与纯函数，无 IO |
| `shared/` | `time_bj` `redact` | 跨模块工具，配单测 |

### 5.1 店铺会话管理（`service/session_manager.py`）

**职责**：维护每个店的登录态，是所有模块获取会话的唯一入口。

**两个通道各自的登录态**：

| 通道 | 存放位置 | 内容 |
|---|---|---|
| 浏览器通道（扫码 / 需签名接口 / 借页面打印） | 每店持久化用户目录 `data/profiles/<shop_id>/`（`launch_persistent_context` + 系统 Edge） | 浏览器自身的完整登录态与指纹；登录态和指纹天然隔离，重登只需重开该目录 |
| 协议通道（curl_cffi 直连） | `session` 表（[data-model.md](data-model.md) 6.2 ②），DPAPI 加密 | `context.cookies()` 导出的**全量** cookie（含 HttpOnly）、`__token`、设备参数 |

两个通道都经该店的固定出口发出（5.17）。

**行为**：

- 首次添加店铺：先配置并检查该店出口（5.17），再打开该店的浏览器用户目录（经同一出口），人工扫码；登录成功后导出 cookie 与 `__token` 写入 `session` 表。
- 探测：每 30 分钟 `GET /api/order/tabcnt`（未登录返回 `code:10008`）；协议响应若下发新 cookie 则回写（⏳ 是否会下发未验证，gaps API-02）。
- 会话失效 → 标记 `needs_login`，暂停该店队列并通知界面；重登后从断点继续。

**会话有效期（API-02）**：

- `sid_guard` 解码后的有效期：**60 天**（`5184000` 秒）；两个样本店均为扫码后 60 天到期
- 界面在到期前 7 天提示重新扫码
- 是否通过 `Set-Cookie` 续期未验证；实现按「不续期」保守处理（从扫码起算 60 天）

**接口**：

```python
get_session(shop_id) -> Session          # 取可用会话，失效时抛 SessionExpired
refresh(shop_id) -> Session              # 强制重新登录（弹浏览器）
probe(shop_id) -> Health                 # healthy | expiring | expired
```

### 5.2 抖店适配层（`adapter/doudian/` + `adapter/browser/`）

**职责**：把「对抖店做的动作」抽象成一组原语，屏蔽协议差异；是唯一与抖店交互的地方。

**接口注册表**：每个抖店接口在 `endpoints.py` 里声明一次，业务代码只引用名字。

| 声明项 | 例 |
|---|---|
| `method` / `path` | `POST` / `/api/order/batchFetchTrackingNos` |
| `bid` | `ffa_order` / `ffa_goods` / `ffa_aftersale` |
| `body` | `json` / `form`（批量备注是 form） |
| `page_base` | `0` / `1` / `None` |
| `success_code` | `0` / `"100000"` |
| `write` | 是否写接口（决定是否受演练模式拦截、是否必须带幂等键） |
| `channel` | `protocol` / `browser`：**逐接口声明**，已验证免签名的走 `protocol`，其余默认 `browser`（5.3） |
| `retry` | 重试策略（5.12） |

**客户端职责**：注入公共参数（`appid` / `__token` / `_bid` / `aid` / `_lid`，来源见 [flows.md](flows.md) 7.1）→ 发请求 →
归一化成功码 → 把失败归入下表五类异常，业务层只按类型处理。

| 异常类型 | 判定 | 上层处理 |
|---|---|---|
| `SessionExpired` | `code=10008` 等 | 暂停该店队列、标记 `needs_login`，重登后从断点继续 |
| `BizRejected` | 超区 / 余额不足 / 地址异常等 | 不重试，订单转 `exception` 并记录原因（取号「不存在可取号商品」除外，见 5.5） |
| `RiskBlocked` | `10001010A`、`602502151` 等（[flows.md](flows.md) 第 8 节） | 暂停该店对应类别的自动化，提示人工检查 |
| `Transient` | 超时 / 5xx / 限流 | 按 5.12 的逐操作策略处理 |
| `ParseError` | 字段缺失 / 结构变化 | 保留原始报文、告警、不重试 |

**可替换的发送层**：客户端依赖一个 `Transport` 接口，生产用 curl_cffi，测试用回放实现读取录制样本
（respx 等 mock 工具只支持 httpx，拦不住 curl_cffi）。

**原语（`ShopChannel`）**：

```python
class ShopChannel(Protocol):
    # 会话
    def probe_session(shop) -> SessionHealth                          # tabcnt

    # 基础数据（登录后同步并缓存，5.9）
    def list_addresses(shop) -> list[AddressDTO]                      # 发货地址（含行政区 ID）
    def list_ebill_accounts(shop, courier_code) -> list[EbillAccountDTO]  # 面单账户（ebill_id / net_code / balance）
    def list_waybill_templates(shop) -> list[TemplateDTO]
    def list_couriers(shop) -> list[CourierDTO]

    # 订单
    def list_orders(shop, tab, page, page_size=200) -> Page[OrderDTO] # searchlist（0-based，上限 200）
    def get_label_order_info(shop, orders) -> list[LabelOrderDTO]     # combine_id / sku_order_id / 实际 sku_id（⏳ 来源待定，gaps API-04）
    def decrypt_receiver(shop, order) -> ReceiverDTO                  # 按需解密，不在取号链路（DEC-06）

    # 取号
    def query_product_types(shop, courier_code, orders) -> ProductTypesDTO   # expType / added_services
    def obtain_waybills(shop, orders, account: EbillAccountDTO, template_code,
                        address: AddressDTO, exp_type) -> FetchResult        # batchFetchTrackingNos
    def find_tracking_no(shop, order) -> str | None                   # 取号超时恢复（getOrderLogistics，⏳ gaps API-19）
    def void_waybills(shop, waybills) -> VoidResult                   # batchCancelTrackingNos

    # 发货
    def precheck_ship(shop, orders, address) -> PrecheckResult        # sendcheck
    def ship_packages(shop, packages) -> ShipResult                   # batchDeliverGoodsByEES：[(courier_code, tracking_no)]
    def fetch_and_ship(shop, orders, account, template_code, address, exp_type) -> ShipResult
                                                                      # batchFetchTrackingNosAndDeliverGoods（一体）
    # 阶段二
    def get_resend_packages(shop, order) -> list[PackageDTO]          # get_manual_send_order_info（deliver_id）
    def modify_logistics(shop, order, package, courier_code, tracking_no) -> ModifyResult  # modifyLogistic
    def add_remark(shop, order, text) -> None                         # addremarks
```

**两个实现**：

| 实现 | 技术 | 用途 |
|---|---|---|
| `adapter/doudian/client.py` | curl_cffi（签名按需启用） | 默认通道，快、省资源 |
| `adapter/browser/channel.py` | Playwright 页面内 `fetch` | 需签名的接口；协议通道被风控拒绝时兜底 |

**通道降级规则**：

- 按接口声明选通道；可按店整体切到 `browser`。
- **只读接口**：协议通道失败（风控拒绝 / 签名错误）后可自动改走浏览器通道重试一次。
- **写接口**：只有在**确定请求未生效**时（发送前失败、或平台明确返回签名 / 风控拒绝）才可降级重发；
  **超时、连接中断等结果不明的失败一律不降级、不重发**，按 5.12 先核实平台状态。
  否则取号会在平台已成功的情况下被重发（只得到「不存在可取号商品」），发货会多一次无意义的请求。
- 契约测试用同一组用例跑两个实现。

### 5.3 签名引擎（`adapter/doudian/signing/`，按需启用）

**M0 / 第一轮验证结论**：只读接口在只带 Cookie + `__token` 时可正常返回（Python + curl_cffi 已在浏览器外验证）。已验证免签名的只读接口：订单列表、状态计数、快递公司（POST）、面单模板、发货地址、收货地址解密、店铺画像。`a_bogus` / `msToken` / `verifyFp` 属于风控打分参数，不是这类接口的鉴权必需项。

**例外（2026-11-25 实测）**：只读接口 `GET /api/order/searchPackageList` 无签名直连返回风控错误
`10001010A`「当前环境存在风险，请稍后重试」。**并非所有只读接口都免签名**，
免签名须逐接口验证后在 `endpoints.py` 声明；未验证的接口默认走浏览器通道。

已验证免签名的写接口：批量备注、取号、发货前检查、发货、取号发货一体、面单作废、改物流（附录 A.2）。

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

**职责**：按店拉取订单并归一化入库。

- 触发：手动点击 + 定时（默认 5 分钟，可配置）。
- 分页拉全（`searchlist` 0-based，`pageSize` 上限 200）；增量时间窗参数待验证（gaps API-12）。
- 归一化：平台字段 → 内部 `OrderDTO` → `orders` / `order_items`。
- 幂等：按 `(shop_id, order_no)` upsert。
- **两套状态分开存**：平台状态（数字 `order_status`）写 `orders.platform_status`，每次同步覆盖；
  本地履约状态 `orders.status`（6.1 状态机）只由本系统推进，不被平台数据覆盖。
- **平台状态驱动的本地转换**：平台变为「已关闭」（`4`）且本地尚未发货 → 本地转 `cancelled`；
  若该单有 `active` 面单，提示人工作废（不自动作废）。平台已发货而本地未发货 → 交给对账（5.8）。
- 取号前置：`pending_label` 的订单必须 `platform_status` 为待发货，否则拦截。
- **供应商代发单不能取号**：「源头好货」等订单出现在待发货里，但商家不能发货（判别字段待定，gaps API-28），同步时标记为不可取号，打单台不显示勾选框。
- 取号所需字段（`combine_id`、`sku_order_id`、实际 `sku_id`）`searchlist` 不能直接提供
  （`sku_id` 可能为 0），来源接口待定（gaps API-04）。
- 单店失败不影响其他店。
- **仪表盘另有一套事实同步**：`tab=all` 拉所有状态写 `order_fact`，与履约用的 `orders` 分开（[dashboard.md](dashboard.md) 2.1）。

### 5.5 打单编排器（`service/labeling.py`）

**职责**：把"勾选的订单"变成"已打印的面单"。

流程：

1. 预检：会话有效 / 发货地址已配置 / 面单模板存在 / 面单账户可用且有余额 / 订单平台状态为待发货。
   **不需要解密收货地址**（DEC-06）。
2. 补齐取号参数：订单取号字段、面单账户、产品类型（完整链路见 [flows.md](flows.md) 7.3）。
3. 按店分组，逐店串行执行取号（`POST /api/order/batchFetchTrackingNos`）。
4. 写入 `waybills`（`status=active`），订单转 `label_obtained`。
5. 按「店 + 快递」分组生成打印批次。
6. 推送打印（[flows.md](flows.md) 第 10 节），成功后 `waybills.status=printed`，订单转 `printed`。

失败处理：

- 单笔业务拒绝（超区/地址异常/余额不足）→ 订单转 `exception`，记原因，不阻塞批次。
- 会话失效 → 暂停该店，提示重登，重登后从断点继续。
- 超时 / 结果不明 → **不重试**，走下方恢复流程（5.12）。

**取号超时的恢复（⏳ gaps API-19）**：

平台对已取号的订单再次取号会拒绝（`fail_msg`「不存在可取号商品」，A.2.2 第 8 条）。
因此若取号实际成功、但响应丢失（超时 / 断网），重试只会得到这条拒绝，本地拿不到运单号。

- 处理原则：取号请求超时或收到「不存在可取号商品」时，**不得**把订单转 `exception`，
  而是保持 `pending_label`、把该取号任务标为待核实，去平台查询该订单当前的运单号，
  查到则补写 `waybills(active)` 并转 `label_obtained`
- **查回运单号的接口（2026-11-25 实测）**：`GET /api/order/getOrderLogistics?order_id=<shop_order_id>`
  → `data.logistics[].logistics_code` 即运单号（详见 A.1）。
  ⏳ **关键情形未验证（gaps API-19）**：返回字段含发货时间 / 发货方式，疑似只列**已发货**物流；
  恢复要查的是「**已取号、未发货**」订单，须用这种订单实测能否查到运单号，否则恢复方案不成立。
  **`orderDetail` 不含运单号**，不要用它做恢复。
- 一体接口 `batchFetchTrackingNosAndDeliverGoods` 有同样问题；它已完成发货，可从订单列表的
  `latest_logistic_info.tracking_no` 查回（待实测），或同样用 `getOrderLogistics`

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
  平台不拦重复发货（[api/write.md](../api/write.md) A.2.4），超时后重试是安全的；本地按幂等键防重。
- 记录平台返回的完整报文摘要（`success_package_list` / `fail_package_list`）。

### 5.7 调度队列（`service/scheduler.py`）

- **每店一条 `asyncio.Queue` + 一个 worker**：同店请求绝不并发。
- **全局 `asyncio.Semaphore(3)`**：同时最多 3 个店在跑（可配置）。
- 同店请求间隔 300~1200ms 随机；地址解密另有更严的单独限速（[flows.md](flows.md) 7.3）。
- 可配置「工作时段」，时段外不跑定时任务。
- 任务落 `tasks` 表（[data-model.md](data-model.md) 6.2 ⑥），进程重启时把 `running` 改回 `queued`；
  其中结果不明的写任务（取号 / 一体）改为「待核实」，按 5.12 处理，不直接重跑。
- 定时任务（拉单 5 分钟、售后 5 分钟、商品库存 15 分钟、资金 30 分钟、每日对账）用进程内 asyncio 循环实现。
- **M7 落地**：每日全店对账（默认本地 03:00，`DD_RECONCILE_DAILY` / `DD_RECONCILE_HOUR` / `DD_RECONCILE_WINDOW_DAYS`）、
  每日数据库快照（默认 04:00，`DD_BACKUP_DAILY` / `DD_BACKUP_KEEP`）、临近超时发货扫描（每 30 分钟，
  `DD_SHIP_DEADLINE_WARN_HOURS`）都挂在同一个 `run_daily_at` / `run_every` 循环上；
  启动时把 `running` 写任务转「待核实」、其余转 `queued`（`task_store.recover_after_restart`），
  会话失效时把该店 `running` 写任务转「待核实」（`mark_expired`），重登后按幂等键重试。
  部署说明见 [deployment.md](deployment.md)。
- 仪表盘：热窗口（今天 + 昨天）每 10~15 分钟、近 30 天每晚重拉并重算日汇总、`tabcnt` 定时快照（[dashboard.md](dashboard.md) 2.2）。

### 5.8 审计与对账（`service/reconcile.py`）

- 每次外部调用记录 `audit_log`：动作、请求摘要、响应摘要、结果、耗时。
- 每日定时对账：
  1. 拉取平台「已发货」订单（时间窗待 DEC-02：当前写 7 天，[附录 G.5](../api/reconcile.md) 数据建议 30 天）。
  2. 与本地 `orders` 比对。
  3. 输出三类异常：
     - 本地已发货、平台未发货 → 可能回传失败，需补发。
     - 平台已发货、本地无记录 → 可能人工在其他地方操作。
     - 运单号不一致 → 需人工核对。
- 对账结果按 `run_id` 落库（`reconcile_findings`），界面展示，支持导出。
- 判定细节见 [api/reconcile.md](../api/reconcile.md)。

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
  `balance = -1` 表示月结账户（如京东），不计张数，视为可用（实测样本）。
  余额不足时取号会失败，界面需提示。
- **多账户选择规则（建议，待确认）**：同一快递返回多个账户时，
  ① 用户在店铺设置里为该快递指定的账户；② 否则取 `isDefault=true`；
  ③ 否则取 `balance` 最大的账户。所选账户 `balance=0` 时取号前即拦截并提示，不发请求（月结账户 `balance=-1` 不拦截；与有张数账户并存时的优先级待 M2 确认）。
- 刷新时机：首次登录后、店铺配置变更提示、每日首次同步前。
- 失效策略：取号失败且错误指向模板/地址时，强制刷新一次再重试。
- **取号必须使用本店已配置的 `address_id` 与 `template_code`**，不能跨店复用。

### 5.10 多店聚合模块（只读）

**职责**：把售后、商品、库存、资金四类数据按店聚合，产出跨店视图与预警。全部只读。

| 子模块 | 服务模块 | 接口依据 |
|---|---|---|
| 售后聚合 | `service/aftersale.py` | [附录 E](../api/aftersale.md) |
| 商品 / 库存 | `service/catalog.py` | [附录 D](../api/catalog.md) |
| 资金看板 | `service/fund.py` | [附录 F](../api/fund.md) |
| 跨店对账 | `service/reconcile.py` | 第 5.8 节 + [附录 G](../api/reconcile.md) |

**共同约束**：

1. 只调只读接口，不触发任何写操作
2. 每店一请求；单店失败隔离（会话失效标记 `needs_login`，不影响其他店）
3. **分页基准按接口区分**：订单 `searchlist` 0-based、资金 `query_item` 0-based、
   售后 `after_sale/pc/list` 1-based、库存 `stock/manage/list` 1-based
4. 金额统一整数分（`*_cents`），展示层再换算
5. 上游不可用时回退本地缓存，并标注数据来源（`source: upstream | local_db`）
6. **实时计数按店缓存 60 秒**（订单 tab 计数在 `order_query.py`，售后计数、商品计数用 `service/shop_cache.py`）：
   页面加载、切页、多标签页、多台电脑共用，60 秒内每店最多请求平台一次；只缓存成功结果；
   该店同步完成后失效；`fetched_at` 是当初取自平台的时间。缓存在进程内存里（单进程部署，不用 Redis）

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

### 5.11 写操作：两步提交

所有写接口（取号、取号发货一体、发货、作废、批量备注，以及阶段二的改物流 / 售后 / 商品 / 库存写操作）走同一套流程：

```
① POST /api/<写操作>/preview
     后端做预检，生成将要发出的每个请求（按店分组）、预计影响的订单数，
     返回 preview_id（短期有效）。不发出任何写请求。
② 前端展示预览 → 用户按住确认（hold-to-confirm）
③ POST /api/<写操作>/execute { preview_id }
     后端按预览内容入队执行；每个请求带幂等键，已成功执行过的直接返回上次结果。
④ 通过 SSE 推送逐单进度；结束后写审计日志。
```

- **演练模式** = 只允许第①步，第③步直接拒绝（engineering-rules 8.3）。
- 预览与执行之间若订单状态变了（例如被平台关闭），执行时重新校验并跳过该单。
- **幂等键**（`domain/idempotency.py`）：

| 操作 | 幂等键 | 说明 |
|---|---|---|
| 取号 / 取号发货一体 | `label:{shop_id}:{shop_order_id}:{seq}` | `seq` = 该订单已作废面单数 + 1。**不带 `seq` 会让作废后的重新取号撞上旧键、直接拿到旧结果** |
| 发货 | `ship:{shop_id}:{courier_code}:{tracking_no}` | 运单维度 |
| 作废 | `void:{shop_id}:{courier_code}:{tracking_no}` | |
| 批量备注 | 不设幂等键 | 覆盖写（`overwrite=true`），重复执行无副作用 |

- 同一幂等键的任务失败后重试，复用原任务行（`attempts + 1`），不新建任务。

### 5.12 重试策略（逐操作）

「瞬时故障一律退避重试」对写操作不成立。按操作分别规定：

| 操作 | 超时 / 结果不明时 | 依据 |
|---|---|---|
| 只读接口 | 指数退避，最多 3 次 | 无副作用 |
| 取号 | **不重试**。任务转「待核实」→ `find_tracking_no` 查回运单号 → 查到则补写面单，查不到再允许重试 | 平台拒绝重复取号（[api/write.md](../api/write.md) A.2.2 第 8 条）；查回接口 ⏳ gaps API-19 |
| 取号发货一体 | **不重试**。核实方式同上；它已发货，也可从订单列表 `latest_logistic_info` 查回 | 同上 |
| 发货 | 退避重试，最多 3 次 | 平台不拦重复发货（A.2.4 第 5 条） |
| 作废 | 先查面单状态再决定；⏳ 重复作废的平台行为未验证 | — |
| 地址解密 | 不自动重试 | 按次扣额度并有风控（[flows.md](flows.md) 7.3） |
| 业务拒绝 / 风控拒绝 | 不重试 | 5.2 异常分类 |

### 5.13 存储

- SQLite WAL 模式，单库；表结构见 [data-model.md](data-model.md)。
- 访问层用 **SQLAlchemy 2 Core**（只用 SQL 表达式，不用 ORM），迁移用 **Alembic**。
- 金额一律整数分、时间一律 ISO-8601 UTC（[data-model.md](data-model.md) 6.3）；平台秒级时间戳在 adapter 边界转换。
- 写库集中在 service 的事务里；只读聚合查询可直接走 store。

### 5.14 日志与审计

- 结构化日志（structlog），统一挂脱敏处理器：cookie、手机号、收件人、详细地址一律打码（engineering-rules 8.1）。
- `audit_log` 记录每次外部调用的动作、请求摘要、响应摘要、结果、耗时；写操作保存完整请求与响应（脱敏后）。

### 5.15 实时推送

`GET /api/events` 用 SSE 推送：任务进度（`sync_progress`）、店铺状态变化（`shop_status_changed`，含会话、出口、风控暂停）、扫码失败（`shop_login_failed`）、打印回执、告警。前端收到后让对应查询失效重取。不用 WebSocket，因为只需服务端单向推送。

### 5.16 本机管理员登录（`service/auth.py`、`api/auth.py`）

**定位**：防止出单机上其他人直接打开后台操作店铺。只在本机使用，不做多租户、角色权限或对外授权（overview 2.2）。

| 项 | 规则 |
|---|---|
| 账号 | MVP 只有**一个管理员账号**（`admin_user` 表支持多行，便于以后扩展，但界面只允许一个） |
| 首次运行 | 没有任何账号时，前端进入「创建管理员」页；`POST /api/auth/setup` 只在账号数为 0 时可用，之后返回 409 |
| 密码 | 至少 8 位；用 **argon2id** 哈希存储（`argon2-cffi`），不存明文、不可逆 |
| 会话 | 登录成功生成 32 字节随机令牌，库里只存其 SHA-256；Cookie 名 `dd_admin`，`HttpOnly`、`SameSite=Strict`、`Path=/`。空闲 12 小时或自登录起 7 天过期 |
| 防暴力尝试 | 同一账号连续 5 次失败后锁定 5 分钟；失败提示不区分「账号不存在」和「密码错误」 |
| 鉴权范围 | 除 `/api/health`、`/api/auth/status`、`/api/auth/setup`、`/api/auth/login` 外，所有 `/api/*`（含 SSE `/api/events`）都要求有效会话，否则 401 |
| Host 校验 | 只接受 `Host` 为 `127.0.0.1:8787` 或 `localhost:8787` 的请求（开发时加 Vite 代理端口），防止 DNS 重绑定让外部网页调用本机接口 |
| 改密 | 已登录时 `POST /api/auth/password`（需旧密码）；改密后该账号的其他会话全部失效 |
| 忘记密码 | 只能在出单机命令行执行 `python -m app.cli reset-admin` 重设，不提供网页找回 |
| 审计 | 登录成功 / 失败、登出、改密写入 `audit_log`（`action=auth.*`）；写操作的 `audit_log` / `tasks` 记录操作人 `actor` |

### 5.17 每店独立环境：浏览器 profile + 固定独立出口（`service/egress.py`）

**决定（DEC-11，所有者）**：每家店一个独立浏览器 profile，加一个**固定、独立**的出口 IP。

| 项 | 规则 |
|---|---|
| 浏览器 profile | 每店一个持久化用户目录 `data/profiles/<shop_id>/`（5.1），cookie 与登录态互不串号 |
| 出口方式 | `direct`（商家自有宽带直连）或 `proxy`（独享静态 IP）；**不使用轮换代理池** |
| 代理协议 | 一律按 `http://账号:密码@主机:端口` 配置。Chromium / Edge 不支持带账号密码的 SOCKS5，扫码浏览器无法使用；带凭证的 `socks5://` 在配置时即拒绝 |
| 粘贴导入 | 出口设置可直接粘贴代理商格式 `IP\|端口\|账号\|密码\|到期日`，解析为 `http://` URL 与到期日 |
| 代理到期 | 记录 `proxy_expires_at`；到期前 7 天提醒；到期后该店暂停（同「出口不通」）。续费后 IP 若变化按「出口 IP 变化」处理 |
| 独立性 | 以**实际出口 IP** 判重：启用中的店铺两两不同。直连本身也是一个 IP，所以**最多一家店**用 `direct` |
| 一致性 | 同一家店的扫码浏览器、协议通道（curl_cffi）、浏览器兜底通道**都走同一出口** |
| 先配出口再扫码 | 店铺出口未配置或未通过检查时，不允许扫码登录；会话在哪个出口建立，就只在那个出口使用 |
| 更换出口 | 改代理地址 → 清空 `egress_ip`、状态复位为 `unchecked`，该店转 `needs_login`，必须重新扫码 |
| 出口检查 | 经该出口请求 IP 回显地址（设置项 `egress_echo_url`，默认 `https://api.ipify.org`）。**只有结果为 `ok` 时才写入 `egress_ip`**；`changed` / `duplicate` 时新 IP 写入 `egress_ip_pending`。时机：配置后、扫码前、每轮该店任务开始前（同一轮内缓存 10 分钟） |
| 出口不通 | 该店 `egress_status=unreachable`，暂停该店全部请求并提示；**绝不自动退回直连** |
| 出口 IP 变化 | 与 `egress_ip` 不同 → `egress_status=changed`，新 IP 存 `egress_ip_pending`，暂停该店；人工确认后 pending 转正、状态 `ok` |
| 出口 IP 重复 | 与其他启用店铺的 `egress_ip` 相同 → **`created_at` 较晚**的那家店 `egress_status=duplicate`（新 IP 存 `egress_ip_pending`），暂停 |
| 代理凭证 | 代理 URL（含账号密码）与 cookie 一样用 `SecretBox` 加密存库；日志只显示主机与端口 |
| 设备参数 | 不伪造。各店 profile 使用本机真实浏览器参数；扫码时记录该浏览器的 `User-Agent` 与 `sec-ch-ua*` 头，协议通道发请求时使用同一组值（参数前后不一致本身就是风控信号） |
| 统一入口 | 凡是会请求抖店的操作（定时任务、手动同步 / 探测 / 计数、扫码），都经 `ShopRunner.run`：先出口检查，再进该店串行队列（5.7） |

**风控暂停**：任一请求遇到 `RiskBlocked`（[flows.md](flows.md) 第 8 节）→ 该店写入 `paused_reason`，`ShopRunner` 跳过该店，
界面提示人工检查；人工点「恢复」（`POST /api/shops/{id}/resume`）后清除。出口异常与风控暂停都只影响该店。

**数据去向**：配置代理的店铺，请求经代理商隧道转发（HTTPS CONNECT，代理商看不到内容，只看到目标域名）；
cookie、订单数据等仍只存本机。

**平台规则风险**：每店独立出口的作用之一是降低店铺被平台关联判定的概率。是否符合平台规则由所有者判断并承担（gaps DEC-11）。
