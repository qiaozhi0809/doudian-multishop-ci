# 缺口清单（待补）

> 日期：2026-11-24 建立；2026-11-25 文档整理后更新。
> 用途：分派给负责人逐项补齐。每项写明「缺什么 / 为什么要 / 怎样算补完」。
> 设计文档见 [docs/README.md](README.md)。**已完成（✅）各行里出现的 `architecture.md` / `overall-design.md` 章节号指整理前的原文件**，
> 对照表见 [docs/README.md](README.md)「章节对照」；未完成各行已改为新文件位置。

**认领方式**：在「负责人」列填名字；补完后把「状态」改为 ✅，并按工程规范第九节同步更新 [api/](api/README.md) 或 [design/](design/overview.md) 中对应章节。

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
| API-03 | P0 | 面单账户接口 `GET /shopuser/power/getEbillAccountListByExpress` 正式收录 | 取号**必填**的 `net_code` / `ebill_id` 来自它；目前只在 A.2.2 的注释里提了一句，A.1 接口表、5.9 基础数据同步、表结构都没有 | 收录进附录 A.1：参数、返回结构、与快递/模板的对应关系；一个快递有多个网点或账户时选哪个 | | 🔶 已收录 A.1 与 5.9，并有京东月结样本（`monthlyAccountOrNetCode`、`balance=-1`）；**网点型快递字段待补抓**；多账户选择规则为建议稿，待 DEC-05 确认 |
| API-04 | P0 | 取号所需订单字段的来源 | 取号请求要 `combine_id`、`sku_order_id`、`sku_id`、`product_id`、`product_cnt`、`is_sub_bundle_item`；取号前置链路第 1 步的 `GET /api/order/orderListInfo` 不在 A.1 表里，`searchCombineOrder` 也没写返回结构 | 确认这些字段分别从哪个接口拿到（`searchlist` / `orderListInfo` / `searchCombineOrder`）；收录到 A.1 并附字段样本 | | 🔶 `searchlist` 两种参数都不返回 `combine_id`、实际 `sku_id`。2026-11-25 用新订单试探失败：该单为「源头好货」供应商代发单，「发货」按钮禁用；打单发货页因本机未装打印组件也不可用。**下一步**：在装了打印组件的机器上，用一笔商家自发的待发货单打开打单弹窗（不点确认），抓弹窗加载的请求。**M2 已实现字段就绪校验**：缺 `combine_id` / 实际 `sku_id` 的订单在预览与打单台被阻断并显示原因，字段来源仍需补测 |
| API-05 | P0 | 发货地址的行政区 ID | 取号与 `sendcheck` 的 `address` 要传 `province_id` / `city_id` / `town_id` / `street_id`；不清楚 `getAfterSaleList` 是否返回 | 确认 `getAfterSaleList` 返回字段；如不返回，找到 ID 的来源接口 | | ✅ 5.9（getAfterSaleList 已返回行政区 ID） |
| API-06 | P1 | 取号扩展验证 | 目前只验证过 1 单、1 个 SKU、中通 | 至少覆盖：一批多单、一单多 SKU、合单、第二家快递；`fail_orders_list` 结构与常见错误码（超区 / 余额不足 / 地址异常）；**同一订单重复取号**的平台行为（返回同号 / 新号 / 报错）；单批上限 | | 🔶 重复取号报「不存在可取号商品」，**但需确认第二次取号时订单是否已发货**（若已发货，结论不成立；用「取号后不发货」的订单重测）；多 SKU / 合单 / 第二家快递 / 单批上限待测。**M2 已按「失败项带 / 不带订单引用」两种结构容错实现**（write.md A.2.9 第 4 条） |
| API-07 | P1 | 打印数据转换 | 取号返回的 `print_data` + `sign` 是加密数据，转成打印组件 `documents` 的逻辑在前端 SDK 的 `mW()` 里，未搞清；打印链路目前不通 | 二选一给出结论：① 「借页面打印」（见 design/flows.md 第 10 节 P1）可行性验证；② `mW()` 转换逻辑说明。另需在出单机用真实热敏打印机打出一张面单 | | ✅ `documents` 结构已解开（flows.md 10 节）：signature + encryptedData + templateURL + params 字段映射，无需逆向；补打走 `batchGetPrintInfos`。未实测真实打印（需出单机热敏打印机） |
| API-08 | P1 | 面单作废接口 | 状态机「作废重取」依赖它；附录 A.2 标「未抓」 | 抓到路径、请求体、响应；说明作废后能否对同一订单重新取号 | | ✅ `batchCancelTrackingNos` 已验证（A.2.6）；作废后可重取号 |
| API-09 | P1 | 发货扩展验证 | 目前只验证过 1 个包裹 | 覆盖：一批多包裹、部分失败时 `fail_package_list` 结构；**同一运单重复发货**的平台行为 | | 🔶 重复发货已测（返回 success，服务端不阻止）；多包裹 / 部分失败待测 |
| API-10 | P1 | 地址解密的风控限制 | `receiveinfo` 返回 `verify_type`，说明有风控通道；多店批量解密是最容易触发风控的环节 | 实测：单店连续解密多少单会触发验证、触发后的返回形态、是否有日配额 | | 🔶 额度制度已写入 7.3（样本店当日剩 8 次）；频率风控：连续约 13 次 / 间隔 0.5~0.8s 触发 `602502151`。**待补**：①「3 小时恢复」出处（官方页面还是推断）；② 额度用完时的错误码；③ 安全间隔（2 秒为估计值） |
| API-11 | P1 | 写接口被风控拦截时的表现 | 错误分类（见 design/backend.md 5.2）需要知道「风控拦截」长什么样，才能和业务拒绝、会话失效区分 | 记录至少一种风控拦截的 `code` / `msg` / 是否要求验证码 | | 🔶 已记录风控样本 `10001010A`，但来自**只读**接口 `searchPackageList`；补完标准要求的写接口风控样本仍缺 |
| API-12 | P1 | 拉单增量与分页上限 | 5.4 写了「cursor/时间窗减少重复拉取」，但 `searchlist` 的增量参数没验证；`pageSize` 上限只知道 100 可用 | 确认按 `create_time` / `update_time` 窗口拉取的参数；`pageSize` 上限；订单号多值输入的格式（拼接串还是数组） | | 🔶 pageSize 上限 200 已确认（201 报 602502051）；增量时间窗 / 订单号多值待测 |
| API-13 | P2 | 取号 + 发货一体 `batchFetchTrackingNosAndDeliverGoods` | 打单台「打单并发货」按钮；源码结构已知，未真实调用 | 用测试单验证一次，记录请求与响应 | | 🔶 成功路径已实测（A.2.5，`success_deliver_list`）；**失败结构未记录；响应是否含 `print_data` 未确认**（不含则「打单并发货」后无法打印） |
| API-14 | P2 | `/order/torder/batchsend` 去留 | 打单台发货已确认走 `batchDeliverGoodsByEES`；`batchsend` 是否还需要不明确 | 确认订单页发货是否走它；不需要就从设计里移除 | | ✅ 电子面单场景不需要 batchsend（A.2.7），已从 5.2 / 7.5 移除；订单页「自行寄件发货」是否走它未核查，不影响 MVP |
| API-15 | P2 | 资金金额字段校准 | 资金账单 `CHARGE_BILL_ITEM` 金额字段名未知；保证金 `payable` / `balance` 单位（元/分）未知 | 用有账单、有保证金的店铺取样本，更新附录 F.4 | | 🔶 保证金单位：分（F.1c / F.4），`margin_account` 已改 `*_cents`；**待补对照依据**（50000 = 500 元是否与页面显示核对）；资金账单字段仍待有账单的店铺 |
| API-16 | P2 | 阶段二写接口 | 售后（同意退款 / 代填运单号 / 延长收货）、商品创建提交、库存修改、改物流 | 按附录 A.2 的「必查项」逐个验证；不阻塞 MVP | | 🔶 改物流 ✅（modifyLogistic，A.2.8）；售后 / 商品创建 / 库存修改待验证。**2026-11-25 实测受阻**：已发货订单申请退款后平台判定「平台主动处理」，商家无操作按钮；需买家以「不想要了 / 拍错了」等主观理由申请才有商家同意入口 |
| API-17 | P1 | 增值服务与产品类型接口 `POST /api/order/query_added_services_and_product_types` | 订单页「打单发货」链路第 3 步（A.2.7），只记了用途；一体接口的 `added_services`、`transport.expType` 可能取自这里 | 记录请求体与响应；确认是否必经、`added_services` / `expType` 取值怎么传 | | ✅ A.2.7 已补完整请求/响应；`selectedValue` 即 `transport.expType` 来源 |
| API-18 | P2 | 改物流 `modifyLogistic` 的两个参数 | A.2.8：`deliverId`（原包裹 ID）来源未确认，候选 `getOrderLogistics` / `orderDetail` 都没收录；`sendType: "1"` 含义未写，样本疑似「自行寄件」方式 | ① 确认 `deliverId` 来源接口并收录 A.1，说明与 `packages.package_no` 的关系；② 补 `sendType` 枚举，至少覆盖「自行寄件」与「打单发货」两种重新发货方式 | | 🔶 `deliverId` ✅ 来源 `get_manual_send_order_info`（A.1 / A.2.8，实测值 147767673767714066）；`sendType` 枚举仍待补 |
| API-19 | P0 | 取号超时 / 响应丢失后的恢复 | 平台拒绝对已取号订单再次取号（A.2.2 第 8 条），取号成功但响应丢失时，重试拿不回运单号（5.5） | 找到查询「已取号未发货订单的当前运单号」的接口（候选 `searchCombineOrder` 已打单列表 / 订单详情），确认免签名并收录 A.1；一体接口可用订单列表 `latest_logistic_info.tracking_no` 查回，需实测 | | 🔶 候选接口 `getOrderLogistics`（5.5 / A.1）；**关键情形未验证**：它疑似只列已发货物流，须用「已取号、未发货」订单实测能否查到运单号；一体接口的 `latest_logistic_info` 待实测。**M2 已按查回实现**（`service/label_recovery.py` + ReplayTransport 测试：查到补写面单、查不到保持 `verifying`），真实场景仍待验证 |
| API-20 | P1 | 新收录接口的签名状态 | `getOrderLogistics`、`orderDetail`、`get_manual_send_order_info`、`query_added_services_and_product_types` 未写明是否免签名；5.3 已规定逐接口验证（`searchPackageList` 就是例外） | 对 4 个接口各做一次浏览器外无签名直连，结果写进 A.1 备注 | | ⏳ |
| API-21 | P1 | 取号前 `sendcheck` 是否必经 | 页面在取号前会调 `sendcheck`（api/write.md A.2.2 前置链路）；不调直接取号是否会失败或有风险未知 | 用测试单跳过 `sendcheck` 直接取号一次，记录结果 | | ⏳ **M2 暂不调用**：取号前只做本地预检（默认地址 / 模板 / 可用账户 / 订单字段），见 write.md A.2.9；有结论后决定是否补 |
| API-22 | P1 | 自渲染面单的合规性 | flows.md 第 10 节方案 B 要用明文地址自绘面单；是否符合平台电子面单 / 隐私面单规范未确认 | 查平台规则或客服确认；不允许则删除方案 B | | ⏳ |
| API-23 | P1 | `searchlist` 时间筛选与状态枚举（仪表盘） | 仪表盘按 `pay_time` 归日（design/dashboard.md） | 确认能否按 `pay_time` / `create_time` 筛时间窗、默认排序与深度翻页上限；数字 `order_status` 完整枚举（未支付、待发货是几）；未支付订单的 `pay_time` 取值；时间字段是秒还是字符串 | | 🔶 数字状态码已见 `2` 待发货、`3` 已发货、`4` 已关闭、`5` 已完成（2026-11-25 样本）；`searchlist` 时间窗筛选、未支付订单 `pay_time`、深度翻页仍待测 |
| API-24 | P2 | 商家实收字段口径 | 仪表盘「商家实收」 | 用同一订单对照 `actual_receive_amount_int` 与待结算 `income_amount`，说明是否已扣平台服务费 | | ⏳ |
| API-25 | P1 | 售后按时间统计 | 售后率、退款率（dashboard.md 1.2） | 售后列表能否按 `apply_time` / `update_time` 筛选排序；退款成功的状态码与成功时间字段；`after_sale_type` 枚举含义 | | ⏳ |
| API-26 | P2 | 商品金额与流量字段 | 按金额的商品排行、曝光 / 点击 | 订单商品行的单价 / 分摊金额字段；`listTractionItems` 返回字段 | | ⏳ |
| API-27 | P2 | 抖店罗盘经营概览（待抓取） | 平台官方 GMV / 退款 / 访客，作为仪表盘参考值（dashboard.md 第 5 节） | 抓取 `compass.jinritemai.com` 经营概览接口；确认现有会话能否访问、是否需签名 | | ⏳ |
| API-28 | P1 | 识别商家不能自行发货的订单 | 「源头好货」等供应商代发订单在「待发货」tab 里，但商家不能取号 / 发货（按钮禁用，提示「供应商发货后自动更新订单状态」）。混进取号批次会被平台拒绝 | 确认判别字段：样本中该单 `operation_actions` 为空数组（自发订单含发货类动作），或订单 / 商品行的「源头好货」「由供应商发货」标记；写入 `docs/api/read.md`，订单同步时标记为不可取号（backend 5.4 / 5.5 预检） | | ⏳ |
| API-29 | P1 | 补打接口 `batchGetPrintInfos` 的响应结构 | M3 打印用它在打印前补齐 `templateURL` / `OAuth`，并给恢复面单补 `print_data`（flows 10、write.md A.2.10）；目前只有请求体，响应结构靠容错解析 | 在出单机用一张已取号面单调一次，记录完整响应；确认 `print_data` / `sign` / `templateURL` / `OAuth` 的字段名与包裹层级，以及模板为自定义时是否在 `custom_*` 字段 | | 🔶 M3 已按常见包裹形态容错（`adapter/doudian/print_parsers.py`），解析为空时走手动补打，不猜测成功 |

---

## 二、文档矛盾 / 过时内容

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
| DOC-12 | P2 | architecture.md 全文 | 2106 行，超出工程规范 600 行硬上限 | 按正文 / 附录 A~G 拆成多文件（engineering-rules 3.3 已列为待办） | | ✅ 2026-11-25 已拆分为 `design/` 7 个文件与 `api/` 8 个文件，均 ≤ 600 行（[docs/README.md](README.md)） |
| DOC-13 | P1 | 附录 A.2.2 取号请求样本 | `address`（店铺发货地址）含真实姓名、手机号、详细地址，违反工程规范 8.1 | 本次 PR 已替换为占位符。**但 git 历史中仍有原文**，是否改写历史由仓库所有者决定 | — | ✅ 2026-11-25 已改写 git 历史：6 个分支中真实姓名、手机号、详细地址与分机号全部替换为占位符并强制推送。**残留**：已合并 PR 的只读引用 `refs/pull/1/head`、`refs/pull/2/head` 仍指向旧提交，需所有者向 GitHub Support 申请清除 |

---

## 三、数据模型缺口（[design/data-model.md](design/data-model.md)）

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
| DM-10 | P2 | 改物流后的本地状态 | 已发货订单换运单号后：旧面单标 `void` 还是新增 `replaced`；新运单如何入 `waybills`；订单状态是否保持 `shipped`；对账如何避免误报 `waybill_mismatch`。写进 6.1 / 6.2（阶段二，依赖 API-18） | | ⏳ |
| DM-11 | P1 | 解密后明文地址的存储与清除 | `receiveinfo` 返回 `expire_time`，明文有有效期；现设计把明文长期存 `orders.receiver_address` 并据此判断「已解密」（7.3 约束 2）。需定：加密存储方式、按 `expire_time` 清除、到期后不再视为已解密、日志与导出中不出现明文。DEC-06 已定为按需解密，明文只来自用户查看，存储量很小 | | ✅ 2026-11-25 改为明文不入库：只在后端内存中缓存到 `expire_time`（flows 7.3），无需加密存储与清除逻辑 |

---

## 四、工程与方案细化（整体方案已给方向，细节待补）

| ID | 优先级 | 缺口 | 补完标准 | 负责人 | 状态 |
|---|---|---|---|---|---|
| ENG-01 | P0 | 本地 API 详细契约 | 在 [design/local-api.md](design/local-api.md) 草案基础上，给每个接口写 pydantic 请求/响应 schema 与错误码 | | 🔶 打单台与解密接口 schema 已落地（`api/label_schemas.py` / `api/order_schemas.py`，OpenAPI 随代码生成）；其余分组待补 |
| ENG-02 | P0 | 抖店错误码分类表 | 把已见过的 `code` 归入「会话失效 / 业务拒绝 / 风控拦截 / 瞬时故障 / 程序错误」五类，落到 `adapter/doudian/error_codes.py` 的设计说明 | | 🔶 第 8 节已有错误码表（10008 / 10001010A / 310011 / 602500705 / 100000）；待按五类异常补全并落到 `error_codes.py` 设计 |
| ENG-03 | P1 | 打印路径决策 | 依据 API-07 的结论，在 design/flows.md 第 10 节的路径中定下 MVP 默认路径 | | ✅ P1 直连组件为默认路径，M3 已实现（`adapter/print` + `service/printing` + `api/print`）；P3 手动补打为保底 |
| ENG-04 | P1 | 出单机部署与打包 | 打包方式、首次安装步骤、Edge / 打印组件依赖检查、升级方式；对应验收标准第 7 条 | | ✅ [design/deployment.md](design/deployment.md)：zip + venv（`backend/requirements.txt` 锁定）+ `scripts/start|stop.ps1|.bat`；首次安装、依赖检查清单、升级 / 回滚、排障齐全；PyInstaller 记作未验证的备选 |
| ENG-05 | P1 | CI 守门脚本 | engineering-rules 第十节 7 个脚本全部「待建」，按其列出的顺序落地 | | ⏳ |
| ENG-06 | P2 | 备份与恢复 | SQLite 每日快照的保留策略、恢复演练步骤 | | ✅ `service/backup.py`（sqlite3 在线备份，WAL 安全）+ `backup_run` 表（0007）+ 每日 04:00 快照、保留 `DD_BACKUP_KEEP`（默认 7）+ `GET /api/backup/snapshots` / `POST /api/backup/run` + 设置页「立即备份」；恢复步骤与演练见 deployment.md §7 |
| ENG-07 | P2 | 通知通道 | 掉线 / 打印失败 / 临近超时发货的通知方式（界面内 / 系统通知 / 外部 IM） | | ✅ 界面内 SSE：掉线走会话健康指示（一键重登）、打印失败走通知中心 / 打单台、临近超时新增 `ship_deadline_warning`（每 30 分钟扫描 `exp_ship_time`，阈值 `DD_SHIP_DEADLINE_WARN_HOURS`，再由通知中心翻译成强提醒）；不接外部 IM |

---

## 五、待拍板的决策

这些不是「缺资料」，而是需要所有者决定：

| ID | 问题 | 选项 | 建议 |
|---|---|---|---|
| DEC-01 | 打单台默认按钮 | 「打面单」（保留已取号中间态）/「打单并发货」（一步到位） | 默认「打面单」，与 7.3 一致 |
| DEC-02 | 对账时间窗 | 7 天 / 30 天 | 30 天（附录 G.5 已发现 7 天会漏单） |
| DEC-03 | 前端交付节奏 | 集中在 M6 / 随各里程碑交付对应页面 | 随里程碑交付（见 design/overview.md 13.1） |
| DEC-04 | 面单作废是否进 MVP | 是 / 否 | 是（见 DOC-08） |
| DEC-05 | 同一快递多个面单账户时选哪个 | 见 design/backend.md 5.9 建议稿：用户指定 → `isDefault` → `balance` 最大 | 按建议稿；如有网点 / 结算上的业务考虑需调整 |
| DEC-06 | 取号前是否必须先解密收货地址 | 保留「先解密」/ 取号与官方组件打印都不解密 | ✅ **已决定（2026-11-25，所有者）：不解密**。只在用户查看收件人或自渲染 PDF 时按需解密；architecture 5.5 / 6.3 / 7.3 / 12 / 13 / 14 / 15 / A.4 / B.1 与 overall-design 第 4、6 节已同步 |
| DEC-07 | 仪表盘「出单率」指什么 | 出单店铺率（今天有几家店出单）/ 动销率 / 发货及时率 | ✅ **已定（设计决定）**：主显示出单店铺数 x / N，并列发货及时率；动销率放商品区（dashboard.md 1.3） |
| DEC-08 | 售后率口径 | 同期（当天申请 ÷ 当天支付）/ 回溯（某天支付的订单后来发生售后的比例） | ✅ **已定（设计决定）**：日视图同期口径；周 / 月回溯口径，近 30 天标「未成熟」（dashboard.md 1.2） |
| DEC-09 | 仪表盘订单事实表是否与对账快照合并 | 合并为 `order_fact` / 分开两张表 | ✅ **已定（设计决定）**：合并，`order_fact` 替代 `orders_snapshot`，对账改读 `order_fact` |
| DEC-10 | 是否需要后台登录 / 账号体系 | 不设账号（仅本机访问）/ 本机单管理员登录 / 多账号与角色 | ✅ **已决定（2026-11-25，所有者）：做管理账号登录**。MVP 为本机单管理员（argon2id、会话 Cookie、失败锁定、Host 校验），多账号与角色暂不做（backend 5.16） |
| DEC-11 | 多店网络环境 | 共用直连 / 轮换代理池 / 每店独立 profile + 固定独立出口 | ✅ **已决定（2026-11-25，所有者）：每店独立 profile + 固定独立出口 IP**。不用轮换代理池；最多一家直连；出口 IP 唯一；异常暂停不回退直连；不伪造指纹（backend 5.17）。作用之一是降低平台关联判定，是否符合平台规则由所有者判断。2026-11-26 追加：浏览器统一改为 CloakBrowser 定制 Chromium（Chromium 146，免费版无 license）；每店固定指纹种子，不轮换。 |
| DEC-12 | 店铺删除策略 | 硬删除 / 软删除 / 只停用 | ✅ **已决定（2026-11-26，所有者）：只提供停用，不做删除**。停用后该店不占代理池、不参与定时任务与默认视图，但订单、对账、面单等历史数据完整保留。后端无 DELETE 接口：`session` / `task` / `waybill` / `order` / `shop_profile` 均外键引用 `shop`，硬删会破坏对账凭据 |
