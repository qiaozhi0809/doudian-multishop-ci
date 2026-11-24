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
| 订单 | `GET /api/orders` | 跨店列表（筛选、排序、分页） |
| | `GET /api/orders/counts` | 跨店 tab 计数 |
| | `GET /api/orders/{id}` | 详情（含商品行、面单历史） |
| | `POST /api/orders/sync` | 立即拉单 |
| | `POST /api/orders/{id}/receiver` | 按需解密单个订单的收件人（用户查看时；不在取号链路，DEC-06；受额度与限速约束，见 [flows.md](flows.md) 7.3） |
| 取号 | `POST /api/labels/preview` · `POST /api/labels/execute` | 两步提交取号（打面单） |
| | `POST /api/labels/fetch-and-ship/preview` · `POST /api/labels/fetch-and-ship/execute` | 两步提交「打单并发货」（一体接口） |
| | `POST /api/labels/void/preview` · `POST /api/labels/void/execute` | 两步提交作废 |
| 打印 | `GET /api/print/status` | 打印组件是否在线 + 打印机列表 |
| | `POST /api/print/jobs` | 提交打印批次 |
| | `GET /api/print/jobs/{id}` | 打印回执 |
| 发货 | `POST /api/shipping/precheck` | 发货前检查（`sendcheck`） |
| | `POST /api/shipping/preview` · `POST /api/shipping/execute` | 两步提交发货 |
| 备注 | `POST /api/remarks/preview` · `POST /api/remarks/execute` | 两步提交批量备注 |
| 任务与事件 | `GET /api/tasks` · `GET /api/tasks/{id}` | 任务列表与进度 |
| | `POST /api/tasks/{id}/retry` · `POST /api/tasks/{id}/cancel` | 重试 / 取消 |
| | `GET /api/events` | SSE 推送 |
| 售后（只读） | `GET /api/aftersale` · `GET /api/aftersale/counts` · `GET /api/aftersale/{id}` | 跨店待办队列、计数、详情 |
| 商品 / 库存（只读） | `GET /api/catalog/products` · `GET /api/catalog/products/counts` · `GET /api/catalog/stock` | 列表、计数、库存概览 |
| 资金（只读） | `GET /api/fund/summary` · `GET /api/fund/unsettled` · `GET /api/fund/margin` | 多店概览、待结算、保证金 |
| 仪表盘（草案，[dashboard.md](dashboard.md)） | `GET /api/dashboard/summary` | KPI 卡片：按日期范围与店铺筛选汇总，附环比 |
| | `GET /api/dashboard/trend?granularity=day\|week\|month` | GMV / 订单量趋势，可按店铺拆分 |
| | `GET /api/dashboard/shops` | 店铺排行（GMV、订单数、客单价、售后率、待发货、超时未发） |
| | `GET /api/dashboard/products` | 商品排行（按销量） |
| | `GET /api/dashboard/heatmap` | 店铺 × 日期出单热力图 |
| 对账 | `POST /api/reconcile/runs` · `GET /api/reconcile/runs` | 触发 / 查看对账批次 |
| | `GET /api/reconcile/findings` · `PATCH /api/reconcile/findings/{id}` | 异常列表、标记已处理 |
| | `GET /api/reconcile/findings/export` | 导出 |
| 系统 | `GET /api/audit` | 审计日志查询 |
| | `GET /api/settings` · `PATCH /api/settings` | 限速、工作时段、演练模式、对账窗口等 |
| | `GET /api/health` | 后端、数据库、打印组件、各店会话的总体健康 |

详细 schema 待补（[gaps.md](../gaps.md) ENG-01）。
