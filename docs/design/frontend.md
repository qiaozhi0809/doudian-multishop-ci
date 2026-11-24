# 前端设计

> 结构、数据层、表格、危险操作交互、技术栈、页面组件映射、Arc 安装。
> 合并自原 `overall-design.md` 第 3 节与原 `architecture.md` 11.1 / 11.3 / 11.5。索引见 [docs/README.md](../README.md)。
> 分层规则（`logic/` `hooks/` `components/` `index.tsx`）见 [engineering-rules.md](../engineering-rules.md) 2.1。
> 仪表盘的指标与数据来源见 [dashboard.md](dashboard.md)。

### 1. 结构

- **登录**：未初始化时进「创建管理员」页，未登录时进登录页，路由守卫拦截所有后台页面；任一接口返回 401 时回到登录页（[backend.md](backend.md) 5.16）。
- **App Shell**：侧边栏导航 + 顶栏（右上角为当前管理员与退出、修改密码）。顶栏常驻三样：**店铺筛选器**（全局，可多选）、**任务中心**（批量操作进度）、**会话健康指示**（任一店掉线即亮红点，点开可一键重登）。
- **页面**：仪表盘、订单、打单台、发货台、售后、商品、库存、资金、对账、店铺与设置（组件映射见第 6 节）。
- **模块四层**：每个页面按 engineering-rules 2.1 拆 `logic/` `hooks/` `components/` `index.tsx`。

### 2. 数据层

- 服务端状态全部用 TanStack Query；查询 key 统一带上店铺筛选条件，如 `['orders', shopIds, filters]`。
- SSE 事件 → 对应 query key 失效；不手写轮询。
- **类型从后端生成**：用 openapi-typescript（或 orval）读 FastAPI 自动产出的 OpenAPI 描述，生成 `src/lib/api-types.ts`。前后端类型只有一个来源，后端改字段前端编译即报错。

### 3. 表格

订单、商品、库存列表是核心。多店聚合后订单可能上千行，且需要**跨页勾选**后批量取号。
先确认 Arc `sortable-data-table` 是否支持虚拟滚动与受控选择；不支持则底层用 TanStack Table + TanStack Virtual，外观沿用 Arc 样式（放在 `components/custom/`）。

### 4. 危险操作交互

写操作统一用「预览 → 按住确认」组件（`hold-to-confirm`），预览里按店分组列出将发出的请求和影响订单数；演练模式下确认按钮置灰并有明显标识。

### 5. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 框架 | React 19 + TypeScript | |
| 构建 | Vite | 开发 `localhost:5173`，生产构建后由后端托管 |
| 样式 | Tailwind CSS 4 + Arc `foundation.css` | Arc 的设计令牌（`--background` / `--surface` / `--foreground` 等） |
| 组件库 | **Arc Free（122 组件）+ Arc Pro（121 组件）** | 个人组件库 `uiarc-system`，本地已就绪 |
| 区块 | **Arc Pro blocks（130+）** | 直接复用的页面级区块 |
| 模板起点 | **`arc-crm`（Pro，20 个文件）** | 完整 CRM 模板，可作为 app shell 参考 |
| 图表 | Free：`bar-chart` / `line-chart` / `donut-chart` / `sparkline` / `gauge` / `treemap`；Pro：`funnel-chart` / `radar-chart` / `race-bar-chart` | |
| 数据层 | TanStack Query（服务端状态）+ 局部 useState | 不引入 Redux 类重方案 |
| 路由 | React Router | |
| 表格 | `sortable-data-table`（Free）；不满足虚拟滚动 / 跨页勾选时用 TanStack Table + TanStack Virtual | 见第 3 节 |
| 接口类型 | openapi-typescript（或 orval）从后端 OpenAPI 生成 | 见第 2 节 |
| 实时 | 原生 `EventSource`（SSE） | |
| 测试 | Vitest（logic / hooks）+ Playwright（关键流程端到端） | |

### 6. 页面 → Arc 组件映射

| 页面 | Arc 组件 / blocks | 模块依据 |
|---|---|---|
| **App Shell**（侧边栏 + 顶栏） | `workspace-sidebar` 或 `sidebar-rail`（Pro） | — |
| 管理员登录 / 创建管理员 | `login-split`（Pro）/ `sign-in`（Free block） | backend 5.16 |
| 首页仪表盘 | `metrics-dashboard`（Pro）+ `metric-card` + `bar-chart` | 多店经营概览 |
| 订单管理 | `sortable-data-table` + `filter-toolbar` + `pagination` | [附录 C](../api/order-page.md) |
| 打单台 / 发货台 | `sortable-data-table` + `hold-to-confirm`（危险操作确认） | flows 7.3 / 7.5 |
| 售后聚合 | `inbox-triage`（Pro）+ `tabs` + `timeline` | [附录 E](../api/aftersale.md) |
| 商品管理 | `sortable-data-table` + `product-listing`（Pro） | [附录 D](../api/catalog.md) |
| 库存管理 | `sortable-data-table` + `usage-meter` + `range-histogram-slider` | [附录 D](../api/catalog.md) |
| 资金看板 | `billing-overview`（Pro）+ `revenue-explorer`（Pro）+ `wallet-card` | [附录 F](../api/fund.md) |
| 跨店对账 | `sortable-data-table` + `empty-states`（Free block） | [附录 G](../api/reconcile.md) |
| 店铺 / 设置 | `settings-page`（Pro）+ `sortable-data-table`；每店显示出口方式、出口 IP 与出口状态，扫码按钮在出口检查通过前禁用 | backend 5.1 / 5.17 |
| 通知 / 异常 | `notification-center` + `toast-stack` | flows 第 8 节 |

**Arc 使用约定**：Arc 优先于自建；Free 优先于 Pro；同一控件不混用两套库；
Pro 组件API 以源码导出的 TypeScript interface 为准，不猜 props。

### 7. Arc 安装

```bash
# Free 组件
npx shadcn@latest add @uiarc/<id>

# Pro 组件（本地源码可直接复制到 components/arc）
npx shadcn@latest add @uiarc-pro/<id>
```

- 组件库源码在 `C:\Users\Administrator\.claude\skills\uiarc-system\`（`vendor/uiarc`、`vendor/uiarc-pro`）
- 组件目录索引：`references/catalog-free.md`、`references/catalog-pro.md`
- 不要把 uiarc-system 仓库作为运行时 import 路径，安装进项目后从 `components/arc` 引用
- 不改 `vendor/` 源码来适配项目；需要调整时在 `components/custom` 里组合
