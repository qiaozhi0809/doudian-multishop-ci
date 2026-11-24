# 工程规范（抖店多店铺管理）

> 这是一份**强制规范**，目标由 CI 守门。违反规则的提交会被拒绝。
> 改规则 = 改 CI + 改本文，二者同步。
> 适用范围：`backend/`（Python）与 `frontend/`（TypeScript）。
> 文档类（`docs/`、`case/`）只遵守长度与结构规则。

---

## 一、最高准则

**原子化解耦**：每个文件只做一件事，每个模块只对一类外部承诺。
**禁止累积**：上线 = 主分支跑过 CI；不解耦的代码不进主分支。

本项目的「一类外部承诺」特指：

| 模块 | 对外承诺 |
|---|---|
| `adapter/doudian` | 抖店 HTTP 协议（含签名、错误码、分页基准） |
| `adapter/print` | 官方打印组件 WebSocket |
| `adapter/browser` | Playwright 扫码登录与兜底 fetch |
| `store/*` | SQLite 表结构与 CRUD |
| `domain/order` | 订单状态机与状态枚举 |
| `domain/aftersale` | 售后状态与待办判定 |
| `domain/money` | 金额换算（一律整数分） |

---

## 二、目录与分层

### 2.1 前端（`frontend/src/`）

技术栈：React 19 + TypeScript + Vite + Tailwind 4 + Arc 组件库。

每个 page / feature 模块下严格四层：

```
<module>/
  logic/        ← 纯函数，无 React，无 fetch，无 storage
  hooks/        ← useState/useEffect/useMemo，调 logic 和 adapters，无 JSX
  components/   ← 纯展示组件，receive props / emit events，无业务调用
  index.tsx     ← 装配层：只负责 hooks() + render(<Component {...props} />)
```

**禁令**：
- `logic/*.ts` 内禁止 `import 'react'`
- `hooks/*.ts` 内禁止 return JSX
- `components/*.tsx` 内禁止 `useEffect` 里调 `fetch` / 禁止直接调 service
- `index.tsx` 不超过 60 行（仅做装配）

**Arc 组件的落位**（与四层不冲突）：

```
src/components/
  ui/        ← shadcn 基础件
  arc/       ← Arc Free / Pro 源码（安装进来，不从 uiarc-system 运行时 import）
  custom/    ← 项目组合层：跨模块拼装写这里
```

Arc 组件视为 `components/` 层的「纯展示件」；业务数据只能由 `hooks/` 注入。

### 2.2 后端（`backend/app/`）

```
backend/app/
  api/          ← FastAPI route：pydantic schema（I/O contract）+ 调 service
  service/      ← 业务编排：事务、状态机、调 adapter / store
  adapter/      ← 外部世界的薄封装，无业务逻辑
    doudian/    ← 抖店 HTTP 客户端（FxgClient）、签名、接口常量、错误码
    print/      ← 打印组件 WebSocket
    browser/    ← Playwright 登录与兜底渠道
  store/        ← SQLite 数据访问，表/键 CRUD
  domain/       ← 纯业务模型 + 纯函数，不依赖框架、无 IO
  shared/       ← 跨模块工具，必须配单测 <name>_test.py
```

与设计文档的映射（设计文档里的旧名 → 本规范的落位）：

| 设计文档 | 本规范 |
|---|---|
| `channels/protocol.py` | `adapter/doudian/client.py` |
| `channels/browser.py` | `adapter/browser/channel.py` |
| `signing/` | `adapter/doudian/signing/` |
| `services/order_sync.py` | `service/order_sync.py` |
| `services/reconcile.py` | `service/reconcile.py` |
| `db/` | `store/` |

**禁令**：
- `domain/` 内禁止 `import fastapi` / `import sqlalchemy` / `import curl_cffi` / 任何 IO
- `api/` 内禁止直接 SQL，必须经 service
- `adapter/` 不写业务判断（不做「这单该不该发货」这类决策），只翻译外部世界
- `store/` 内禁止业务判断（不能写 `if order.status == 'stock_up':`）

---

## 三、文件长度上限

### 3.1 角色目标线（review 判断）

| 角色 | 目标线 | 说明 |
|---|---|---|
| `index.tsx`（装配层） | 60-80 行 | 超过通常说明混入业务 |
| 薄 API handler / adapter / hook / 小组件 | 80-120 行 | 超过应拆 schema / serializer |
| service 编排 | 150-250 行 | 超过应拆 query / write / strategy |
| store / domain 枚举 / 接口常量表 | 200-400 行 | 声明式文件可更长，按域拆 |
| 测试文件 | 250-400 行 | 按行为拆 |
| 文档（`docs/`、`case/`） | 400-600 行 | 长文档按章节或附录拆 |

### 3.2 CI 硬上限

| 类型 | 硬上限 |
|---|---|
| `index.tsx`（装配层） | 80 行 |
| `*.ts` / `*.tsx` | 300 行 |
| `*.py` | 400 行 |
| `*.md` | 600 行 |

超限处理：拆。把「做不止一件事」的部分提到 logic / hook / component / service 子文件。
若只是类型定义、声明式常量表或测试样例天然较长，不要强拆成不可发现的小文件。

### 3.3 当前已知偏离（待处理）

| 文件 | 行数 | 处理 |
|---|---|---|
| `docs/architecture.md` | ~2100 | 超出 600 行硬上限 → 按附录拆成多文件（A~G 各自独立） |

新增文档一律从第一天就按 600 行规划；存量文档拆分为独立任务，不阻塞功能开发。

---

## 四、命名与发现性

- 文件名：前端 `kebab-case`（`order-status.ts`）；后端 `snake_case`（`order_status.py`）
- 模块名：单数（`order/`，不是 `orders/`），集合型目录除外（`constants/`、`enums/`）
- 禁止 `utils.ts` / `helpers.py` / `common.ts` 等垃圾桶名 → 按 domain 命名
  （`money-format.ts`、`time-bj.py`、`order-status.ts`）

---

## 五、硬编码规则

**原则**：字面量必须有定义源，业务代码只引用定义源。

允许直接写字面量的位置：
- 类型定义：`Enum` / `StrEnum` / `Literal` / pydantic schema
- 常量模块：按 domain 命名，如 `domain/order_status.py`、`adapter/doudian/bid.py`
- registry / catalog 声明：业务配置的唯一来源
- 配置 schema：环境变量名、外部 key 的集中定义
- 测试：可以写 literal 表达样例与边界

### 5.1 本项目必须进常量模块的字面量

| 类别 | 例子 | 定义源 |
|---|---|---|
| 订单状态（数字） | `3=已发货`、`4=已关闭`、`5=已完成` | `domain/order_status.py` |
| 订单状态（筛选字符串） | `"unpaid"`、`"stock_up"`、`"on_delivery"`、`"received"`、`"closed"` | `domain/order_status.py`（独立枚举，勿与数字混用） |
| 售后状态 | `after_sale_status` 数字、`status_deadline=0` 表已完结 | `domain/aftersale_status.py` |
| 业务域 `_bid` | `"ffa_order"`、`"ffa_goods"`、`"ffa_aftersale"` | `adapter/doudian/bid.py` |
| 接口路径 | `/api/order/searchlist`、`/bill_center/domestic/shop/query_item` | `adapter/doudian/endpoints.py` |
| 分页基准 | `searchlist` 0-based、`after_sale/pc/list` 1-based | `adapter/doudian/endpoints.py`（随路径声明） |
| 错误码 | `10008` 未登录、`100000` 成功（字符串） | `adapter/doudian/error_codes.py` |
| 查询类型 | `"CHARGE_BILL_ITEM"`、`"SHOP_UNSETTLED_ORDER"` | `adapter/doudian/enums.py` |
| 打印端口 | `13999`（WSS）、`13888`（HTTP） | `adapter/print/ports.py` |

### 5.2 生产代码禁止散落

- 渠道/平台标识、`_bid` 值、环境 key、错误码、接口路径
- 金额单位换算系数（100）→ `domain/money.py`
- 结算延迟天数（21）→ 从平台返回的 `settle_period_detail` 读取，不写死

正确做法：公共流程查枚举/常量；字符串解析集中在 adapter 边界，解析后传 typed value；
新增字面量先建定义源，再在业务代码引用。

---

## 六、公共工具规范

公共工具 = 被 ≥ 2 个调用方使用的工具。

**写之前问**：
1. 真的 ≥ 2 个调用方？只有 1 个 → 留在调用方私有目录
2. 是无副作用纯函数？有副作用 → 放 adapter 不放 lib
3. 写得了单测吗？写不了 → 设计有问题，不进公共

**写之后**：同一文件 = 同一 domain；一个文件超 200 行 → 必拆子文件。

---

## 七、依赖方向（不允许反向）

```
前端：components → hooks → logic → lib
       index.tsx ─┘            ↑
       adapters ──────────────┘

后端：api → service → adapter / store / domain
             └────── store / domain
```

禁止反向：`logic` 调 `hooks`、`domain` 调 `service`、`store` 调 `service`。
CI 扫 import 图。

---

## 八、抖店业务专项规则

这一节是本项目特有的，优先级等同于上述所有规则。

### 8.1 会话与凭证

- cookie **只存本机**：`cookies/` 目录不入库、不提交、不进日志
- 导出会话必须用浏览器 `context.cookies()` 取全量（含 HttpOnly），
  禁止只用 `document.cookie`（会缺 `sessionid` / `sid_tt` / `sid_guard`）
- 日志中出现的 cookie、手机号、收货地址一律脱敏
- 会话失效（`code=10008`）必须走统一的 `SessionExpired` 异常，不允许各处自己判断

### 8.2 多店并发

- **同店请求绝不并发**：每店一条串行队列
- 全局并发上限默认 3 个店，可配置
- 请求间隔 300~1200ms 随机
- 单店失败隔离：一店会话失效不得阻塞其他店

### 8.3 写操作

- 写接口（取号 / 发货 / 售后处理 / 商品创建 / 库存修改）必须：
  1. 人工二次确认（界面 `hold-to-confirm` 或等价交互）
  2. 幂等键去重（`idempotency_key`）
  3. 完整记录请求/响应到审计日志
- 签名要求**逐接口声明**，在 `adapter/doudian/endpoints.py` 标注：
  - 已验证免签名（批量备注 / 取号 / sendcheck / 发货）→ 协议直连
  - 未验证的 → 走 `adapter/browser` 兜底渠道，不得假设免签名
- 演练模式（dry-run）下禁止发出任何写请求

### 8.4 数据口径

- **金额**：一律整数分（`*_cents`），禁止浮点；展示层再除 100
- **时间**：平台接口多为 unix 秒；本地存储用 ISO 字符串；转换集中在 `shared/time-bj.py`
- **两套状态枚举不得混用**：
  - 筛选参数 = 字符串（`"stock_up"`）
  - 数据字段 `order_status` = 数字（`3`）
  - 各自独立建模，禁止互相转换猜测

### 8.5 接口适配

- 所有接口路径、参数名、分页基准集中在 `adapter/doudian/endpoints.py`
- 分页基准随接口声明（`page_base: 0 | 1`），禁止全局假设
- 响应成功码不统一（`0`、`"100000"`）→ 统一在客户端层归一化
- 新增接口前必须在文档（`docs/` 附录）记录实测结果，再写代码

---

## 九、提交守则

- 一次 commit 一件事；多任务拆多 commit
- 不许「顺手改」无关文件
- commit message 用 Conventional Commits（`feat(scope): ...` / `fix(scope): ...`）
- 主分支保持绿；CI 红的 PR 不许合
- 涉及接口行为的改动，必须同步更新 `docs/` 对应附录

---

## 十、CI 守门项（与本文一一对应）

| 规则 | 守门脚本 | 状态 |
|---|---|---|
| 文件长度上限 | `scripts/ci/check-file-length.sh` | 待建 |
| 前端分层（logic 禁 react） | `scripts/ci/check-frontend-layers.sh` | 待建 |
| 后端分层（domain 禁框架） | `scripts/ci/check-backend-layers.sh` | 待建 |
| 垃圾桶命名 | `scripts/ci/check-naming.sh` | 待建 |
| commit message 格式 | `scripts/ci/check-commit-msg.sh` | 待建 |
| 文档结构 | `scripts/ci/check-docs-structure.sh` | 待建 |
| 敏感信息（cookie/密钥） | `scripts/ci/check-secrets.sh` | 待建 |

> 项目当前处于设计阶段，CI 脚本尚未建立。落地顺序：
> `check-file-length` → `check-secrets` → 后端分层 → 前端分层 → 命名 → commit message。

---

## 十一、违规处理

- pre-commit hook 拦截 → 修了再 commit
- CI 失败 → PR 不许合
- 想破例 → 写一条 ADR `docs/50-decisions/NNNN-*.md` 说明并修改 CI 白名单
