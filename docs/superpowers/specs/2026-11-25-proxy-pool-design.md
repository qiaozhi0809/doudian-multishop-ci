# 代理池（Proxy Pool）设计

**Goal:** 在「设置」下新增代理池页面，支持批量导入代理商给出的多条代理；添加店铺时可直接从池中选取可用代理一并完成出口配置，避免每次手工复制粘贴。

**Scope:** 新增 `proxy_pool` 表与迁移 `0008`、代理池的 store / service / api 三层、前端 `pages/proxy-pool/` 页面，以及添加店铺与出口对话框的接入。不改动现有的出口检查、IP 判重、会话登录流程。

## 0. 边界声明：这**不是**轮换代理池

工程规范 [engineering-rules.md](../../engineering-rules.md) 8.2、[backend.md](../../design/backend.md) 5.17、[gaps.md](../../gaps.md) DEC-11 三处明确：

> 每店固定独立出口；**禁止使用轮换代理池**；**禁止伪造设备指纹**。

本设计中的「代理池」只是**配置来源**：池是候选清单，每家店铺仍然绑定**一个**固定代理，绑定后不会自动切换。池的引入不改变以下既有约束：

- 一个池项同一时间只能绑一家店；
- 两家启用店铺的出口 IP 必须不同；
- 出口异常时暂停该店，**绝不回退直连**；
- 最多一家店可以使用 `direct`。

后续若有人想基于此表实现「一店多代理自动轮换」，那是**违反既有决策**的新需求，必须重新走决策流程。

## 1. 数据模型

### 1.1 新表 `proxy_pool`

```sql
CREATE TABLE proxy_pool (
  id              INTEGER PRIMARY KEY,
  identity        TEXT NOT NULL UNIQUE,  -- sha256(明文 URL)，导入去重
  proxy_url       BLOB NOT NULL,         -- SecretBox 密文
  proxy_display   TEXT NOT NULL,         -- host:port，界面与日志只显示这个
  expires_at      TEXT,                  -- YYYY-MM-DD，可空表示不限
  last_checked_at TEXT,                  -- 上次手动检测时间
  last_check_ip   TEXT,                  -- 上次检测到的出口 IP，失败为 NULL
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
```

`identity` 存明文 URL 的 SHA-256 而非明文本身：既能 O(1) 去重，又不把代理凭证以可还原形式写进索引。

### 1.2 `shop` 表变化

- **新增** `proxy_pool_id INTEGER`
- **新增部分唯一索引**：

  ```sql
  CREATE UNIQUE INDEX idx_shop_pool
    ON shop(proxy_pool_id) WHERE proxy_pool_id IS NOT NULL;
  ```

  在数据库层面保证「一个池项只能绑一家店」。
- **删除** `proxy_url` / `proxy_display` / `proxy_expires_at` 三列（单一口径：代理信息只存在池里）

### 1.3 上层零改动的关键手法

`shop_store.get()` / `shop_store.list()` 改为 `LEFT JOIN proxy_pool`，把池的 `proxy_url`、`proxy_display`、`proxy_expires_at` **以同名列**取出：

```sql
SELECT s.*,
       p.proxy_url  AS proxy_url,
       p.proxy_display AS proxy_display,
       p.expires_at AS proxy_expires_at
FROM shop s LEFT JOIN proxy_pool p ON p.id = s.proxy_pool_id
```

因此 `EgressService`（`proxy_for` / `_require_usable` / `check`）、`ShopAdminService._view`、`ShopRow` schema **全部不需要改动**——它们读到的仍是这些键，只是来源变成池。

`proxy_url` 在 JOIN 结果中仍是密文，解密仍然只在 `EgressService.proxy_for` 这一处发生。

### 1.4 迁移 `0008`

顺序：

1. 建 `proxy_pool` 表与 `identity` 唯一索引；
2. `shop` 加列 `proxy_pool_id`；
3. 数据搬迁：对 `shop.proxy_url IS NOT NULL` 的每一行，插入池项（`identity` 按明文算），回填 `shop.proxy_pool_id`；
4. 删除 `shop.proxy_url` / `proxy_display` / `proxy_expires_at`；
5. 建 `idx_shop_pool` 部分唯一索引。

现有库只有一家直连店铺（`proxy_url IS NULL`），第 3 步实际是空操作，但代码必须写并测试。SQLite 3.46 支持 `DROP COLUMN`。

与既有迁移一致：`downgrade()` 抛 `NotImplementedError`。

## 2. 后端

### 2.1 模块划分

| 文件 | 职责 |
|---|---|
| `store/proxy_pool_store.py` | 池表 CRUD + `list_with_usage()`（LEFT JOIN shop 取占用店铺）；无业务判断，不碰加密 |
| `service/proxy_pool.py` | 导入解析、去重、检测、编辑后重置已绑定店铺 |
| `api/proxy_pool.py` | 5 个路由 |
| `api/proxy_pool_schemas.py` | 请求/响应 schema |

### 2.2 接口

```
GET    /api/proxy-pool                 池列表（每项带占用店铺）
POST   /api/proxy-pool/import          批量导入 { "text": "多行" }
PATCH  /api/proxy-pool/{id}            改密码 / 主机 / 端口 / 到期日
DELETE /api/proxy-pool/{id}            被占用时 409
POST   /api/proxy-pool/{id}/check      手动检测，经该代理取出口 IP
```

`GET` 返回项：

```json
{
  "id": 1,
  "proxy_display": "1.2.3.4:8080",
  "expires_at": "2026-12-31",
  "expiry_state": "ok",
  "in_use_by": { "shop_id": 3, "shop_name": "店A" },
  "last_checked_at": "2026-11-25T15:40:00Z",
  "last_check_ip": "116.116.168.60"
}
```

### 2.3 `set_egress` 的三个入口

对外仍是同一个 `PUT /api/shops/{id}/egress`，`EgressRequest` 扩展为：

```python
class EgressRequest(BaseModel):
    mode: Literal["direct", "proxy"]
    pool_id: int | None = None
    proxy_url: str | None = None
    paste: str | None = None
    expires_at: str | None = None
```

| 模式 | 行为 |
|---|---|
| `direct` | 清 `proxy_pool_id`；沿用 `_ensure_no_other_direct` |
| `proxy` + `pool_id` | 校验池项存在、未过期、未被别店占用，然后绑定 |
| `proxy` + `paste` / `proxy_url` | **先 upsert 进池**（按 `identity` 去重）**再绑定**——「快捷新增并绑定」 |

三条路径最终都写 `shop.proxy_pool_id`。原有「清空已确认 IP、状态复位 `unchecked`、已登录店铺转 `needs_login`」逻辑不变。

### 2.4 加店铺时一并配出口

`POST /api/shops` 增加可选字段：

```python
class ShopCreate(BaseModel):
    name: str
    entity: str | None = None
    shop_no: str | None = None
    egress: EgressRequest | None = None
```

`ShopAdminService.create_with_egress()` 在**同一个事务**内完成建店与绑定，避免出现「店建好了但出口没配上」的半成品。

为此 `EgressService` 内部把「校验池项 + 写 `proxy_pool_id` + 清 IP / 转 `needs_login`」抽成接收 `conn` 的私有方法 `_bind_egress(conn, shop, request, now)`；`set_egress()` 退化成「开事务 → 调它 → 提交 → 发事件」的外壳，`create_with_egress` 则用自己那个事务的 conn 调同一个方法。事件发布统一放在事务提交之后。

### 2.5 依赖方向

```
api/proxy_pool → service/proxy_pool → store/proxy_pool_store
                                   ↘ service/egress（重置已绑定店铺）

service/egress → store/proxy_pool_store（只查，不依赖 ProxyPoolService）
```

`EgressService` 需要读池项时直接走 **store**，不调用 `ProxyPoolService`；反向 `ProxyPoolService` 依赖 `EgressService` 是单向的，故不成环。「换出口导致店铺转 `needs_login`」的状态机只保留在 `EgressService` 一处。

### 2.6 检测

现有 `make_fetch_ip` 把一切失败都压成 `None`，区分不出「超时」还是「代理不通」。检测要给出原因，所以在 `service/egress_probe.py` **新增**一个更细的入口，并让旧函数复用它：

```python
@dataclass(frozen=True)
class ProbeResult:
    ip: str | None
    reason: str | None   # None | "timeout" | "proxy_unavailable" | "bad_echo" | "network"

async def probe_egress(proxy: str | None, echo_url: str) -> ProbeResult: ...

async def make_fetch_ip(echo_url: str, ...) -> FetchIp:
    async def fetch_ip(proxy): return (await probe_egress(proxy, echo_url)).ip
    return fetch_ip
```

`make_fetch_ip` 的返回值契约不变，现有 `EgressService` 一条线都不受影响。

`ProxyPoolService.check(id)`：

1. 从 store 取池项 → `SecretBox` 解密；
2. 调注入的 `probe(proxy_url)`；
3. 成功：写 `last_checked_at` / `last_check_ip`，返回 IP 与耗时；
4. 失败：只写 `last_checked_at`，`last_check_ip` 置 NULL，返回 `reason`。

`reason` 到界面文案的映射放在前端 `logic/`，后端只回传机器可读的枚举值。

检测是只读操作，**不改店铺任何状态**。`probe` 通过 `Overrides` 注入，测试用 `FakeTransport`。

## 3. 前端

### 3.1 新页面 `pages/proxy-pool/`

严格四层（engineering-rules 2.1）：

```
logic/pool-form.ts          导入文本 → 行数 / 有效行 / 错误行（纯函数）
hooks/use-proxy-pool.ts     列表、导入、编辑、删除、检测
components/pool-table.tsx   表格：代理 / 到期日 / 状态 / 上次检测 / 操作
components/import-dialog.tsx
index.tsx                   装配（≤ 80 行）
```

表格「状态」直接反映绑定关系：`空闲` / `已用于「测试店」` / `已过期`（过期且被占用要更醒目）。

### 3.2 导航

`FOOTER_NAV` 增加 `{ path: "/proxy-pool", label: "代理池" }`；`NavIcon` 增加 `proxy`；`side-nav.tsx` 的 `ICONS` 映射到 lucide 的 `Network`。

### 3.3 添加店铺对话框

在现有三个输入框下增加「出口」区：

```
出口   ( ) 直连    (•) 代理
       [ 下拉：1.2.3.4:8080 · 到期 12-31   ▾ ]
       + 新增代理
```

- 下拉只列「未占用 + 未过期」的池项；空池时提示「池里没有可用代理」；
- 「+ 新增代理」展开一行粘贴框，格式与现有 `IP|端口|账号|密码|到期日` 一致；
- 已存在直连店时「直连」置灰并说明原因。

前端的置灰只是提前告知，**正确性仍由后端保证**。

### 3.4 现有出口对话框

`logic/egress-form.ts` 的 `entry` 从 `"paste" | "fields"` 扩为 `"pool" | "paste" | "fields"`，默认 `pool`；`buildEgressRequest` 增加 `entry="pool"` 分支返回 `{ mode: "proxy", pool_id }`。`paste` / `fields` 两个入口保持原样。

## 4. 一致性与错误处理

### 4.1 规则与保证方式

| 规则 | 保证方式 |
|---|---|
| 一个池项只能绑一家店 | `idx_shop_pool` 部分唯一索引；冲突映射 409 |
| 同一代理不重复入池 | 导入时按 `identity` 去重，重复行计入 `skipped` |
| 两家店不能用同一出口 IP | **池层查不出来**，沿用 `judge_egress` 的 `duplicate` 判定，由出口检查暴露 |
| 最多一家直连 | 沿用 `_ensure_no_other_direct` + 索引兜底 |

### 4.2 过期语义

复用 `expiry_state` 的 `ok / expiring / expired`：

- 池中过期项在下拉里不出现，表格标红；
- 已绑定店铺走 `_require_usable`，抛「代理已到期，请续费或更换」（与现状一致）。

### 4.3 编辑池项的连锁反应

| 改什么 | 对已绑定店铺的影响 |
|---|---|
| 密码 / 主机 / 端口（`identity` 变） | 清 `egress_ip`、`egress_status → unchecked`、店铺转 `needs_login` |
| 只改到期日 | **不动店铺状态**，只更新 `proxy_expires_at` |
| 改后 `identity` 与另一池项冲突 | 409，**不写任何字段** |

### 4.4 删除

被占用 → 409 并带店铺名；空闲 → 直接删除。

### 4.5 导入的部分失败

逐行尽力，响应体是摘要：

```json
{
  "added": 8, "skipped": 2, "failed": 1,
  "failures": [{ "line": 5, "text": "1.2.3.4|abc|...", "reason": "端口必须是数字" }]
}
```

失败行原文只在**响应体**回显（用户自己刚粘贴的内容）；**审计日志只记行号与原因**，不落账号密码。

### 4.6 错误码映射

| 场景 | 类型 | HTTP |
|---|---|---|
| 删除/绑定已被占用的池项 | 新增 `ProxyPoolInUse` | 409 |
| 池项不存在 | 现有 `NotFound` | 404 |
| 格式错、绑定已过期项 | 现有 `InvalidRequest` | 422 |
| 直连冲突 | 现有 `EgressConflict` | 409 |

`api/errors.py` 的映射表增加 `(ProxyPoolInUse, 409)`。

## 5. 测试策略

### 5.1 后端

| 文件 | 覆盖 |
|---|---|
| `tests/store/proxy_pool_store_test.py` | CRUD、JOIN 视图字段形状、唯一索引撞车 |
| `tests/service/proxy_pool_test.py` | 导入解析与去重、部分失败摘要、编辑连锁、删除拦截、检测 |
| `tests/api/proxy_pool_test.py` | 5 个路由的状态码与响应体 |
| `tests/service/egress_test.py`（补） | `set_egress` 三个入口、绑定占用冲突 |
| `tests/store/db_test.py`（补） | 迁移 `0008` 在空库与含数据库上各跑一次 |

### 5.2 必须钉死的边界用例

1. 导入 10 行、第 3 与第 7 行格式错 → `added=8, failed=2`，行号准确
2. 同一代理连导两次 → 第二次 `skipped`，库中仅一条
3. 绑定已被别店占用的池项 → 409，且不写任何字段
4. 删除被占用的池项 → 409，错误信息带店铺名
5. 改密码 → 已绑定店铺 `egress_ip` 清空、转 `needs_login`
6. **只改到期日 → 店铺状态完全不变**
7. 过期池项不出现在可用列表，但已绑定的店仍能读出它（报「代理已到期」而非「代理缺失」）
8. 改密码后与另一池项 `identity` 撞车 → 409，原值不变

### 5.3 前端

- `logic/pool-form.test.ts`：粘贴文本 → 行数 / 有效行 / 错误行
- `logic/egress-form.test.ts` 补 `entry: "pool"` 分支
- `hooks/use-proxy-pool.test.tsx`：导入摘要回填、检测结果刷新
- `pages/proxy-pool/index.test.tsx`：表格三种状态渲染

### 5.4 回归

改动触及 `EgressService`，收尾必须跑全量后端（当前 547）与前端（当前 379）测试，全绿才算完成。

## 6. 收尾清单

1. `pnpm gen:api` 重新生成 `src/lib/api-types.ts`（后端 OpenAPI 变了，忘了这步前端类型会对不上）
2. `docs/design/backend.md` 5.17 节补代理池说明，并注明「池是配置来源，不是轮换」
3. `docs/design/data-model.md` 补 `proxy_pool` 表
4. 迁移 `0008` 在空库与现有库各跑一次
5. 文件长度自检：`*.py` ≤ 400、`*.ts/tsx` ≤ 300、`index.tsx` ≤ 80

## 7. 明确不做（YAGNI）

- 不在池里做自动轮换、自动切代理、负载均衡——违反 DEC-11；
- 不做池项的「分组 / 标签 / 备注」；
- 不做自动周期检测（用户选择的是手动检测）；
- 不做池项导入的 CSV / Excel 解析，只支持代理商原始文本行；
- 不改动现有的 IP 判重算法与出口检查时机。

## 8. 风险

| 风险 | 处理 |
|---|---|
| 删除 `shop` 三列属于破坏性迁移 | 迁移前自动备份（现有 `backup` 服务）；迁移代码先在现有库副本上跑一遍 |
| `LEFT JOIN` 后 `shop_store.list()` 在事务内多处调用，可能有性能影响 | 池表规模为几十行，索引在 `id` 主键上，可忽略；若有问题再拆查询 |
| 前端忘记重新生成类型 | 收尾清单第 1 条；CI 可加一条 `gen:api` 后 `git diff --exit-code` 的检查 |
