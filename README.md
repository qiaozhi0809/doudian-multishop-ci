# 抖店多店铺管理后台

本机运行的抖音小店多店铺管理工具：把订单、售后、商品、库存、资金、对账聚合到同一个界面，
替代「逐个登录每个店后台、重复操作」的日常劳动。

数据与登录态全部留在本机。每家店使用独立浏览器环境与固定独立出口 IP；配置了代理的店铺，请求经代理商的加密隧道转发，代理商看不到内容。

## 文档

| 文档 | 内容 |
|---|---|
| [文档索引](docs/README.md) | 全部文档的目录与章节对照 |
| [总体设计](docs/design/overview.md) | 定位、范围、架构、技术栈、里程碑、验收、风险 |
| [后端](docs/design/backend.md) · [数据模型](docs/design/data-model.md) · [核心流程](docs/design/flows.md) | 模块设计、表结构、取号 / 打印 / 发货 / 对账流程 |
| [前端](docs/design/frontend.md) · [本地 API](docs/design/local-api.md) · [经营仪表盘](docs/design/dashboard.md) | 界面、接口草案、多店经营指标（草案） |
| [抖店接口](docs/api/README.md) | 已验证的只读 / 写接口与各页面字段映射 |
| [工程规范](docs/engineering-rules.md) | 分层结构、命名、文件长度、硬编码、提交守则 |
| [缺口清单](docs/gaps.md) | 待验证接口、文档矛盾、数据模型缺口、待拍板决策（可认领） |

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS 4 + Arc 组件库 |
| 后端 | Python 3.12 + FastAPI + curl_cffi |
| 存储 | SQLite（WAL）+ SQLAlchemy Core + Alembic |
| 打印 | 抖店官方打印组件（本地 WebSocket） |
| 登录 | Playwright + 系统 Edge（首次扫码，之后走协议） |

## 模块范围

**已定义（只读）**
- 订单：列表、筛选、状态计数、按需地址解密
- 售后：列表、详情、状态计数、待办队列
- 商品 / 库存：列表、计数、库存概览
- 资金：待结算、账单、保证金
- 跨店对账：快照比对、三类异常
- 经营仪表盘：多店订单量、销售额、售后率、出单、排行（草案）

**已定义（写操作）**
- 已验证：批量备注、取号、发货前检查、发货、取号并发货、面单作废、改物流

## 状态

**M1（登录 + 基础数据 + 拉单）已完成**：后端 FastAPI 服务（`backend/app`，15 个 service 模块）
与前端后台骨架（`frontend/src`，auth / shop / order 页面）可运行，后端 44 个测试。
M2 起（取号 / 打印 / 发货 / 对账 / 只读聚合）待实现。

主链路抖店接口已用测试单验证，剩余缺口见 [docs/gaps.md](docs/gaps.md)。

## 许可

个人自用项目，不对外提供授权或服务。
