# 文档索引

> 2026-11-25 整理：原 `architecture.md`（2600+ 行）与 `overall-design.md` 合并、去重后拆分为下列文件，每个文件不超过 600 行（engineering-rules 3.2）。
> 正文章节号沿用原 `architecture.md`，所以文档里写的「5.5」「7.3」「附录 E」仍然有效，按下表找文件即可。

## 设计（`design/`）

| 文件 | 内容 |
|---|---|
| [overview.md](design/overview.md) | 定位、背景与目标、范围与路线图、假设、总体架构与运行形态、技术栈与目录、测试、里程碑、验收、风险、能力分级、术语 |
| [backend.md](design/backend.md) | 分层与模块、会话、抖店适配层与通道降级、签名、订单同步、取号与超时恢复、发货、调度、对账、基础数据、只读聚合、两步提交与幂等、逐操作重试、存储、日志、SSE |
| [data-model.md](design/data-model.md) | 订单状态机、表结构、关键约束、会话存储与迁移 |
| [flows.md](design/flows.md) | 登录与公共参数、拉单、取号（含地址解密额度）、打印、发货、对账、错误码、风控、打印方案 |
| [frontend.md](design/frontend.md) | 前端结构、数据层、表格、危险操作、技术栈、页面 → Arc 组件、Arc 安装 |
| [local-api.md](design/local-api.md) | 前端调用的本地 API 草案 |
| [dashboard.md](design/dashboard.md) | 经营仪表盘（多店订单量 / 销售额 / 售后率 / 出单 / 排行）——草案 |

## 抖店接口（`api/`）

| 文件 | 内容 |
|---|---|
| [README.md](api/README.md) | A.0 验证总览、签名判断、A.3 页面路径、A.4 关键结论、A.5 M0 验证清单 |
| [read.md](api/read.md) | A.1 只读接口 |
| [write.md](api/write.md) | A.2 写接口（A.2.1 ~ A.2.8） |
| [order-page.md](api/order-page.md) | 附录 C 订单管理页 |
| [catalog.md](api/catalog.md) | 附录 D 商品 / 库存 |
| [aftersale.md](api/aftersale.md) | 附录 E 售后 |
| [fund.md](api/fund.md) | 附录 F 资金 |
| [reconcile.md](api/reconcile.md) | 附录 G 跨店对账逻辑 |

## 实施计划（`superpowers/plans/`）

| 文件 | 内容 |
|---|---|
| [2026-11-25-roadmap.md](superpowers/plans/2026-11-25-roadmap.md) | 总路线图：M1 ~ M7 范围、阻塞缺口、完成标准、分工 |
| [2026-11-25-m1-backend.md](superpowers/plans/2026-11-25-m1-backend.md) | M1 后端任务级计划（14 个任务，TDD，含管理员登录与每店固定出口） |
| [2026-11-25-m1-frontend.md](superpowers/plans/2026-11-25-m1-frontend.md) | M1 前端任务级计划（6 个任务，含登录页与路由守卫） |

## 其他

| 文件 | 内容 |
|---|---|
| [engineering-rules.md](engineering-rules.md) | 工程规范（分层、命名、文件长度、硬编码、抖店专项规则、提交守则） |
| [gaps.md](gaps.md) | 缺口清单：待验证接口、数据模型、工程细化、待拍板决策（可认领） |

## 章节对照

| 原位置 | 现位置 |
|---|---|
| `architecture.md` 第 0 ~ 4 节、第 11 ~ 15 节、附录 B、术语表 | [design/overview.md](design/overview.md)（第 11.1 / 11.3 前端部分移至 frontend.md） |
| `architecture.md` 第 5 节 | [design/backend.md](design/backend.md) |
| `architecture.md` 第 6 节 | [design/data-model.md](design/data-model.md) |
| `architecture.md` 第 7 ~ 10 节 | [design/flows.md](design/flows.md) |
| `architecture.md` 第 16 节 | [api/README.md](api/README.md) A.5 |
| `architecture.md` 附录 A.0 / A.3 / A.4 | [api/README.md](api/README.md) |
| `architecture.md` 附录 A.1 / A.2 | [api/read.md](api/read.md) / [api/write.md](api/write.md) |
| `architecture.md` 附录 C ~ G | `api/` 下同名附录文件 |
| `overall-design.md` 第 1 节 运行形态 | overview.md 4.1 |
| `overall-design.md` 2.1 / 2.2 / 2.3 / 2.4 | backend.md 5.0 / 5.2 / 5.1 / 5.7 |
| `overall-design.md` 2.5 两步提交 | backend.md 5.11 |
| `overall-design.md` 2.6 打印路径 | flows.md 第 10 节 |
| `overall-design.md` 2.7 / 2.8 / 2.9 | backend.md 5.13 / 5.14 / 5.15 |
| `overall-design.md` 第 3 节 | frontend.md |
| `overall-design.md` 第 4 节 | local-api.md |
| `overall-design.md` 第 5 节 | overview.md 第 11 节、frontend.md 第 5 节 |
| `overall-design.md` 第 6 节 | overview.md 13.1 |
