# 缺口清单（待补）

> 日期：2026-11-24
> 来源：对 [architecture.md](architecture.md) 与 [engineering-rules.md](engineering-rules.md) 的完整审阅。
> 用途：分派给负责人逐项补齐。每项写明「缺什么 / 为什么要 / 怎样算补完」。
> 整体方案（前后端设计、本地接口、技术栈）见 [overall-design.md](overall-design.md)，本清单不重复。

> **2026-11-25 更新**：DOC-01~11、DM-01~09、API-01/02/03/04/05/07/13 已在
> `architecture.md` 与 `engineering-rules.md` 中补充落位，状态列已同步。
> 剩余项（API-06、08~12、14~16，ENG-01~07，DEC-01~04）待继续验证或拍板。

**认领方式**：在「负责人」列填名字；补完后把「状态」改为 ✅，并按工程规范第九节同步更新 `architecture.md` 对应附录。

**优先级**：
- **P0**：阻塞 M1 / M2（不补就没法开始写对应模块）
- **P1**：阻塞履约闭环（M3 / M4）或验收
- **P2**：阶段二或质量问题，不阻塞 MVP

---

## 一、抖店接口：待验证 / 待收录

> 大多需要**真实店铺 + 真实待发货订单**，属于客观条件卡住的验证项。
> 写操作验证一律用测试单，先确认请求体，再真实提交。

| ID | 优先级 | 缺口 | 为什么要 | 补完标准 | 负责人 | 状态 |
|---|---|---|---|---|---|---|
| API-01 | P0 | `__token` / `_lid` / `aid` / `appid` 的来源与有效期 | 所有请求都带这几个公共参数；7.1 只写了「页面公共参数」，没写怎么拿。拿不到，协议直连通道就无法独立工作 | 写清每个参数：从哪个页面变量或接口取、浏览器外能否获取、有效期、失效时的返回 | | ✅ 7.1 公共参数完整；**`_lid` 只读与写接口均不校验**（只读三组对照 + 取号/发货随机值实测 2026-11-25） |
| API-02 | P0 | 会话有效期与 cookie 续期 | 决定会话探测频率和重登提示时机；协议直连响应若下发 `Set-Cookie` 需要回写，否则会话会提前过期 | 实测一个店从扫码到失效的时长；说明响应是否刷新 cookie、哪些 cookie 会变 | | 🔶 5.1 已补 60 天有效期；cookie 刷新待验证 |
| API-03 | P0 | 面单账户接口 `GET /shopuser/power/getEbillAccountListByExpress` 正式收录 | 取号**必填**的 `net_code` / `ebill_id` 来自它；目前只在 A.2.2 的注释里提了一句，A.1 接口表、5.9 基础数据同步、表结构都没有 | 收录进附录 A.1：参数、返回结构、与快递/模板的对应关系；一个快递有多个网点或账户时选哪个 | | 🔶 已收录 A.1 与 5.9；**多账户选择规则为建议稿**（5.9），待 DEC-05 确认 |
| API-04 | P0 | 取号所需订单字段的来源 | 取号请求要 `combine_id`、`sku_order_id`、`sku_id`、`product_id`、`product_cnt`、`is_sub_bundle_item`；取号前置链路第 1 步的 `GET /api/order/orderListInfo` 不在 A.1 表里，`searchCombineOrder` 也没写返回结构 | 确认这些字段分别从哪个接口拿到（`searchlist` / `orderListInfo` / `searchCombineOrder`）；收录到 A.1 并附字段样本 | | 🔶 6.2 字段已补；A.2.2 补「`combine_id` 必填（空报 310011）」「`sku_id` ≠ searchlist 值」；来源接口待确认（searchPackageList 需签名） |
| API-05 | P0 | 发货地址的行政区 ID | 取号与 `sendcheck` 的 `address` 要传 `province_id` / `city_id` / `town_id` / `street_id`；不清楚 `getAfterSaleList` 是否返回 | 确认 `getAfterSaleList` 返回字段；如不返回，找到 ID 的来源接口 | | ✅ 5.9（getAfterSaleList 已返回行政区 ID） |
| API-06 | P1 | 取号扩展验证 | 目前只验证过 1 单、1 个 SKU、中通 | 至少覆盖：一批多单、一单多 SKU、合单、第二家快递；`fail_orders_list` 结构与常见错误码（超区 / 余额不足 / 地址异常）；**同一订单重复取号**的平台行为（返回同号 / 新号 / 报错）；单批上限 | | 🔶 重复取号已测（报「不存在可取号商品」）；多 SKU / 合单 / 第二家快递 / 单批上限待测 |
| API-07 | P1 | 打印数据转换 | 取号返回的 `print_data` + `sign` 是加密数据，转成打印组件 `documents` 的逻辑在前端 SDK 的 `mW()` 里，未搞清；打印链路目前不通 | 二选一给出结论：① 「借页面打印」（见 overall-design 第 2.6 节）可行性验证；② `mW()` 转换逻辑说明。另需在出单机用真实热敏打印机打出一张面单 | | 🔶 10 章 print 消息已验证；数据转换待解 |
| API-08 | P1 | 面单作废接口 | 状态机「作废重取」依赖它；附录 A.2 标「未抓」 | 抓到路径、请求体、响应；说明作废后能否对同一订单重新取号 | | ⏳ |
| API-09 | P1 | 发货扩展验证 | 目前只验证过 1 个包裹 | 覆盖：一批多包裹、部分失败时 `fail_package_list` 结构；**同一运单重复发货**的平台行为 | | 🔶 重复发货已测（返回 success，服务端不阻止）；多包裹 / 部分失败待测 |
| API-10 | P1 | 地址解密的风控限制 | `receiveinfo` 返回 `verify_type`，说明有风控通道；多店批量解密是最容易触发风控的环节 | 实测：单店连续解密多少单会触发验证、触发后的返回形态、是否有日配额 | | ⏳ |
| API-11 | P1 | 写接口被风控拦截时的表现 | 错误分类（见 overall-design 2.2）需要知道「风控拦截」长什么样，才能和业务拒绝、会话失效区分 | 记录至少一种风控拦截的 `code` / `msg` / 是否要求验证码 | | ✅ 已记录 `10001010A`（searchPackageList 无签名直连触发） |
| API-12 | P1 | 拉单增量与分页上限 | 5.4 写了「cursor/时间窗减少重复拉取」，但 `searchlist` 的增量参数没验证；`pageSize` 上限只知道 100 可用 | 确认按 `create_time` / `update_time` 窗口拉取的参数；`pageSize` 上限；订单号多值输入的格式（拼接串还是数组） | | 🔶 pageSize 上限 200 已确认（201 报 602502051）；增量时间窗 / 订单号多值待测 |
| API-13 | P2 | 取号 + 发货一体 `batchFetchTrackingNosAndDeliverGoods` | 打单台「打单并发货」按钮；源码结构已知，未真实调用 | 用测试单验证一次，记录请求与响应 | | 🔶 A.2.5 结构已知，待实测 |
| API-14 | P2 | `/order/torder/batchsend` 去留 | 打单台发货已确认走 `batchDeliverGoodsByEES`；`batchsend` 是否还需要不明确 | 确认订单页发货是否走它；不需要就从设计里移除 | | ⏳ |
| API-15 | P2 | 资金金额字段校准 | 资金账单 `CHARGE_BILL_ITEM` 金额字段名未知；保证金 `payable` / `balance` 单位（元/分）未知 | 用有账单、有保证金的店铺取样本，更新附录 F.4 | | 🔶 保证金单位已确认（分：basic_balance 50000=500元）；账单字段仍待有账单店铺；`margin_account` 暂存原始值（`payable` / `balance`），校准后迁移为 `*_cents` |
| API-16 | P2 | 阶段二写接口 | 售后（同意退款 / 代填运单号 / 延长收货）、商品创建提交、库存修改、改物流 | 按附录 A.2 的「必查项」逐个验证；不阻塞 MVP | | ⏳ |

---

## 二、文档矛盾 / 过时内容（改 architecture.md）

| ID | 优先级 | 位置 | 问题 | 应改为 | 负责人 | 状态 |
|---|---|---|---|---|---|---|
| DOC-01 | P0 | 附录 A.2 标题与说明框；附录 C.4 | 标题写「全部待定，均未真实调用」，说明框写「下面所有写接口都未验证」；但表里批量备注 / 取号 / 发货前检查 / 发货已标 ✅。C.4 仍写批量备注「未验证」 | 标题改为「写接口（部分已验证）」；说明框只针对未验证项；C.4 同步 | | ✅ 已改 |
| DOC-02 | P0 | 附录 A.0 总览表「订单」行 | 把取号、发货、批量备注写在「只读接口」列 | 移到「写接口」列并标已验证 | | ✅ 已核对 |
| DOC-03 | P0 | 5.6、第 13 节 M4、第 16 节清单 | 发货仍写 `/order/torder/batchsend` + `send_list` / `deliverType` | 改为已验证的 `batchDeliverGoodsByEES`（按「快递编码 + 运单号」发货，`send_type: "3"`）；幂等键同步改为 `ship:{shop_id}:{courier_code}:{tracking_no}` | | ✅ 5.6 / M4 / 幂等键已改 |
| DOC-04 | P0 | 2.1、7.4、11.2、第 13 节 M3 | 打印组件写成 `ws://127.0.0.1:13999` | 第 10 节已验证必须用 `wss://localhost:13999`（自签证书 + Origin 头），全文统一 | | ✅ 全文改 wss://localhost:13999 |
| DOC-05 | P0 | 第 16 节 M0 清单 | 「为真实订单取号」「执行真实发货回传」「确认 `send_type`」「确认写接口是否强制签名」「`customTempCode` vs `parentTempCode`」仍未勾，但附录 A.2 已验证 | 勾掉并注明证据位置；第 13 节 M0 状态同步 | | ✅ M0 清单已同步 |
| DOC-06 | P0 | engineering-rules.md 8.3 | 「写接口签名要求未验证前，一律走浏览器兜底」；现已验证 4 个写接口免签名 | 改为「逐接口声明：已验证免签名的走协议直连；未验证的走浏览器兜底」 | | ✅ 8.3 改逐接口声明 |
| DOC-07 | P0 | architecture.md 5.x / 11.4 与 engineering-rules.md 2.2 | 两份文档规定的目录不同（`channels/` `services/` `db/` vs `adapter/` `service/` `store/`） | 以工程规范为准（overall-design 第 2.1 节已采用），architecture.md 的模块路径全部改成新名 | | ✅ 目录树与命名已统一 |
| DOC-08 | P1 | 2.1 与 2.3、附录 B.2 | 「面单作废与重打」2.1 列入 MVP，2.3 与 B.2 列入阶段二 | 定一个；建议 MVP 保留（状态机依赖作废），前提是 API-08 补齐 | | ✅ MVP 保留并注明依赖 API-08 |
| DOC-09 | P1 | 6.1 状态机、6.2 `waybills.status`、7.4 | 7.4 用了 `print_failed`，但订单状态机与 `waybills.status` 枚举里都没有；「打单并发货」会从 `pending_label` 直达 `shipped`，状态机未画 | 补 `print_failed`（或明确它只是 `waybills.status=failed`）；补一体化直达路径 | | ✅ `print_failed` 已移出订单状态（6.1 / 7.4 / 第 10 节统一为 `print_job.status=failed`，订单停在 `label_obtained`）；快捷路径已补 |
| DOC-10 | P1 | 文档头部、第 11.4 节、engineering-rules 3.3 | 引用的 `case/notes/*`、`case/forensic/` 不在仓库；项目路径写 `E:\抖店多店铺管理`、`docs/superpowers/specs/`；3.3 引用的文件名不存在 | 证据目录要么入库（先脱敏），要么注明存放位置；路径改成本仓库的实际路径 | | ✅ 路径改 artifacts/（不入库） |
| DOC-11 | P2 | 7.5、10、A.2.x | 验证日期写 2026-11-25，晚于文档更新日期 2026-11-24 | 核对并统一日期 | | ✅ 日期已统一 |
| DOC-12 | P2 | architecture.md 全文 | 2106 行，超出工程规范 600 行硬上限 | 按正文 / 附录 A~G 拆成多文件（engineering-rules 3.3 已列为待办） | | ⏳ 保留（P2） |
| DOC-13 | P1 | 附录 A.2.2 取号请求样本 | `address`（店铺发货地址）含真实姓名、手机号、详细地址，违反工程规范 8.1 | 本次 PR 已替换为占位符。**但 git 历史中仍有原文**，是否改写历史由仓库所有者决定 | — | 🔶 |

---

## 三、数据模型缺口（改 architecture.md 第 6 节）

| ID | 优先级 | 缺口 | 补完标准 | 负责人 | 状态 |
|---|---|---|---|---|---|
| DM-01 | P0 | `shop_address` 缺行政区 ID 列 | 增加 `province_id` / `city_id` / `town_id` / `street_id` 及名称列（依赖 API-05） | | ✅ 6.2 shop_address 已补 |
| DM-02 | P0 | 缺面单账户表 | 新增 `ebill_account`：`shop_id`、`courier_code`、`ebill_id`、`net_code`、网点名、余额（如有）、`raw_json`、`synced_at`（依赖 API-03） | | ✅ 6.2 ebill_account 已补 |
| DM-03 | P0 | `order_items` / `orders` 缺取号所需字段 | `order_items` 加 `sku_order_id`、`product_id`；`orders` 加 `combine_id`（依赖 API-04） | | ✅ 6.2 order_items / orders 已补 |
| DM-04 | P1 | `waybills` 缺打印数据 | 明确 `label_payload` 存什么；加 `print_data`、`sign`、`logistics_template_code`、`ebill_id` | | ✅ 6.2 waybills 已补 |
| DM-05 | P1 | 缺打印任务表 | 新增 `print_job`：批次、打印机、状态、组件回执、重试次数 | | ✅ 6.2 print_job 已补 |
| DM-06 | P1 | 附录 G 的 `orders_snapshot` 未进 6.2 | 补表结构，并按 G.7 写明与 `orders` 的合并计划 | | ✅ 6.4 已引用 |
| DM-07 | P1 | 只读聚合模块无表 | 补 `aftersale`（附录 E.7 已给字段）、`product_snapshot`、`stock_snapshot`、`fund_unsettled`、`margin_account` | | ✅ 6.2 ⑯~⑳ 已建表（`stock_snapshot` 含 `future_stock_num`；`aftersale` 时间存 ISO、枚举存数字；`fund_unsettled` 唯一键列非空） |
| DM-08 | P1 | 会话存储两处并存 | `session.cookies` 与 `cookies/` 目录二选一；存储需加密（overall-design 2.3 建议 DPAPI） | | ✅ 6.4 已定（DPAPI） |
| DM-09 | P2 | 迁移机制 | 表结构变更的迁移方式（overall-design 建议 Alembic）与初始迁移脚本 | | ✅ 6.4 已定（Alembic） |

---

## 四、工程与方案细化（整体方案已给方向，细节待补）

| ID | 优先级 | 缺口 | 补完标准 | 负责人 | 状态 |
|---|---|---|---|---|---|
| ENG-01 | P0 | 本地 API 详细契约 | 在 overall-design 第 4 节草案基础上，给每个接口写 pydantic 请求/响应 schema 与错误码 | | ⏳ |
| ENG-02 | P0 | 抖店错误码分类表 | 把已见过的 `code` 归入「会话失效 / 业务拒绝 / 风控拦截 / 瞬时故障 / 程序错误」五类，落到 `adapter/doudian/error_codes.py` 的设计说明 | | ⏳ |
| ENG-03 | P1 | 打印路径决策 | 依据 API-07 的结论，在 overall-design 2.6 的三条路径中定下 MVP 默认路径 | | ⏳ |
| ENG-04 | P1 | 出单机部署与打包 | 打包方式、首次安装步骤、Edge / 打印组件依赖检查、升级方式；对应验收标准第 7 条 | | ⏳ |
| ENG-05 | P1 | CI 守门脚本 | engineering-rules 第十节 7 个脚本全部「待建」，按其列出的顺序落地 | | ⏳ |
| ENG-06 | P2 | 备份与恢复 | SQLite 每日快照的保留策略、恢复演练步骤 | | ⏳ |
| ENG-07 | P2 | 通知通道 | 掉线 / 打印失败 / 临近超时发货的通知方式（界面内 / 系统通知 / 外部 IM） | | ⏳ |

---

## 五、待拍板的决策

这些不是「缺资料」，而是需要所有者决定：

| ID | 问题 | 选项 | 建议 |
|---|---|---|---|
| DEC-01 | 打单台默认按钮 | 「打面单」（保留已取号中间态）/「打单并发货」（一步到位） | 默认「打面单」，与 7.3 一致 |
| DEC-02 | 对账时间窗 | 7 天 / 30 天 | 30 天（附录 G.5 已发现 7 天会漏单） |
| DEC-03 | 前端交付节奏 | 集中在 M6 / 随各里程碑交付对应页面 | 随里程碑交付（见 overall-design 第 6 节） |
| DEC-04 | 面单作废是否进 MVP | 是 / 否 | 是（见 DOC-08） |
| DEC-05 | 同一快递多个面单账户时选哪个 | 见 architecture 5.9 建议稿：用户指定 → `isDefault` → `balance` 最大 | 按建议稿；如有网点 / 结算上的业务考虑需调整 |
