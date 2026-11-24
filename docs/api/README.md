# 抖店接口（附录 A ~ G）

> 本目录记录所有抖店内部接口的实测结论。设计文档见 [../design/](../design/overview.md)，索引见 [../README.md](../README.md)。
> 证据样本：`artifacts/`（本地留存，不入库）。新增接口前必须先在这里记录实测结果（engineering-rules 8.5）。

| 文件 | 内容 |
|---|---|
| 本页 | A.0 验证总览、签名判断、A.3 页面路径、A.4 关键结论、A.5 M0 验证清单 |
| [read.md](read.md) | A.1 只读接口 |
| [write.md](write.md) | A.2 写接口（取号 / 发货 / 一体 / 作废 / 改物流 / 备注 / 发货前检查） |
| [order-page.md](order-page.md) | 附录 C：订单管理页 UI → 接口字段 |
| [catalog.md](catalog.md) | 附录 D：商品 / 库存 |
| [aftersale.md](aftersale.md) | 附录 E：售后 |
| [fund.md](fund.md) | 附录 F：资金 |
| [reconcile.md](reconcile.md) | 附录 G：跨店对账逻辑 |

### A.0 验证状态总览（2026-11-25）

| 模块 | 只读接口 | 写接口 | 数据样本 |
|---|---|---|---|
| 会话 | ✅ 探测 / cookie 导出 | — | ✅ |
| 订单 | ✅ 列表 / 筛选（8 项）/ 计数 / 地址解密 | ✅ 取号 / 发货前检查 / 发货 / 取号发货一体 / 批量备注 / 面单作废 / 改物流 | ✅ 18 单 + 新店 529 单 |
| 商品 | ✅ 列表 / 计数 / 分组 / 类目树 | ⏳ 创建提交 | ✅ 6 个商品 |
| 库存 | ✅ 列表 / 仓库列表 | ⏳ 库存修改 | ✅ |
| 售后 | ✅ 列表 / 计数 / 详情 | ⏳ 同意退款 / 填运单号 / 延长收货 | ✅ 8 单 |
| 资金 | ✅ 待结算 / 账单 / 保证金（单位：分） | — | ⚠️ 待结算 7 条；账单 0 条 |
| 对账 | ✅ 基于订单列表 | — | ✅ 18 单 |
| 店铺 | ✅ 画像 / 管理人 / 绑定账号 | — | ✅ |
| 打印 | — | 🔶 组件协议已验证（`getPrinters` / `print`）；`print_data` 转换未解 | ❌ 需出单机 |

**主要未确认项**（完整清单见 [gaps.md](../gaps.md)）：

1. 打印数据 `print_data` 的转换 / 借页面打印可行性（API-07）—— 需出单机
2. 取号超时后能否查回「已取号未发货」订单的运单号（API-19）
3. 取号字段 `combine_id` / 实际 `sku_id` 的免签名来源（API-04）
4. 资金账单 `CHARGE_BILL_ITEM` 金额字段 —— 需有账单的店铺
5. 售后、商品、库存写接口（阶段二）

### 签名判断

- 只读接口：已验证的 20+ 个免签名，但**存在例外**（`searchPackageList` 无签名触发风控 `10001010A`），
  不能整体假设免签名
- 写接口：已验证的 7 个（批量备注 / 取号 / 发货前检查 / 发货 / 取号发货一体 / 面单作废 / 改物流）均免签名；
  售后、商品、库存写接口未验证
- 任一接口确认需签名时，用 Playwright 在页面内执行 fetch（浏览器渠道兜底），业务代码不需改动

### A.3 页面路径

| 功能 | 路径 |
|---|---|
| 订单管理 | `/ffa/morder/order/list` |
| 打单发货 | `/ffa/morder/logistics/ewaybill-delivery` |
| 手工打单 | `/ffa/morder/logistics/ewaybill-delivery-manual` |
| 电子面单 | `/ffa/logistics-project/eBill/landing` |
| 发货 | `/ffa/morder/logistics/delivery` |
| 批量发货 | `/ffa/morder/logistics/combine-delivery` |
| 批量导入发货 | `/ffa/morder/delivery/upload` |

### A.4 关键结论

- 大多数只读接口：Cookie + `__token` 即可（浏览器外已验证 200）；**例外** `searchPackageList` 需签名。
- `a_bogus` / `msToken` / `verifyFp`：风控打分参数，已验证的读写接口均非必需；`_lid` 不校验。
- 会话探测用 `/api/order/tabcnt`（未登录 = `code:10008`）；
  `/ecomauth/loginv1/session_check` 不可用（无 cookie 也返回 `check_code:0`）。
- 分页基准不统一：`searchlist` / 商品 / 资金为 0-based，`getAfterSaleList` / 售后 / 库存为 1-based；`searchlist` 的 `pageSize` 上限 200。
- 列表返回的收货信息为**脱敏值**（`辛*` / `1**********`），取号与官方组件打印**不需要**明文（DEC-06）；查看收件人或自渲染 PDF 时才调 `receiveinfo` 解密。
- 写接口：已验证的 7 个均免签名；平台**不拦重复发货**、**拒绝重复取号**（[write.md](write.md) A.2.2 / A.2.4）。
- 打印：官方组件本地 WebSocket（默认 13999）。

### A.5 M0 技术验证清单（原 `architecture.md` 第 16 节）

> 在写正式代码之前完成。任何一项失败，先调整方案再继续。

- [x] 登录抖店并导出 cookie（`document.cookie` 覆盖只读接口所需；建议 `context.cookies()` 取全量）
- [x] 用 `curl_cffi` + `impersonate="chrome"` 在浏览器外访问需登录接口（订单列表，200）
- [x] 确认 `a_bogus` / `msToken` / `verifyFp` 非只读接口鉴权必需（三组对照）
- [x] 拉取待发货订单列表（含完整响应结构）
- [x] 识别取号接口与请求体（`/api/order/batchFetchTrackingNos`）
- [x] 识别发货接口与请求体（`/api/order/batchDeliverGoodsByEES`，按运单号发货）
- [x] 探明官方打印组件协议（`wss://localhost:13999`）
- [x] 请求/响应样本落盘（`artifacts/`，不入库）
- [x] 为真实订单取号（2026-11-25，运单号 `79209902836406`）
- [x] 执行真实发货回传（2026-11-25，订单状态转「已发货」）
- [x] 确认 `send_type` 枚举值（电子面单 = `"3"`）
- [x] 确认写接口是否强制签名（已验证的 7 个写接口均不强制）
- [x] 面单作废、取号发货一体、改物流（2026-11-25，测试单）
- [ ] 在出单机验证打印组件（开发机已验证 `getPrinters`；真实热敏打印机待出单机验证）

#### 第一轮补充验证（2026-11-24 完成）

- [x] 发货地址 / 面单模板 / 快递公司 三个基础数据接口的路径、方法与返回结构
- [x] 收货地址解密接口的参数约定与明文返回
- [x] 会话探测接口选型（`tabcnt` 可用，`session_check` 不可用）
- [x] 订单列表分页边界（0-based，pageSize 上限 200）
- [x] 上述接口均验证为**浏览器外免签名**可调（`searchPackageList` 例外，需签名）
- [x] 取号模板参数：传自定义模板 code（`customTempList`，见 [write.md](write.md) A.2.2）
