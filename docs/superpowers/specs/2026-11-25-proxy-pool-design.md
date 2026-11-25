# 代理池（Proxy Pool）设计

**Goal:** 在「设置」下新增代理池页面，支持批量导入代理商给出的多条代理；添加店铺时可直接从池中选取可用代理一并完成出口配置，避免每次手工复制粘贴。

**Scope:** 新增 `proxy_pool` 表与迁移 `0008`、代理池的 store / service / api 三层、前端 `pages/proxy-pool/` 页面，以及添加店铺与出口对话框的接入。不改动现有的出口检查判定（`judge_egress`）、IP 判重、会话登录流程。

**修订记录（2026-11-25 第二版）**：对照代码核对后修正——迁移拿不到解密密钥（1.4）、迁移前其实没有自动备份（1.4）、停用店铺会永久占住池项（1.2、4.4）、`identity` 未归一化（1.1）、「上层零改动」说法不准确（1.3）、检测时可提前发现 IP 撞车（2.6）、编辑接口不能回传密码（2.2）。

## 0. 边界声明：这**不是**轮换代理池

工程规范 [engineering-rules.md](../../engineering-rules.md) 8.2、[backend.md](../../design/backend.md) 5.17、[gaps.md](../../gaps.md) DEC-11 三处明确：

> 每店固定独立出口；**禁止使用轮换代理池**；**禁止伪造设备指纹**。

本设计中的「代理池」只是**配置来源**：池是候选清单，每家店铺仍然绑定**一个**固定代理，绑定后不会自动切换。池的引入不改变以下既有约束：

- 一个池项同一时间只能绑一家启用店铺；
- 两家启用店铺的出口 IP 必须不同；
- 出口异常时暂停该店，**绝不回退直连**；
- 最多一家启用店铺可以使用 `direct`。

后续若有人想基于此表实现「一店多代理自动轮换」，那是**违反既有决策**的新需求，必须重新走决策流程。

## 1. 数据模型

### 1.1 新表 `proxy_pool`

```sql
CREATE TABLE proxy_pool (
  id              INTEGER PRIMARY KEY,
  identity        TEXT NOT NULL UNIQUE,  -- 见下文；导入去重
  proxy_url       BLOB NOT NULL,         -- SecretBox 密文
  proxy_display   TEXT NOT NULL,         -- host:port，界面与日志只显示这个
  expires_at      TEXT,                  -- YYYY-MM-DD，可空表示不限
  last_checked_at TEXT,                  -- 上次手动检测时间
  last_check_ip   TEXT,                  -- 上次检测到的出口 IP，失败为 NULL
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
```

**`identity` 的算法**（纯函数 `domain/egress_rules.proxy_identity(url) -> str`）：

```
sha256( "{scheme}://{unquote(user)}:{unquote(password)}@{host.lower()}:{port}" ).hexdigest()
```

先拆解再拼接，使「粘贴代理商格式」（账号密码经 `quote` 编码）和「手填 URL」得到同一个值；不把凭证以可还原形式写进索引。迁移搬来的旧数据暂用 `legacy:<shop_id>`（见 1.4）。

### 1.2 `shop` 表变化

- **新增** `proxy_pool_id INTEGER REFERENCES proxy_pool(id)`（库已开 `PRAGMA foreign_keys=ON`，删除被引用的池项会被数据库拒绝，作为兜底）
- **新增部分唯一索引**，与现有 `uq_shop_direct`、`uq_shop_egress_ip` 口径一致，**停用店铺不占位**：

  ```sql
  CREATE UNIQUE INDEX uq_shop_pool
    ON shop(proxy_pool_id) WHERE proxy_pool_id IS NOT NULL AND status != 'disabled';
  ```

  不排除停用店铺的话，停用店铺会永久占住池项，而店铺没有「删除」也没有「解绑」操作，池项就再也用不了。
- **删除** `proxy_url` / `proxy_display` / `proxy_expires_at` 三列（单一口径：代理信息只存在池里）。`store/schema.py` 同步修改，`migration_test` 会校验两者一致。

### 1.3 读路径不变的手法

`shop_store.get()` / `shop_store.list()` 改为 `LEFT JOIN proxy_pool`，把池的字段**以原列名**取出：

```sql
SELECT s.*,
       p.proxy_url     AS proxy_url,
       p.proxy_display AS proxy_display,
       p.expires_at    AS proxy_expires_at
FROM shop s LEFT JOIN proxy_pool p ON p.id = s.proxy_pool_id
```

因此**只读这些键**的代码不需要改：`EgressService.check / ensure_ready / proxy_for / _require_usable`、`ShopAdminService._view`、`ShopRow`。

**需要改的写路径**：

- `shop_store.set_egress` 的白名单：去掉 `proxy_url` / `proxy_display` / `proxy_expires_at`，加入 `proxy_pool_id`；
- `EgressService.set_egress`：改为写 `proxy_pool_id`（2.3）；
- `ShopAdminService.update` 的「重新启用」分支：撞 `uq_shop_pool` 时的报错文案（4.4）。

`proxy_url` 在 JOIN 结果中仍是密文，店铺侧的解密仍只在 `EgressService.proxy_for` 一处；池侧的解密只在 `ProxyPoolService`（检测、编辑）。

### 1.4 迁移 `0008`

顺序：

1. 建 `proxy_pool` 表；
2. `ALTER TABLE shop ADD COLUMN proxy_pool_id INTEGER REFERENCES proxy_pool(id)`；
3. 数据搬迁：对每个 `shop.proxy_url IS NOT NULL` 的行，**原样复制密文**插入池项，`identity = 'legacy:<shop_id>'`，回填 `shop.proxy_pool_id`。迁移在 Alembic 里运行，**拿不到 SecretBox，无法解密算真实 `identity`**；每店各建一项，也保证第 5 步的唯一索引不会撞车；
4. 用原生 `ALTER TABLE shop DROP COLUMN ...` 删除三列（SQLite ≥ 3.35）。**不用 Alembic batch 模式**：batch 会重建 `shop` 表，而 `shop` 被多张表外键引用，开着外键约束时重建有风险；
5. 建 `uq_shop_pool`。

**启动时补算**：`ProxyPoolService.rehash_legacy()` 在应用启动时执行一次，把 `legacy:` 开头的池项解密后改成真实 `identity`；若与已有项撞车则保留 `legacy:` 并记一条警告日志（两家店原本就填了同一个代理，属于历史数据问题，不自动合并）。

现有库只有一家直连店铺（`proxy_url IS NULL`），第 3 步实际是空操作，但代码必须写并测试。

与既有迁移一致：`downgrade()` 抛 `NotImplementedError`。

**迁移前备份**：现有启动流程直接 `upgrade_to_head`，没有迁移前备份，而 `backup` 服务是在迁移之后才构建的。新增 `store/migrate.py: backup_before_upgrade(db_path, backups_dir) -> Path | None`：库文件存在且当前版本不是 head 时，用 `sqlite3` 的 `backup()` API（WAL 下安全）复制到 `backups_dir/pre-upgrade-<旧版本>-<时间>.db`，`lifespan` 在 `upgrade_to_head` 之前调用。此后所有破坏性迁移都受益。

## 2. 后端

### 2.1 模块划分

| 文件 | 职责 |
|---|---|
| `store/proxy_pool_store.py` | 池表 CRUD + `list_with_usage()`（LEFT JOIN 启用店铺取占用者）；无业务判断，不碰加密 |
| `service/proxy_pool.py` | 导入解析、去重、编辑、删除、检测、`rehash_legacy` |
| `api/proxy_pool.py` | 5 个路由 |
| `api/proxy_pool_schemas.py` | 请求/响应 schema |

### 2.2 接口

```
GET    /api/proxy-pool                 池列表（每项带占用店铺）
POST   /api/proxy-pool/import          批量导入 { "text": "多行" }
PATCH  /api/proxy-pool/{id}            改主机 / 端口 / 账号 / 密码 / 到期日
DELETE /api/proxy-pool/{id}            被启用店铺占用时 409
POST   /api/proxy-pool/{id}/check      手动检测，经该代理取出口 IP
```

应用已全局要求登录（`create_app` 的 `dependencies=[Depends(require_admin)]`）；写操作（后四个）与现有出口接口一样在路由参数里再取一次 `admin: str = Depends(require_admin)`，作为审计的 `actor`。

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

`in_use_by` 只看**启用**店铺；没有则为 `null`。

`PATCH` 请求体全部可选：`{host?, port?, username?, password?, expires_at?}`。**任何接口都不回传账号密码**，所以编辑框里密码留空表示「不改」；服务端解密旧 URL、替换给出的部分、重新校验并加密。

### 2.3 `set_egress` 的三个入口

对外仍是同一个 `PUT /api/shops/{id}/egress`，`EgressRequest` 增加 `pool_id`：

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
| `proxy` + `pool_id` | 校验池项存在、未过期、未被别的启用店铺占用，然后绑定 |
| `proxy` + `paste` / `proxy_url` | **先按 `identity` upsert 进池再绑定**：已存在则复用该池项，本次给出的到期日覆盖原值（未给则保留）；不存在则新建 |

`pool_id`、`paste`、`proxy_url` 三者最多给一个，否则 422。三条路径最终都写 `shop.proxy_pool_id`。原有「清空已确认 IP、状态复位 `unchecked`、已登录店铺转 `needs_login`」逻辑不变。

### 2.4 加店铺时一并配出口

`POST /api/shops` 增加可选字段：

```python
class ShopCreate(BaseModel):
    name: str
    entity: str | None = None
    shop_no: str | None = None
    egress: EgressRequest | None = None
```

`ShopAdminService.create(..., egress=None, actor=...)` 在**同一个事务**内完成建店与绑定，避免出现「店建好了但出口没配上」的半成品。路由增加 `admin: str = Depends(require_admin)` 取 `actor`。

为此 `EgressService` 内部把「校验 + upsert 池项 + 写 `proxy_pool_id` + 清 IP / 转 `needs_login` + 审计」抽成接收 `conn` 的方法 `bind_in(conn, shop, request, now, actor) -> str`（返回新的店铺状态）；`set_egress()` 退化成「开事务 → 调它 → 提交 → 发事件」的外壳，`ShopAdminService.create` 用自己事务的 conn 调同一个方法。事件统一在事务提交之后发布。

### 2.5 依赖方向

```
api/proxy_pool → service/proxy_pool → store/proxy_pool_store
                                   ↘ store/shop_store（编辑后重置已绑定店铺）

service/egress → store/proxy_pool_store（查 + upsert，不依赖 ProxyPoolService）
service/shop_admin → service/egress（create 时调 bind_in）
```

`ProxyPoolService` 与 `EgressService` 互不依赖。「换出口导致店铺转 `needs_login`」的重置动作抽成 `service/egress.py` 里的模块级函数 `reset_shop_egress(conn, shop, now) -> str`，两边共用，状态机只有一份。

### 2.6 检测

现有 `make_fetch_ip` 把一切失败都压成 `None`，区分不出原因。在 `service/egress_probe.py` 新增更细的入口，并让旧函数复用它：

```python
ProbeReason = Literal["timeout", "proxy_unavailable", "network", "bad_echo"]

@dataclass(frozen=True)
class ProbeResult:
    ip: str | None
    reason: ProbeReason | None   # 成功时为 None

Probe = Callable[[str | None], Awaitable[ProbeResult]]

def make_probe(echo_url: str, transport_factory=...) -> Probe: ...
def make_fetch_ip(echo_url: str, transport_factory=...) -> FetchIp:  # 契约不变，内部调 make_probe
```

原因映射（与 `CurlTransport._classify` 对齐）：`TimeoutError` → `timeout`；`EgressUnavailable` → `proxy_unavailable`；其他 `TransientError` → `network`；非 200 或回显不是 IP → `bad_echo`。

`ProxyPoolService.check(id)`：

1. 从 store 取池项 → `SecretBox` 解密（事务外做网络请求）；
2. 调注入的 `probe(proxy_url)`；
3. 成功：写 `last_checked_at` / `last_check_ip`；
4. 失败：只写 `last_checked_at`，`last_check_ip` 置 NULL；
5. 返回 `{ip, reason, elapsed_ms, ip_in_use_by}`。`ip_in_use_by`：检测到的 IP 若等于**其他**启用店铺（不含本池项绑定的店）已确认的 `egress_ip`，返回那家店的 `{shop_id, shop_name}`——在绑定之前就发现「两个代理出口其实是同一个 IP」。

`reason` 到界面文案的映射放在前端 `logic/`，后端只回传机器可读的枚举值。

检测是只读操作，**不改店铺任何状态**。`probe` 通过 `Overrides.probe` 注入，测试用假函数。

## 3. 前端

### 3.1 新页面 `pages/proxy-pool/`

严格四层（engineering-rules 2.1）：

```
logic/pool-import.ts        导入文本 → 总行数 / 有效行 / 错误行（纯函数，提交前预览）
logic/pool-status.ts        池项 → 状态文案与色调；检测 reason → 文案
hooks/use-proxy-pool.ts     列表、导入、编辑、删除、检测
components/pool-table.tsx   表格：代理 / 到期日 / 状态 / 上次检测 / 操作
components/import-dialog.tsx
components/edit-dialog.tsx
index.tsx                   装配（≤ 80 行）
```

表格「状态」直接反映绑定关系：`空闲` / `已用于「测试店」` / `已过期`（过期且被占用用 danger 色调，过期空闲用 muted）。

### 3.2 导航

`FOOTER_NAV` 增加 `{ path: "/proxy-pool", label: "代理池", icon: "proxy" }`；`NavIcon` 增加 `proxy`；`side-nav.tsx` 的 `ICONS` 映射到 lucide 的 `Network`；`app.tsx` 增加路由。

### 3.3 添加店铺对话框

在现有三个输入框下增加「出口」区：

```
出口   ( ) 直连    (•) 代理
       [ 下拉：1.2.3.4:8080 · 到期 12-31   ▾ ]
       + 新增代理
```

- 下拉只列「未占用 + 未过期」的池项；空池时提示「池里没有可用代理」并给「+ 新增代理」；
- 「+ 新增代理」展开一行粘贴框，格式与现有 `IP|端口|账号|密码|到期日` 一致；
- 已有启用店铺直连时「直连」置灰并说明原因；
- 出口区可以不填（`egress` 省略），与现状一致：之后再到出口对话框配置。

前端的置灰只是提前告知，**正确性仍由后端保证**。

### 3.4 现有出口对话框

`logic/egress-form.ts` 的 `entry` 从 `"paste" | "fields"` 扩为 `"pool" | "paste" | "fields"`，`EgressForm` 增加 `poolId: number | null`，默认 `entry: "pool"`；`buildEgressRequest` 增加 `entry="pool"` 分支：未选时报错「请选择池里的代理」，选了返回 `{ mode: "proxy", pool_id }`。`paste` / `fields` 两个入口保持原样。下拉组件 `PoolSelect` 两个对话框共用，放在 `components/custom/pool-select/`。

## 4. 一致性与错误处理

### 4.1 规则与保证方式

| 规则 | 保证方式 |
|---|---|
| 一个池项只能绑一家启用店铺 | 服务层先查并抛 `ProxyPoolInUse`；`uq_shop_pool` 部分唯一索引兜底 |
| 同一代理不重复入池 | 导入时按 `identity` 去重（含同一批内的重复行），重复行计入 `skipped` |
| 两家店不能用同一出口 IP | 池层只在**检测时提示**（`ip_in_use_by`）；强制仍靠 `judge_egress` 的 `duplicate` 判定与 `uq_shop_egress_ip` |
| 最多一家直连 | 沿用 `_ensure_no_other_direct` + `uq_shop_direct` 兜底 |
| 被引用的池项不能悄悄消失 | `shop.proxy_pool_id` 外键 |

### 4.2 过期语义

复用 `expiry_state` 的 `ok / expiring / expired`：

- 池中过期项在下拉里不出现，表格标红；
- 绑定已过期项 → 422「代理已到期，请续费或更换」；
- 已绑定店铺走 `_require_usable`，抛「代理已到期，请续费或更换」（与现状一致）。

### 4.3 编辑池项的连锁反应

| 改什么 | 对绑定它的启用店铺的影响 |
|---|---|
| 主机 / 端口 / 账号 / 密码（`identity` 变） | `reset_shop_egress`：清 `egress_ip`、`egress_status → unchecked`、`active` 店铺转 `needs_login`；提交后发事件 |
| 只改到期日 | **不动店铺状态**，只更新池项 `expires_at`（店铺经 JOIN 读到新值） |
| 改后 `identity` 与另一池项冲突 | 409，**不写任何字段** |

### 4.4 删除与停用店铺

| 情况 | 结果 |
|---|---|
| 被启用店铺占用 | 409，信息带店铺名 |
| 只被停用店铺引用 | 同一事务内把这些店的 `proxy_pool_id` 置空再删；这些店重新启用后读到「该店铺代理地址缺失，请重新设置出口」（现有文案） |
| 空闲 | 直接删除 |

停用店铺重新启用时，若它的池项已被别的启用店铺占用，撞 `uq_shop_pool`：`ShopAdminService.update` 现有的 `IntegrityError` 文案只提直连，改为「该店铺的出口与其他启用店铺冲突（直连或代理已被占用），请先更换出口」。

### 4.5 导入的部分失败

逐行尽力；空行跳过；单次最多 500 行（超过 422）。响应体是摘要：

```json
{
  "added": 8, "skipped": 2, "failed": 1,
  "failures": [{ "line": 5, "reason": "端口必须是数字" }]
}
```

`failures` **不回显原文**（原文含账号密码；用户按行号对照自己粘贴的内容即可）。审计日志同样只记行号与原因。

### 4.6 错误码映射

| 场景 | 类型 | HTTP |
|---|---|---|
| 删除/绑定已被占用的池项 | 新增 `ProxyPoolInUse`（`service/egress.py`，继承 `EgressConflict`） | 409 |
| 编辑后与另一池项重复 | 同上 | 409 |
| 池项不存在 | 现有 `NotFound` | 404 |
| 格式错、绑定已过期项、入口参数冲突 | 现有 `InvalidRequest` | 422 |
| 直连冲突 | 现有 `EgressConflict` | 409 |

`ProxyPoolInUse` 继承 `EgressConflict`，`api/errors.py` 映射表无需新增条目，但须放在 `EgressConflict` 之前以保留具体类型名。

## 5. 测试策略

### 5.1 后端

| 文件 | 覆盖 |
|---|---|
| `tests/domain/egress_rules_test.py`（补） | `proxy_identity` 归一化 |
| `tests/store/proxy_pool_store_test.py` | CRUD、`list_with_usage`、JOIN 视图字段形状、唯一索引撞车 |
| `tests/service/proxy_pool_test.py` | 导入解析与去重、部分失败摘要、编辑连锁、删除、检测、`rehash_legacy` |
| `tests/api/proxy_pool_api_test.py` | 5 个路由的状态码与响应体、未登录 401 |
| `tests/service/egress_test.py`（补） | `set_egress` 三个入口、绑定占用冲突 |
| `tests/service/egress_probe_test.py`（补） | `make_probe` 四种 reason |
| `tests/store/migration_0008_test.py` | 迁移在空库与含代理店铺的库上各跑一次 |

### 5.2 必须钉死的边界用例

1. 导入 10 行、第 3 与第 7 行格式错 → `added=8, failed=2`，行号准确，响应里没有账号密码
2. 同一代理连导两次 → 第二次 `skipped`，库中仅一条；同一批内重复也只入一条
3. 粘贴格式与手填 URL 指向同一代理 → `identity` 相同
4. 绑定已被别店占用的池项 → 409，且不写任何字段
5. 删除被启用店铺占用的池项 → 409，错误信息带店铺名；只被停用店铺引用 → 删除成功，该店 `proxy_pool_id` 为空
6. 改密码 → 已绑定店铺 `egress_ip` 清空、转 `needs_login`
7. **只改到期日 → 店铺状态完全不变**
8. 过期池项不出现在可用列表，但已绑定的店仍能读出它（报「代理已到期」而非「代理缺失」）
9. 改密码后与另一池项 `identity` 撞车 → 409，原值不变
10. 停用店铺释放池项后，别店可绑定；原店重新启用 → 409 新文案
11. 迁移：含代理店铺的库升级后，`proxy_for` 解密出的 URL 与升级前一致

### 5.3 前端

- `logic/pool-import.test.ts`：粘贴文本 → 行数 / 有效行 / 错误行
- `logic/pool-status.test.ts`：三种状态、四种 reason 文案
- `logic/egress-form.test.ts` 补 `entry: "pool"` 分支
- `hooks/use-proxy-pool.test.tsx`：导入摘要回填、检测结果刷新
- `pages/proxy-pool/index.test.tsx`：表格三种状态渲染
- `nav-items.test.ts` 更新底部入口

### 5.4 回归

改动触及 `EgressService` 与 `shop` 表结构，收尾必须跑全量后端与前端测试，全绿才算完成。

## 6. 收尾清单

1. 后端导出 `frontend/openapi.json` 后 `pnpm gen:api` 重新生成 `src/lib/api-types.ts`（CI 校验二者一致）
2. `docs/design/backend.md` 5.17 节补代理池说明，并注明「池是配置来源，不是轮换」
3. `docs/design/data-model.md` 补 `proxy_pool` 表，`shop` 表删三列、加 `proxy_pool_id`
4. `docs/design/local-api.md` 补 5 个接口与 `EgressRequest.pool_id`、`ShopCreate.egress`
5. 文件长度自检：`*.py` ≤ 400、`*.ts/tsx` ≤ 300、`index.tsx` ≤ 80

## 7. 明确不做（YAGNI）

- 不在池里做自动轮换、自动切代理、负载均衡——违反 DEC-11；
- 不做池项的「分组 / 标签 / 备注」；
- 不做自动周期检测（用户选择的是手动检测）；
- 不做批量检测（逐项点「检测」即可；需要时再加）；
- 不做池项导入的 CSV / Excel 解析，只支持代理商原始文本行；
- 不改动现有的 IP 判重算法与出口检查时机。

## 8. 风险

| 风险 | 处理 |
|---|---|
| 删除 `shop` 三列属于破坏性迁移 | 迁移前自动备份（1.4 新增的 `backup_before_upgrade`）；迁移测试覆盖含代理数据的库 |
| 迁移拿不到密钥 | `legacy:` 占位 + 启动补算（1.4） |
| `LEFT JOIN` 后 `shop_store.list()` 调用变重 | 池表几十行、按主键连接，可忽略 |
| 前端忘记重新生成类型 | 收尾清单第 1 条；CI 已校验 `openapi.json` 一致 |
