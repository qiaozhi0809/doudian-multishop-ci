# 本地 API

> 前端只调这些接口，不直接访问抖店。两步提交、幂等与重试规则见 [backend.md](backend.md) 5.11 / 5.12。
> 原 `overall-design.md` 第 4 节。索引见 [docs/README.md](../README.md)。

**约定**：

- 前缀 `/api`，JSON；金额字段统一以 `_cents` 结尾；时间为 ISO-8601 字符串。
- 分页：本地 API 统一 `page`（从 1 开始）+ `page_size`；抖店各接口的 0/1 基准差异只在 adapter 里处理，不外泄。
- 多店查询用 `shop_ids` 参数（逗号分隔，省略 = 全部启用店铺）。
- 错误统一结构：`{ "error": { "type": "BizRejected", "message": "...", "shop_id": 1, "detail": {...} } }`。
- 跨店聚合结果每店附 `source: upstream | local_db` 与失败原因，单店失败不让整个请求失败。
- **鉴权**：除 `/api/health` 与下表「登录」分组的前三个接口外，都需要管理员会话 Cookie `dd_admin`，否则 401（[backend.md](backend.md) 5.16）。

| 分组 | 方法 + 路径 | 用途 |
|---|---|---|
| 登录 | `GET /api/auth/status` | `{setup_required, logged_in, username}`，前端据此决定进入初始化页、登录页还是后台 |
| | `POST /api/auth/setup {username, password}` | 首次运行创建管理员；已有账号时 409 |
| | `POST /api/auth/login {username, password}` | 成功设置 `dd_admin` Cookie；失败 401，锁定中 423 |
| | `POST /api/auth/logout` | 删除当前会话 |
| | `POST /api/auth/password {old_password, new_password}` | 改密，其他会话失效 |
| 店铺与会话 | `GET /api/shops` | 店铺列表 + 会话健康 |
| | `POST /api/shops` | 新增店铺（随后发起扫码） |
| | `POST /api/shops/{id}/login` | 打开浏览器扫码 / 重登 |
| | `POST /api/shops/{id}/probe` | 立即探测会话 |
| | `POST /api/shops/{id}/sync-base` | 同步地址 / 模板 / 快递 / 面单账户 |
| | `GET /api/shops/{id}/base` | 查看本店基础数据 |
| | `PATCH /api/shops/{id}` | 改名、停用、切换通道、默认打印机 |
| | `PUT /api/shops/{id}/egress {mode: direct\|proxy, proxy_url? \| paste?, expires_at?}` | 设置固定出口；`paste` 为代理商格式 `IP\|端口\|账号\|密码\|到期日`；只接受 `http(s)://`；修改已登录店铺的出口会使其转 `needs_login`（backend 5.17） |
| | `POST /api/shops/{id}/egress/check[?accept_change=true]` | 经该出口检查连通并取出口 IP → `{egress_ip, egress_ip_pending, egress_status}`；`accept_change` 用于人工确认 IP 变化 |
| | `POST /api/shops/{id}/resume` | 解除风控暂停（`paused_reason` 置空） |
| 订单 | `GET /api/orders` | 跨店列表（筛选、排序、分页） |
| | `GET /api/orders/counts` | 跨店 tab 计数 |
| | `GET /api/orders/{id}` | 详情（含商品行、面单历史） |
| | `POST /api/orders/sync` | 立即拉单 |
| | `POST /api/orders/{id}/receiver` | 按需解密单个订单的收件人，结果只返回给前端、不入库（用户查看时；不在取号链路，DEC-06；受额度与限速约束，见 [flows.md](flows.md) 7.3）。冷却中返回 429 `DecryptCooldown` |
| 取号 | `GET /api/labels/pool?shop_ids=&stage=pending\|labeled&page=&page_size=` | 打单发货订单池（本地库）：每单附 `blocked_reason` 与当前有效面单；`pending` = `synced` / `pending_label`，`labeled` = `label_obtained` / `printed` |
| | `POST /api/labels/preview` · `POST /api/labels/execute` | 两步提交取号（打面单）；预览响应按店列出 `courier_code` / `template_code` / `ebill_id` / `net_code` / `ready_order_ids`，以及逐单 `blocked` 与整店 `shop_errors` |
| | `POST /api/labels/fetch-and-ship/preview` · `POST /api/labels/fetch-and-ship/execute` | 两步提交「打单并发货」（一体接口） |
| | `POST /api/labels/void/preview` · `POST /api/labels/void/execute` | 两步提交作废；预览列出待作废面单 |
| 打印 | `GET /api/print/status` | 打印组件探测（`getPrinters`，2 秒超时）+ 打印机列表；组件未启动时前端打印按钮置灰 |
| | `POST /api/print/jobs {waybill_ids, printer_name?}` | 提交打印批次（202）；每张面单一条 `print_job`；无打印数据的面单转手动补打提示 |
| | `GET /api/print/jobs/{id}` | 单条打印回执：`queued` / `success` / `failed` + `result_code` / 尝试次数 / 回执详情 |
| | `GET /api/print/waybills?waybill_ids=1,2` | 面单可打印信息（`has_print_data`）与最近一次打印任务（打单发货页状态显示） |
| 发货 | `GET /api/shipping/pool?shop_ids=&page=&page_size=` | 待发货订单池：`label_obtained` / `printed` 且有有效面单的订单（本地库）。前端已改用打单发货页「待发货」阶段（`/api/labels/pool?stage=labeled`），本接口保留 |
| | `POST /api/shipping/check {order_ids}` | 发货前检查（`sendcheck`）：按店返回 `total` / `double_check_num` / `double_check_detail` / `place_holder`，以及不可发货的 `blocked` 与整店 `shop_errors` |
| | `POST /api/shipping/ship {order_ids, double_check_ack?}` | 提交发货（202）：提交前重新检查；有二次确认项但未确认时 422；逐店按运单号调用 `batchDeliverGoodsByEES`，幂等键 `ship:{shop_id}:{courier_code}:{tracking_no}` |
| | `GET /api/shipping/batches/{batch_id}` | 批次逐单结果（`pending` / `success` / `failed` + `fail_msg`） |
| 备注 | `POST /api/remarks/preview` · `POST /api/remarks/execute` | 两步提交批量备注 |
| 任务与事件 | `GET /api/tasks` · `GET /api/tasks/{id}` | 任务列表与进度 |
| | `POST /api/tasks/{id}/retry` · `POST /api/tasks/{id}/cancel` | 重试 / 取消 |
| | `GET /api/events` | SSE 推送 |
| 售后（只读） | `GET /api/aftersale` · `GET /api/aftersale/todo` · `GET /api/aftersale/counts` · `GET /api/aftersale/statuses` · `GET /api/aftersale/{after_sale_id}?shop_id=` · `POST /api/aftersale/sync` | 快照列表 / 待办队列（按处理截止时间）、平台计数、状态筛选项、按需详情、同步 |
| 商品 / 库存（只读） | `GET /api/catalog/products` · `GET /api/catalog/products/counts` · `GET /api/catalog/products/groups` · `GET /api/catalog/stock` · `GET /api/catalog/stock/summary` · `GET /api/catalog/stock/warehouses` · `POST /api/catalog/products/sync` · `POST /api/catalog/stock/sync` | 商品快照、状态计数、分组、库存快照、本地预警汇总、仓库列表、同步 |
| 资金（只读） | `GET /api/fund/summary` · `GET /api/fund/unsettled` · `GET /api/fund/margin` · `GET /api/fund/bills?days=&page=` · `POST /api/fund/sync` | 多店概览、待结算快照、保证金、近 N 天账单（上游、不落库）、同步 |
| 仪表盘（草案，[dashboard.md](dashboard.md)） | `GET /api/dashboard/summary` | KPI 卡片：按日期范围与店铺筛选汇总，附环比 |
| | `GET /api/dashboard/trend?granularity=day\|week\|month` | GMV / 订单量趋势，可按店铺拆分 |
| | `GET /api/dashboard/shops` | 店铺排行（GMV、订单数、客单价、售后率、待发货、超时未发） |
| | `GET /api/dashboard/products` | 商品排行（按销量） |
| | `GET /api/dashboard/heatmap` | 店铺 × 日期出单热力图 |
| 对账 | `POST /api/reconcile/run {window_days?}` | 手动触发（202）：`searchlist tab=all` 拉全状态订单，窗口默认 30 天（1~90）；单店失败隔离 |
| | `GET /api/reconcile/findings?shop_ids=&run_id=&kind=&status=&page=&page_size=` | 异常列表（默认最近一次批次），附本次批次摘要与三类异常标题 |
| | `PATCH /api/reconcile/findings/{id} {status: open\|handled}` | 标记处理状态 |
| 系统 | `GET /api/audit` | 审计日志查询 |
| | `GET /api/settings` · `PATCH /api/settings` | 限速、工作时段、演练模式、对账窗口等 |
| | `GET /api/health` | 后端、数据库、打印组件、各店会话的总体健康 |

M5 只读聚合的读取口径（实现于 `service/aftersale.py` / `catalog.py` / `fund.py`）：

- 列表接口读**本地快照**（带 `synced_at`），`POST .../sync` 才请求上游并按店落库；上游同步在指定 `shop_ids` 时才做暂停 / 出口 / 会话预检，省略则只跑可用店铺。
- `counts` / `groups` / `warehouses` / `bills` 直接请求上游，逐店返回 `source: upstream | error` 与失败原因，单店失败不影响其他店。
- 账单不落库；金额字段尚未校准（[api/fund.md](../api/fund.md) F.4），命中候选字段时 `amount_status=confirmed`，否则金额记 0 且 `amount_status=pending`，界面标注「待探明」。
- 库存的 `spot_stock_num` 与 `future_stock_num` 分列返回，前端不提供相加。
详细 schema 待补（[gaps.md](../gaps.md) ENG-01）。

**M2 已落地的取号接口细节**（2026-11-25）：

- 预览 10 分钟有效、一次性、按管理员归属（`{ error: { type: "InvalidRequest" } }` 422）；
  预览时 `synced` 且预检通过的订单转 `pending_label`。
- `execute` 返回 202 并在后台逐店串行执行；演练模式返回 409 `DryRunBlocked`；预览类型与执行路径不一致返回 422。
- 进度经 SSE 推送：`label_progress {preview_id, mode, shop_id, order_id, order_no, result: success|failed|verifying|skipped, tracking_no?, reason?}`、
  `label_done {preview_id, mode, ok, failed, verifying, skipped}`。

**M4 已落地的发货 / 对账接口细节**（2026-11-25）：

- `check` 只读（`sendcheck` 允许退避重试），按店串行；单店失败进 `shop_errors`，不影响其他店。
- `ship` 在返回 202 前同步完成所有店的检查；有二次确认项时必须带 `double_check_ack: true`（前端按住确认按钮即代表已核对）。
  检查通过后按「店 + 快递 + 运单号」分包，每店一次 `batchDeliverGoodsByEES`；服务端不阻止重复发货，
  本地以 `tasks.idempotency_key = ship:{shop_id}:{courier_code}:{tracking_no}` 判重，`shipment` 的 success 唯一索引兜底。
  整批瞬时错误退避重试 3 次；仍失败逐包裹标记失败（「结果不明，可重试」），订单状态不动。
- 发货进度经 SSE 推送：`ship_progress {batch_id, shop_id, order_id, order_no, result: success|failed|skipped, tracking_no?, reason?}`、
  `ship_done {batch_id, ok, failed, skipped}`。
- 对账在同一事务内先读旧快照 → 判定三类异常 → 统一 upsert `order_fact`（附录 G.4）；
  首次运行会给已发货订单建立基线并报 `platform_shipped_local_not`（G.6）；
  结束推送 `reconcile_done {run_id, status, scanned, findings, errors}`。
- 对账窗口按 `create_time` / `pay_time` 任一落在窗口内纳入；两类时间都缺的订单不纳入。
- 取号结果不明（超时 / 「不存在可取号商品」）时进入待核实并通过 `getOrderLogistics` 查回；
  任务状态与进度为 `verifying`，订单保持 `pending_label`。
