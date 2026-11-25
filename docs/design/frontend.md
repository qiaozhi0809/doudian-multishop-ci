# 前端设计

> 结构、数据层、表格、危险操作交互、技术栈、页面组件映射、Arc 安装。
> 合并自原 `overall-design.md` 第 3 节与原 `architecture.md` 11.1 / 11.3 / 11.5。索引见 [docs/README.md](../README.md)。
> 分层规则（`logic/` `hooks/` `components/` `index.tsx`）见 [engineering-rules.md](../engineering-rules.md) 2.1。
> 仪表盘的指标与数据来源见 [dashboard.md](dashboard.md)。
> **视觉与交互规范见 [ui-guidelines.md](ui-guidelines.md)**（令牌、字体、状态色、数据格式、文案、审查清单）。

### 1. 结构

- **登录**：未初始化时进「创建管理员」页，未登录时进登录页，路由守卫拦截所有后台页面；任一接口返回 401 时回到登录页（[backend.md](backend.md) 5.16）。
- **App Shell**：左侧浮动侧栏（左下角个人中心：主题、修改密码、退出登录）+ 内容区。没有单独的顶栏。**店铺筛选器**（全局，可多选）在侧栏顶部、品牌下方；**任务中心**（批量操作进度）在侧栏底部、个人中心上方；**会话健康指示**（任一店掉线即亮红点，点开可一键重登）在页面标题行右侧。
- **页面**：概览、全部订单、打单发货、售后处理、商品列表、库存、结算与保证金、发货异常、店铺管理（组件映射见第 6 节）。
- **模块四层**：每个页面按 engineering-rules 2.1 拆 `logic/` `hooks/` `components/` `index.tsx`。

### 1.1 导航分组（信息架构）

按**工作流**分组，不按数据对象平铺。侧边栏结构：

```
📊 概览                      /dashboard

📦 订单                       ← 同一条流水线：订单池 → 打单发货 → 售后 → 出问题的
   ├── 全部订单               /orders
   ├── 打单发货               /labeling   （原打单台 + 发货台；/shipping 跳到「待发货」阶段）
   ├── 售后处理               /aftersale
   └── 发货异常               /reconcile  （原「对账」：比的是发货记录，不是钱）

📋 商品
   ├── 商品列表               /catalog
   └── 库存                   /stock

💰 资金
   └── 结算与保证金           /fund

⚙️ 设置
   └── 店铺管理               /shops
```

**打单发货**（2026-11-25 合并）：打单台的「已取号」和发货台筛的是同一批订单（`label_obtained` / `printed`），
拆成两页只是多切一次页面。合并后一页分两个阶段，叫法对齐抖店后台：

| 阶段 | 订单 | 这一阶段的操作 |
|---|---|---|
| 待打单 | `synced` / `pending_label` | 打单（取号）、打单并发货 |
| 待发货 | `label_obtained` / `printed` | 发货（先发货前检查）、打印面单、作废面单 |

**分组理由**：

- 「订单」组三页共用同一个订单数据源与店铺筛选，按操作流程相邻放置（订单池 → 打单发货 → 售后）；售后原来单独一组只有一项，并进来
- 「商品」组共用商品维度，库存的筛选依赖商品
- 「发货异常」（每天比对平台与本地的发货记录：平台未发 / 本地无记录 / 运单不一致）比的是发货，不是钱，放在「订单」组最后
- 「资金」组只有结算与保证金
- 「店铺管理」放底部「设置」组（低频操作）
- 组名用短的名词，组内页面名不和组名重复（「订单」组下是「全部订单」，「商品」组下是「商品列表」）

**导航交互**：

- 分组只显示灰色组名，组内页面常显，不折叠；侧栏固定宽，不收起成图标栏（页面只有十个左右）
- 当前页显示 active 态
- 分组顺序与页面顺序固定，MVP 不做用户自定义排序

**实现**：`nav-items.ts` 拆为 `NAV_SECTIONS`（仪表盘独立入口 + 订单处理 / 售后 / 商品与库存 / 财务四个分组）
与「设置」组 `FOOTER_NAV`。版式照壹帆智播的「桌面工具档」：浮动侧栏 + 左下角个人中心（`components/custom/user-menu`），
主题存 `doudian.theme`（浅色 / 深色 / 跟随系统）。

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
| **App Shell**（浮动侧栏 + 页面标题行） | 自写，照壹帆智播 `Shell.tsx` | — |
| 管理员登录 / 创建管理员 | `card` + `input` + `password-field` + `button` + `alert`（Free）组合的居中表单。不用 `sign-in` / `login-split` 区块：它们只支持邮箱 / SSO 演示流程，没有账号密码提交与错误提示的接口 | backend 5.16 |
| 首页仪表盘 | `metrics-dashboard`（Pro）+ `metric-card` + `bar-chart` | 多店经营概览 |
| 订单管理 | `sortable-data-table` + `filter-toolbar` + `pagination` | [附录 C](../api/order-page.md) |
| 打单发货 | `sortable-data-table` + `hold-to-confirm`（危险操作确认） | flows 7.3 / 7.5 |
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

Arc 官方 registry（`npx shadcn add @uiarc/...`）已停止免费访问、需要授权码，**本项目不走 registry**，
改为从本机的授权源码副本 `uiarc-system` 复制：

| 机器 | 源码位置 |
|---|---|
| macOS 开发机 | `~/Desktop/uiarc-system` |
| Windows | `C:\Users\Administrator\.claude\skills\uiarc-system` |

- 目录：Free `vendor/uiarc/registry/`（`foundation.css`、`motion-tokens.ts`、`components/<id>/`、`blocks/<id>/`）与 `vendor/uiarc/lib/`；Pro 在 `vendor/uiarc-pro/` 下同样结构
- 索引：`references/catalog-free.md`、`catalog-pro.md`；Free 选型说明 `vendor/uiarc/skills/arc/components.md`；Pro 以源码导出的 TypeScript interface 为准
- 只复制用到的条目到 `frontend/src/components/arc/`，保持相对 import 可解析；在 `components/arc/SOURCE.md` 记录来源版本与复制清单
- 不把 uiarc-system 作为运行时 import 路径；不改复制进来的源码，调整写在 `components/custom/`
