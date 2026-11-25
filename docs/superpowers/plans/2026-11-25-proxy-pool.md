# 代理池 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 代理信息从 `shop` 表搬进新的 `proxy_pool` 表，提供池的导入、编辑、删除、检测页面，并让添加店铺与出口对话框直接从池里选代理。

**Architecture:** `shop` 只存 `proxy_pool_id`，`shop_store.get/list` 用 `LEFT JOIN` 以原列名返回代理字段，出口的读路径保持原样。写路径集中在 `EgressService.bind_in`（建店与改出口共用），池的管理在独立的 `ProxyPoolService`；两者共用 `reset_shop_egress`，互不依赖。前端新增 `pages/proxy-pool/` 与共享下拉 `PoolSelect`。

**Tech Stack:** 后端 FastAPI + SQLAlchemy Core + Alembic + SQLite；前端 React + TanStack Query + arc 组件。无新增依赖。

**Spec:** [2026-11-25-proxy-pool-design.md](../specs/2026-11-25-proxy-pool-design.md)（第二版）；相关：[backend.md](../../design/backend.md) 5.17、[engineering-rules.md](../../engineering-rules.md)。

## Global Constraints

- 池只是配置来源：每店绑一个固定代理，**不做轮换**（DEC-11）。
- 账号密码只以 SecretBox 密文落库；接口响应、异常信息、日志、审计**只出现 `主机:端口`**，导入失败也不回显原文。
- `identity = sha256("{scheme}://{unquote(user)}:{unquote(password)}@{host.lower()}:{port}").hexdigest()`；迁移旧数据为 `legacy:<shop_id>`。
- `uq_shop_pool` 条件为 `proxy_pool_id IS NOT NULL AND status != 'disabled'`，与 `uq_shop_direct`、`uq_shop_egress_ip` 一致。
- 单次导入最多 500 行；空行跳过；只认代理商格式 `IP|端口|账号|密码|到期日`。
- 时间 ISO-8601 UTC（`%Y-%m-%dT%H:%M:%SZ`），到期日 `YYYY-MM-DD`。
- 文件长度：`*.py` ≤ 400、`*.ts/tsx` ≤ 300、页面 `index.tsx` ≤ 80。
- 后端命令在 `backend/` 下用 `uv run`；前端命令在 `frontend/` 下用 `pnpm`。
- 每个任务一个提交，提交信息末尾加 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。

## Review Focus

1. **凭证外泄**：导入失败行、编辑报错、检测失败、审计记录里出现账号或密码。期望：只有 `主机:端口` 与行号。→ Task 4、Task 6 各有一条断言密码不在输出里的测试。
2. **两个窗口同时绑定同一池项**：服务层预检都通过，第二个提交撞 `uq_shop_pool`。期望 409 `ProxyPoolInUse`，不是 500。→ Task 3 用直接写库模拟竞态。
3. **停用店铺重新启用时池项已被别店占用**：期望 409，文案提到「代理已被占用」，而不是只说直连。→ Task 3。
4. **编辑池项给了非法端口 / 主机**：期望 422 且池项与店铺都不变。→ Task 6。
5. **旧库升级**：含代理店铺的库升级后，`proxy_for` 解密结果与升级前一致；启动补算把 `legacy:` 换成真实 `identity`。→ Task 2、Task 5。

---

### Task 1: 迁移前自动备份

**Files:**
- Modify: `backend/app/store/migrate.py`
- Modify: `backend/app/main.py:71-75`（`lifespan` 里 `upgrade_to_head` 之前）
- Test: `backend/tests/store/migration_test.py`

**Interfaces:**
- Produces: `backup_before_upgrade(db_path: Path, backups_dir: Path, now: datetime) -> Path | None`；`current_revision(db_path: Path) -> str | None`

- [ ] **Step 1: 写失败测试**

```python
def test_backup_skipped_for_new_db(tmp_path):
    assert backup_before_upgrade(tmp_path / "app.db", tmp_path / "bk", NOW) is None

def test_backup_skipped_when_at_head(tmp_path):
    db = tmp_path / "app.db"; upgrade_to_head(db)
    assert backup_before_upgrade(db, tmp_path / "bk", NOW) is None

def test_backup_copies_db_when_behind_head(tmp_path):
    db = tmp_path / "app.db"; _upgrade_to(db, "0007")   # 用 alembic command.upgrade 到指定版本
    out = backup_before_upgrade(db, tmp_path / "bk", NOW)
    assert out.name == "pre-upgrade-0007-20261201T000000Z.db"
    assert "backup_run" in _tables(out)                 # 是完整可打开的库
```

- [ ] **Step 2:** `uv run pytest tests/store/migration_test.py -q` → FAIL（`ImportError`）
- [ ] **Step 3: 实现。** `current_revision` 用 `alembic.runtime.migration.MigrationContext`；head 用 `ScriptDirectory.from_config(cfg).get_current_head()`；复制用 `sqlite3.connect(src).backup(sqlite3.connect(dst))`。`lifespan` 在 `upgrade_to_head(db_path)` 前调用，目标目录 `settings.backups_dir`，生成文件时 `log.info("db.pre_upgrade_backup", file=...)`。
- [ ] **Step 4:** 同上命令 → PASS
- [ ] **Step 5: 提交** `feat(store): 迁移前自动备份数据库`

---

### Task 2: 归一化函数、迁移 0008、存储层改到池

**Files:**
- Modify: `backend/app/domain/egress_rules.py`
- Create: `backend/migrations/versions/0008_proxy_pool.py`
- Modify: `backend/app/store/schema.py`（新增 `proxy_pool` 表；`shop` 删三列、加 `proxy_pool_id` 外键与 `uq_shop_pool`）
- Create: `backend/app/store/proxy_pool_store.py`
- Modify: `backend/app/store/shop_store.py`
- Modify: `backend/app/service/egress.py`（`set_egress` 的 paste / proxy_url 路径改为 upsert 池再写 `proxy_pool_id`）
- Test: `backend/tests/domain/egress_rules_test.py`、`backend/tests/store/proxy_pool_store_test.py`、`backend/tests/store/migration_0008_test.py`、`backend/tests/store/migration_test.py`（`TABLES` 加 `proxy_pool`）、`backend/tests/service/egress_test.py:249`（改为把池项删掉来构造「代理缺失」）

**Interfaces:**
- Produces（domain）：
  - `@dataclass(frozen=True) class ProxyParts: scheme: str; host: str; port: int; username: str; password: str`
  - `split_proxy_url(url: str) -> ProxyParts`（账号密码已 `unquote`）
  - `join_proxy_url(parts: ProxyParts) -> str`（账号密码 `quote(safe='')`；无账号时不带 `@`）
  - `proxy_identity(url: str) -> str`
- Produces（`proxy_pool_store`，均接收 `conn`，无业务判断）：
  - `upsert(conn, *, identity: str, proxy_url: bytes, proxy_display: str, expires_at: str | None, now: str) -> int`：已存在则只在 `expires_at` 非空时覆盖它，返回池项 id
  - `get(conn, pool_id: int) -> Mapping | None`、`get_by_identity(conn, identity: str) -> Mapping | None`
  - `list_with_usage(conn) -> list[dict]`：池列 + `in_use_shop_id`、`in_use_shop_name`（只连启用店铺）
  - `referrers(conn, pool_id: int) -> list[Mapping]`：引用它的全部店铺（`id, name, status`）
  - `update(conn, pool_id: int, now: str, **fields)`：白名单 `identity, proxy_url, proxy_display, expires_at, last_checked_at, last_check_ip`，未知列 `ValueError`
  - `delete(conn, pool_id: int) -> None`、`list_legacy(conn) -> list[Mapping]`
- Produces（`shop_store`）：`get/list` 返回的映射里 `proxy_url / proxy_display / proxy_expires_at` 来自池；`set_egress` 白名单改为 `egress_mode, proxy_pool_id, egress_ip, egress_status, egress_checked_at, egress_ip_pending`

- [ ] **Step 1: 写失败测试（domain）**

```python
def test_identity_same_for_paste_and_url():
    pasted, _ = parse_provider_line("203.0.113.5|8000|u@x|p:w|2026-12-31")
    assert proxy_identity(pasted) == proxy_identity("http://u%40x:p%3Aw@203.0.113.5:8000")

def test_identity_ignores_host_case_and_differs_by_password():
    a = proxy_identity("http://u:p@Proxy.Example:8000")
    assert a == proxy_identity("http://u:p@proxy.example:8000")
    assert a != proxy_identity("http://u:q@proxy.example:8000")

def test_split_join_round_trip():
    url = "http://u%40x:p%3Aw@203.0.113.5:8000"
    assert join_proxy_url(split_proxy_url(url)) == url
```

- [ ] **Step 2: 写失败测试（迁移与存储）**

```python
# migration_0008_test.py
def test_0008_moves_shop_proxy_into_pool(tmp_path):
    db = tmp_path / "app.db"; _upgrade_to(db, "0007")
    _raw_insert_shop(db, name="店A", egress_mode="proxy", proxy_url=b"CIPHER",
                     proxy_display="203.0.113.5:8000", proxy_expires_at="2026-12-31")
    upgrade_to_head(db)
    with make_engine(db).connect() as conn:
        shop = shop_store.get(conn, 1)
        assert shop["proxy_url"] == b"CIPHER" and shop["proxy_expires_at"] == "2026-12-31"
        assert proxy_pool_store.get(conn, shop["proxy_pool_id"])["identity"] == "legacy:1"
        assert "proxy_url" not in {c["name"] for c in sa.inspect(conn).get_columns("shop")}

def test_0008_on_empty_db(tmp_path): ...  # 升级成功，proxy_pool 为空

# proxy_pool_store_test.py
def test_upsert_dedupes_and_keeps_expiry_when_none(engine): ...   # 第二次 upsert 返回同一 id；expires_at=None 不覆盖
def test_unique_pool_index_ignores_disabled_shops(engine): ...    # 停用店与启用店可同绑；两家启用店撞 IntegrityError
def test_delete_referenced_item_violates_fk(engine): ...          # 有店引用时 delete 抛 IntegrityError
def test_list_with_usage_reports_only_enabled_shop(engine): ...
```

- [ ] **Step 3:** `uv run pytest tests/domain/egress_rules_test.py tests/store -q` → FAIL
- [ ] **Step 4: 实现 domain 函数**，`proxy_identity` 内部用 `split_proxy_url`。
- [ ] **Step 5: 实现迁移 0008**（`revision="0008"`, `down_revision="0007"`），按 spec 1.4 五步：第 3 步用 `op.get_bind()` 逐行 `INSERT ... SELECT`，删列用 `op.execute("ALTER TABLE shop DROP COLUMN proxy_url")` 等三句，**不用 batch**。同步改 `schema.py`。
- [ ] **Step 6: 实现 `proxy_pool_store`**，并把 `shop_store.get/list` 改为 `sa.select(shop, proxy_pool.c.proxy_url, proxy_pool.c.proxy_display, proxy_pool.c.expires_at.label("proxy_expires_at")).select_from(shop.outerjoin(proxy_pool, ...))`。
- [ ] **Step 7: 改 `EgressService.set_egress`**：proxy 模式算出 `url` 后 `pool_id = proxy_pool_store.upsert(conn, identity=proxy_identity(url), proxy_url=box.encrypt(...), proxy_display=display_proxy(url), expires_at=expiry, now=now)`，再 `shop_store.set_egress(..., proxy_pool_id=pool_id)`；direct 写 `proxy_pool_id=None`。其余逻辑不动。
- [ ] **Step 8:** `uv run pytest -q`（全量，`shop` 表结构变了）→ PASS
- [ ] **Step 9: 提交** `feat(store): 代理信息迁入 proxy_pool 表（迁移 0008）`

---

### Task 3: 从池选代理绑定、占用冲突

**Files:**
- Modify: `backend/app/service/egress.py`
- Modify: `backend/app/service/shop_admin.py`（`update` 里 `IntegrityError` 文案）
- Modify: `backend/app/api/shop_schemas.py`（`EgressRequest.pool_id`）、`backend/app/api/shop.py`（传 `pool_id`）、`backend/app/api/errors.py`（`ProxyPoolInUse` 排在 `EgressConflict` 前）
- Test: `backend/tests/service/egress_test.py`、`backend/tests/service/shop_admin_test.py`（无则建）、`backend/tests/api/shop_api_test.py`

**Interfaces:**
- Consumes: Task 2 的 `proxy_pool_store.*`、`proxy_identity`
- Produces:
  - `class ProxyPoolInUse(EgressConflict)`，构造 `ProxyPoolInUse(shop_name: str)`，消息 `代理已被店铺「{shop_name}」使用`
  - `reset_shop_egress(conn, shop: Mapping, now: str) -> str`：清 `egress_ip / egress_ip_pending / egress_checked_at`、`egress_status="unchecked"`；`active` 转 `needs_login`；返回新状态
  - `EgressService.bind_in(conn, shop: Mapping, *, mode: str, pool_id: int | None, proxy_url: str | None, paste: str | None, expires_at: str | None, now: str, actor: str) -> str`（含审计，返回新店铺状态）
  - `EgressService.set_egress(shop_id, mode, pool_id=None, proxy_url=None, paste=None, expires_at=None, actor="system") -> None`
  - 常量 `REENABLE_CONFLICT = "该店铺的出口与其他启用店铺冲突（直连或代理已被占用），请先更换出口"`（`shop_admin.py`）

- [ ] **Step 1: 写失败测试**

```python
def test_bind_pool_item(env):            # set_egress(sid, "proxy", pool_id=pid) → proxy_for == URL_A，状态 unchecked
def test_bind_item_used_by_enabled_shop_conflicts(env):
    env.svc.set_egress(a, "proxy", pool_id=pid)
    with pytest.raises(ProxyPoolInUse, match="店A"):
        env.svc.set_egress(b, "proxy", pool_id=pid)
    assert env.row(b)["proxy_pool_id"] is None
def test_bind_expired_item_rejected(env):  # ValueError「代理已到期，请续费或更换」
def test_bind_missing_item_not_found(env):
def test_more_than_one_entry_rejected(env): # pool_id 与 paste 同时给 → ValueError
def test_paste_existing_proxy_reuses_item_and_updates_expiry(env)
def test_race_on_same_item_maps_to_conflict(env):  # 预检后直接用 shop_store 抢先绑定，再提交 → ProxyPoolInUse
def test_reenable_when_item_taken_says_proxy_in_use(env):  # ShopAdminService.update(enabled=True) → EgressConflict(REENABLE_CONFLICT)
```

API：`PUT /api/shops/{id}/egress {"mode":"proxy","pool_id":N}` → 200；占用 → 409 且 `error.type == "ProxyPoolInUse"`。

- [ ] **Step 2:** `uv run pytest tests/service/egress_test.py tests/service/shop_admin_test.py tests/api/shop_api_test.py -q` → FAIL
- [ ] **Step 3: 实现。** `bind_in` 按 spec 2.3：先校验入口参数（最多一个），pool 入口查 `proxy_pool_store.get` → `NotFound` / 过期 `ValueError` / `list_with_usage` 或 `referrers` 中有别的启用店 → `ProxyPoolInUse`；然后 `shop_store.set_egress` + `reset_shop_egress` + 审计。`set_egress` 外壳捕获 `IntegrityError`：mode 为 proxy 时转 `ProxyPoolInUse("另一家店铺")`，否则保持原 `EgressConflict`。
- [ ] **Step 4:** 同上命令 → PASS
- [ ] **Step 5: 提交** `feat(egress): 出口可从代理池选择，池项占用冲突返回 409`

---

### Task 4: 添加店铺时一并配置出口

**Files:**
- Modify: `backend/app/service/shop_admin.py`、`backend/app/wiring.py`（`ShopAdminService` 注入 `egress`）
- Modify: `backend/app/api/shop_schemas.py`（`ShopCreate.egress: EgressRequest | None = None`）、`backend/app/api/shop.py`（`create_shop` 加 `admin: str = Depends(require_admin)`，`ValueError` → `InvalidRequest`）
- Test: `backend/tests/service/shop_admin_test.py`、`backend/tests/api/shop_api_test.py`

**Interfaces:**
- Consumes: Task 3 的 `EgressService.bind_in`
- Produces: `ShopAdminService.__init__(engine, events, egress: EgressService, clock=...)`；`ShopAdminService.create(name, entity=None, shop_no=None, egress: EgressRequest-like dict | None = None, actor="system") -> int`（`egress` 为 `{"mode", "pool_id", "proxy_url", "paste", "expires_at"}` 的 dict，路由用 `body.egress.model_dump()`）

- [ ] **Step 1: 写失败测试**

```python
def test_create_with_pool_item_binds_in_same_transaction(...):
    sid = admin.create("店B", egress={"mode": "proxy", "pool_id": pid})
    assert shop_store.get(conn, sid)["proxy_pool_id"] == pid

def test_create_with_taken_item_creates_nothing(...):
    with pytest.raises(ProxyPoolInUse): admin.create("店C", egress={"mode": "proxy", "pool_id": pid})
    assert [s["name"] for s in shop_store.list(conn)] == ["店A"]   # 没有半成品

def test_create_with_bad_paste_creates_nothing(...)   # ValueError，店铺数不变
def test_create_without_egress_unchanged(...)
def test_create_with_paste_leaks_no_password_in_audit(...)  # audit_log 全表文本不含 PW
```

API：`POST /api/shops {"name":"店B","egress":{"mode":"proxy","pool_id":N}}` → 201 且 `proxy_display` 为池项的 `主机:端口`。

- [ ] **Step 2:** 跑上述测试 → FAIL
- [ ] **Step 3: 实现。** 一个 `engine.begin()` 内 `shop_store.create` → `bind_in`；提交后若有 egress 发 `SHOP_STATUS_CHANGED`。
- [ ] **Step 4:** 跑上述测试 → PASS
- [ ] **Step 5: 提交** `feat(shop): 添加店铺时可同时绑定出口`

---

### Task 5: 细分探测原因、ProxyPoolService 列表 / 导入 / 删除 / 补算

**Files:**
- Modify: `backend/app/service/egress_probe.py`、`backend/app/wiring.py`（`Overrides.probe: Probe | None`；构建 `proxy_pool` 服务）、`backend/app/main.py`（构建服务后调用 `app.state.proxy_pool.rehash_legacy()`）
- Create: `backend/app/service/proxy_pool.py`
- Test: `backend/tests/service/egress_probe_test.py`、`backend/tests/service/proxy_pool_test.py`

**Interfaces:**
- Produces（probe）：`ProbeReason`、`ProbeResult(ip, reason)`、`Probe`、`make_probe(echo_url, transport_factory=_default_factory) -> Probe`；`make_fetch_ip` 契约不变
- Produces（service）：
  - `MAX_IMPORT_LINES = 500`
  - `@dataclass(frozen=True) class ImportSummary: added: int; skipped: int; failed: int; failures: list[tuple[int, str]]`（行号从 1 起，按原文行计）
  - `ProxyPoolService(engine, box: SecretBox, events: EventBus, probe: Probe, clock=...)`
  - `list_view() -> list[dict]`：键 `id, proxy_display, expires_at, expiry_state, in_use_by: {"shop_id","shop_name"} | None, last_checked_at, last_check_ip`
  - `import_text(text: str, actor: str) -> ImportSummary`
  - `delete(pool_id: int, actor: str) -> None`
  - `rehash_legacy() -> int`（返回补算条数）

- [ ] **Step 1: 写失败测试（probe）**

```python
@pytest.mark.parametrize("outcome,reason", [
    (TimeoutError(), "timeout"),
    (EgressUnavailable("x"), "proxy_unavailable"),
    (TransientError("x"), "network"),
    (TransportResponse(500, b"1.2.3.4"), "bad_echo"),
    (TransportResponse(200, b"<html>"), "bad_echo"),
])
async def test_probe_reasons(outcome, reason): ...
async def test_probe_success(): assert result == ProbeResult("203.0.113.5", None)
```

- [ ] **Step 2: 写失败测试（service）**

```python
def test_import_partial_failure_reports_line_numbers(svc):
    text = "\n".join(good(i) if i not in (3, 7) else "bad|line" for i in range(1, 11))
    s = svc.import_text(text, "admin")
    assert (s.added, s.skipped, s.failed) == (8, 0, 2)
    assert [n for n, _ in s.failures] == [3, 7]
    assert PW not in repr(s) and PW not in _audit_text(engine)

def test_import_twice_and_in_batch_duplicates_skipped(svc)   # 同批两行相同 → added 1 skipped 1；再导一次 → skipped 全部
def test_import_blank_lines_ignored_and_over_limit_rejected(svc)  # 501 行有效 → ValueError
def test_delete_in_use_by_enabled_shop_conflicts(svc)        # ProxyPoolInUse，消息含店名
def test_delete_only_disabled_referrer_unbinds_it(svc)       # 成功；该店 proxy_pool_id None；proxy_for → EgressNotReady「代理地址缺失」
def test_list_view_hides_disabled_user_and_marks_expired(svc)
def test_rehash_legacy_sets_real_identity(svc)               # legacy:1 → proxy_identity(URL_A)
def test_rehash_legacy_keeps_placeholder_on_clash(svc)       # 已有同 identity 项 → 保留 legacy:，返回 0
```

- [ ] **Step 3:** `uv run pytest tests/service/egress_probe_test.py tests/service/proxy_pool_test.py -q` → FAIL
- [ ] **Step 4: 实现 `make_probe`**，`make_fetch_ip` 改为调用它取 `.ip`。
- [ ] **Step 5: 实现 `ProxyPoolService` 的四个方法。** 导入逐行 `parse_provider_line`，`ValueError` 的消息作为失败原因（这些消息本身不含账号密码）；审计 `CallRecord(None, "proxy_pool.import", actor, {"lines": n}, {"added","skipped","failed","failed_lines"}, "ok", 0)`。删除时同一事务内先把停用引用者的 `proxy_pool_id` 置空。
- [ ] **Step 6: 接线**：`Overrides.probe`；`build_services` 返回 `"proxy_pool"`；`lifespan` 构建服务后调用 `rehash_legacy()`。
- [ ] **Step 7:** `uv run pytest -q` → PASS
- [ ] **Step 8: 提交** `feat(proxy-pool): 池的导入、删除、列表与旧数据补算`

---

### Task 6: 编辑与检测

**Files:**
- Modify: `backend/app/service/proxy_pool.py`
- Test: `backend/tests/service/proxy_pool_test.py`

**Interfaces:**
- Consumes: `reset_shop_egress`（Task 3）、`split_proxy_url / join_proxy_url / proxy_identity`（Task 2）、`Probe`（Task 5）
- Produces:
  - `update(pool_id: int, *, host: str | None = None, port: int | None = None, username: str | None = None, password: str | None = None, expires_at: str | None = None, actor: str) -> None`（`None` = 不改）
  - `@dataclass(frozen=True) class CheckResult: ip: str | None; reason: ProbeReason | None; elapsed_ms: int; ip_in_use_by: dict | None`
  - `async check(pool_id: int, actor: str) -> CheckResult`

- [ ] **Step 1: 写失败测试**

```python
def test_change_password_resets_bound_shop(svc)       # 绑定店 active → needs_login，egress_ip None，egress_status unchecked；发了 SHOP_STATUS_CHANGED
def test_change_expiry_only_leaves_shop_untouched(svc) # 店铺行除 proxy_expires_at 外与之前完全相同
def test_edit_into_existing_identity_conflicts(svc)    # ProxyPoolInUse；池项密文与 display 不变
def test_edit_invalid_port_rejected_and_nothing_written(svc)  # port=0 → ValueError
def test_edit_error_messages_never_contain_password(svc)
async def test_check_success_records_ip(svc)           # last_check_ip、last_checked_at 写入；店铺不变
async def test_check_failure_clears_ip_and_returns_reason(svc)
async def test_check_reports_ip_used_by_other_shop(svc) # 别的启用店 egress_ip 相同 → ip_in_use_by == {"shop_id":..,"shop_name":"店B"}
async def test_check_ignores_own_bound_shop(svc)       # 绑定本项的店 IP 相同 → ip_in_use_by None
```

- [ ] **Step 2:** `uv run pytest tests/service/proxy_pool_test.py -q` → FAIL
- [ ] **Step 3: 实现 `update`**：解密 → `split_proxy_url` → 替换 → `join_proxy_url` → `validate_proxy_url`（端口须 1–65535）→ 新 `identity` 撞别的项抛 `ProxyPoolInUse`；`identity` 变了才对所有引用店铺调 `reset_shop_egress`。
- [ ] **Step 4: 实现 `check`**：事务外 `await probe(url)`，计时用 `time.monotonic()`；再开事务写结果并查 `ip_in_use_by`。
- [ ] **Step 5:** 同上命令 → PASS，再 `uv run pytest -q` 全量 → PASS
- [ ] **Step 6: 提交** `feat(proxy-pool): 池项编辑连锁重置与手动检测`

---

### Task 7: 代理池接口与前端类型

**Files:**
- Create: `backend/app/api/proxy_pool.py`、`backend/app/api/proxy_pool_schemas.py`
- Modify: `backend/app/main.py`（注册路由）、`frontend/openapi.json`、`frontend/src/lib/api-types.ts`
- Test: `backend/tests/api/proxy_pool_api_test.py`、`backend/tests/api/openapi_test.py`（路径集合加 `/api/proxy-pool`）

**Interfaces:**
- Consumes: Task 5、6 的 `ProxyPoolService`
- Produces（schema 名即前端类型名）：`ShopRef{shop_id, shop_name}`、`PoolItem`（字段同 `list_view`）、`PoolImportIn{text}`、`PoolImportFailure{line, reason}`、`PoolImportOut{added, skipped, failed, failures}`、`PoolPatch{host?, port?, username?, password?, expires_at?}`、`PoolCheckOut{ip, reason, elapsed_ms, ip_in_use_by}`；路由前缀 `/api/proxy-pool`，`tags=["proxy-pool"]`；`ValueError` → `InvalidRequest`

- [ ] **Step 1: 写失败测试**：五个路由的成功状态码（200 / 200 / 200 / 204 / 200）；删除占用 409 `ProxyPoolInUse`；不存在 404；导入 501 行 422；未登录 `GET /api/proxy-pool` 401；所有响应文本不含测试密码。
- [ ] **Step 2:** `uv run pytest tests/api/proxy_pool_api_test.py -q` → FAIL
- [ ] **Step 3: 实现路由与 schema**，写操作参数里取 `admin: str = Depends(require_admin)`。
- [ ] **Step 4:** `uv run pytest -q` → PASS
- [ ] **Step 5: 生成前端类型**

```bash
cd backend && uv run python -m app.main --export-openapi ../frontend/openapi.json
cd ../frontend && pnpm gen:api && pnpm exec tsc -b
```

Expected: `tsc` 无报错（现有代码对 `EgressRequest` 新增可选字段兼容）。
- [ ] **Step 6: 提交** `feat(api): 代理池接口`

---

### Task 8: 代理池页面

**Files:**
- Create: `frontend/src/pages/proxy-pool/index.tsx`、`proxy-pool-page.module.css`、`logic/pool-import.ts`、`logic/pool-status.ts`、`hooks/use-proxy-pool.ts`、`components/pool-table.tsx`、`components/import-dialog.tsx`、`components/edit-dialog.tsx`，以及对应 `*.test.ts(x)` 与 `index.test.tsx`
- Modify: `frontend/src/lib/query-keys.ts`（`proxyPool: () => ["proxyPool"] as const`）、`frontend/src/app.tsx`（`/proxy-pool` 路由）、`frontend/src/components/custom/app-shell/logic/nav-items.ts`（`NavIcon` 加 `"proxy"`，`FOOTER_NAV` 追加代理池）、`.../components/side-nav.tsx`（`proxy: Network`）、`.../logic/nav-items.test.ts`

**Interfaces:**
- Consumes: Task 7 的 `PoolItem / PoolImportOut / PoolCheckOut / PoolPatch`
- Produces:
  - `previewImport(text: string): { total: number; valid: number; errors: { line: number; reason: string }[] }`（规则与后端 `parse_provider_line` 一致：5 段非空、端口纯数字、到期日真实日期；空行不计入 total）
  - `poolStatus(item: PoolItem): { label: string; tone: "success" | "info" | "danger" | "muted" }`：空闲 `success`；`已用于「X」` `info`；过期且占用 `danger`；过期空闲 `muted`，文案 `已过期`
  - `checkReasonText(reason: PoolCheckOut["reason"]): string`：`timeout` → `检测超时（10 秒）`；`proxy_unavailable` → `代理连不上，请检查地址、账号密码或是否到期`；`network` → `网络错误，请稍后重试`；`bad_echo` → `回显地址返回的不是 IP，请检查设置里的回显地址`
  - `useProxyPool()` 返回 `{ items, loading, importText(text) → Promise<PoolImportOut | {error}>, update(id, patch), remove(id), check(id) → Promise<PoolCheckOut>, pendingIds: number[] }`；成功后失效 `queryKeys.proxyPool()` 与 `queryKeys.shops()`

- [ ] **Step 1: 写失败测试**：`pool-import.test.ts`（第 3、7 行错 → errors 行号 [3,7]）；`pool-status.test.ts`（四种状态、四种原因）；`use-proxy-pool.test.tsx`（导入后摘要回填、检测后列表刷新）；`index.test.tsx`（三种状态渲染、检测结果含 `ip_in_use_by` 时显示「该 IP 已被店铺「店B」使用」）；`nav-items.test.ts` 期望 `["店铺管理", "代理池"]`。
- [ ] **Step 2:** `pnpm test src/pages/proxy-pool src/components/custom/app-shell` → FAIL
- [ ] **Step 3: 实现。** 编辑对话框密码框占位文字「留空表示不改」；删除用确认对话框；导入对话框提交前显示 `previewImport` 的行数统计，提交后显示后端摘要与失败行号。
- [ ] **Step 4:** 同上命令 → PASS；`pnpm lint && pnpm exec tsc -b` 无报错
- [ ] **Step 5: 提交** `feat(frontend): 代理池页面`

---

### Task 9: 出口对话框与添加店铺接入池

**Files:**
- Create: `frontend/src/components/custom/pool-select/pool-select.tsx`、`frontend/src/components/custom/pool-select/available-pool.ts`（+ 测试）
- Modify: `frontend/src/pages/shop/logic/egress-form.ts`、`egress-form.test.ts`、`components/egress-dialog.tsx`、`components/egress-fields.tsx`、`components/add-shop-dialog.tsx`、`hooks/use-shop-actions.ts`（`addShop` 透传 `egress`）、`index.test.tsx`

**Interfaces:**
- Consumes: `useProxyPool` 的列表查询（只读，直接用 `queryKeys.proxyPool()` 的 `useQuery`）
- Produces:
  - `availablePoolItems(items: PoolItem[]): PoolItem[]`（`in_use_by === null && expiry_state !== "expired"`）
  - `<PoolSelect value={number | null} onChange={(id) => void} error?: string />`，选项文案 `{proxy_display} · 到期 {MM-DD}`，无到期日显示 `不限期`；空时显示「池里没有可用代理」
  - `EgressForm` 增加 `poolId: number | null`，`entry: "pool" | "paste" | "fields"`，`emptyEgressForm()` 默认 `entry: "pool"`；`EgressField` 增加 `"poolId"`；`buildEgressRequest` 的 pool 分支：未选 → `errors.poolId = "请选择池里的代理"`，选了 → `{ mode: "proxy", pool_id }`

- [ ] **Step 1: 写失败测试**：`egress-form.test.ts` 补 pool 分支两例；`available-pool.test.ts` 过滤占用与过期；`index.test.tsx` 补「添加店铺时选池项 → POST 体含 `egress.pool_id`」「已有启用直连店时直连选项禁用并说明」「出口区不填 → POST 体无 `egress`」。
- [ ] **Step 2:** `pnpm test src/pages/shop src/components/custom/pool-select` → FAIL
- [ ] **Step 3: 实现。** 出口对话框的入口切换增加「从池选择」；添加店铺对话框的出口区复用 `EgressFields`（pool / paste 两个入口），默认「暂不设置」。
- [ ] **Step 4:** 同上命令 → PASS；`pnpm test && pnpm lint && pnpm exec tsc -b` 全量无报错
- [ ] **Step 5: 提交** `feat(frontend): 出口与添加店铺从代理池选择`

---

### Task 10: 设计文档同步与全量回归

**Files:**
- Modify: `docs/design/backend.md`（5.17 补代理池一段，注明「池是配置来源，不是轮换」）、`docs/design/data-model.md`（`proxy_pool` 表；`shop` 删三列、加 `proxy_pool_id`；6.3 关键约束加 `uq_shop_pool`）、`docs/design/local-api.md`（5 个接口；`EgressRequest.pool_id`；`ShopCreate.egress`）、`docs/design/frontend.md`（导航底部「代理池」）

- [ ] **Step 1: 改文档**（内容取自 spec 1、2.2–2.4、3.2）
- [ ] **Step 2: 全量回归**

```bash
cd backend && uv run ruff check . && uv run pytest -q
cd ../frontend && pnpm lint && pnpm test && pnpm build
```

Expected: 全部通过。

- [ ] **Step 3: 文件长度自检**

```bash
cd .. && find backend/app -name '*.py' | xargs wc -l | awk '$1>400 && $2!="total"'
find frontend/src -name '*.ts*' | xargs wc -l | awk '$1>300 && $2!="total"'
wc -l frontend/src/pages/proxy-pool/index.tsx
```

Expected: 前两条无输出，最后一条 ≤ 80。
- [ ] **Step 4: 提交** `docs: 代理池写入设计文档`
