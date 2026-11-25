# CloakBrowser 集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 CloakBrowser 的定制 Chromium 取代系统浏览器作为项目唯一的浏览器通道，并让每店拥有一个固定不变的指纹身份。

**Architecture:** 项目通过 PyPI 包 `cloakbrowser==0.3.30`（对应 Chromium 146.0.7680.177.5，无 license 校验）启动浏览器，二进制缓存在项目自己的数据目录下，与机器上其他工具完全隔离。指纹种子按「每店一个、首次生成后永久固定」存入该店 profile 目录，启动时以 `--fingerprint=<seed>` 覆盖库默认的随机值。

**Tech Stack:** Python 3.12、cloakbrowser 0.3.30（PyPI）、Playwright、pydantic-settings、pytest

**Spec:** 无独立 spec 文档；设计依据是本轮对话中确认的三条事实——(1) `cloakbrowser` 0.3.30 的 `CHROMIUM_VERSION == "146.0.7680.177.5"` 且代码中无任何 license 校验；(2) 该版本的 `build_args()` 按 flag key 去重且 user args 优先，`--fingerprint=<seed>` 可覆盖默认随机值；(3) 二进制缓存目录可由 `CLOAKBROWSER_CACHE_DIR` 指定。

## Global Constraints

- 依赖方向：`api → service → adapter / store / domain`；`shared/` 放跨模块工具且必须配单测。
- 文件 `*.py` ≤ 400 行；测试文件命名为 `<name>_test.py`。
- 秘密材料不入库：指纹种子是本地随机数，不进 git（`profiles/` 已在数据目录下，不随仓库分发）。
- 版本钉死：`pyproject.toml` 中写 `cloakbrowser==0.3.30`，**禁止**使用 `>=`，否则升级到 0.7.x 会变成需要 license key 的 Pro 版且下载 Chromium 156。
- **禁用一切自动更新**：启动时设 `CLOAKBROWSER_AUTO_UPDATE=false`（库只认小写字面量 `"false"`，`False`/`0`/`no` 均无效），且在 `import cloakbrowser` 之前设置；不得调用 `check_for_update()`；不得让 `uv sync --upgrade` 影响该依赖版本。
- 每店固定出口：CloakBrowser 启动时必须继续传该店代理，**不得**因为换浏览器而改变出口语义。
- 不伪造会话级身份：同一店铺的 seed 永远不变；不同店铺的 seed 必须不同。

## Review Focus

- **seed 文件损坏或越界**（如被手工改成 `abc` 或 `1`）——应当自动重建为合法值而不是崩溃或沿用非法值。
- **profile 目录只读**——写入 `.cloak-seed` 失败时应给出可读错误，而不是静默用随机值（否则身份不稳定）。
- **cloakbrowser 未安装**——导入失败时应落到系统浏览器或给出明确提示，不能让整个登录流程不可用。
- **代理参数格式**——`playwright_proxy()` 返回 dict，CloakBrowser 的 `proxy` 参数同时接受字符串与 dict，需确保 dict 形式被正确透传。
- **headless 与窗口尺寸**——CloakBrowser 文档指出有头模式下不要叠 viewport，否则 outerWidth/innerWidth 不自洽。
- **自动更新被无意开启**——环境变量若写成 `False` / `0` / `no`，库只认小写字面量 `"false"`，两个后台更新线程会照常启动，可能在用户不知情时换掉二进制或包装版本。

---

### Task 1: 指纹种子管理

**Files:**
- Create: `backend/app/shared/cloak.py`
- Test: `backend/tests/shared/cloak_test.py`

**Interfaces:**
- Produces:
  - `SEED_MIN: int = 10_000`
  - `SEED_MAX: int = 99_999`
  - `get_or_create_seed(profile_dir: Path) -> int`
  - `cloak_launch_args(seed: int) -> list[str]`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/shared/cloak_test.py`：

```python
"""CloakBrowser 指纹种子：每店固定、越界重建、不可写时抛错。"""

import pytest

from app.shared.cloak import SEED_MAX, SEED_MIN, cloak_launch_args, get_or_create_seed


def test_creates_seed_once_and_reuses_it(tmp_path):
    first = get_or_create_seed(tmp_path)
    second = get_or_create_seed(tmp_path)

    assert first == second
    assert SEED_MIN <= first <= SEED_MAX


def test_rebuilds_out_of_range_seed(tmp_path):
    (tmp_path / ".cloak-seed").write_text("5", encoding="ascii")

    seed = get_or_create_seed(tmp_path)

    assert SEED_MIN <= seed <= SEED_MAX
    assert (tmp_path / ".cloak-seed").read_text(encoding="ascii").strip() == str(seed)


def test_rebuilds_garbage_seed(tmp_path):
    (tmp_path / ".cloak-seed").write_text("not-a-number", encoding="ascii")

    seed = get_or_create_seed(tmp_path)

    assert SEED_MIN <= seed <= SEED_MAX


def test_two_profiles_get_different_seeds(tmp_path):
    a = get_or_create_seed(tmp_path / "1")
    b = get_or_create_seed(tmp_path / "2")

    assert a != b


def test_launch_args_contains_fixed_fingerprint():
    assert cloak_launch_args(12345) == [
        "--fingerprint=12345",
        "--fingerprint-platform=windows",
    ]


def test_raises_when_profile_not_writable(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)

    try:
        with pytest.raises(OSError):
            get_or_create_seed(ro)
    finally:
        ro.chmod(0o700)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/shared/cloak_test.py -q`
Expected: `ModuleNotFoundError: No module named 'app.shared.cloak'`

- [ ] **Step 3: 写最小实现**

创建 `backend/app/shared/cloak.py`：

```python
"""CloakBrowser 指纹种子：每店一个固定值，首次生成后永久复用。

种子决定 CloakBrowser 生成的整套指纹（硬件并发、内存、屏幕、窗口、GPU 等）。
固定种子 = 该店铺永远呈现同一台设备，与「每店固定出口 IP」是同一个思路。
"""

import random
from pathlib import Path

SEED_FILE = ".cloak-seed"
SEED_MIN = 10_000
SEED_MAX = 99_999


def get_or_create_seed(profile_dir: Path) -> int:
    """读取该 profile 的固定指纹种子；缺失或非法时生成并落盘。

    profile 目录不可写时抛 OSError——调用方应据此报错，而不是静默换随机值，
    否则同一店铺的身份会在每次启动时变化。
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    path = profile_dir / SEED_FILE
    if path.is_file():
        text = path.read_text(encoding="ascii", errors="ignore").strip()
        if text.isdigit() and SEED_MIN <= int(text) <= SEED_MAX:
            return int(text)

    seed = random.randint(SEED_MIN, SEED_MAX)
    path.write_text(str(seed), encoding="ascii")
    return seed


def cloak_launch_args(seed: int) -> list[str]:
    """CloakBrowser 启动参数：固定指纹 + 声称 Windows 平台。"""
    return [f"--fingerprint={seed}", "--fingerprint-platform=windows"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/shared/cloak_test.py -q`
Expected: 6 passed

若 `test_raises_when_profile_not_writable` 在 Windows 上因权限模型不同而未抛错，改为对该用例加 `@pytest.mark.skipif(sys.platform == "win32", reason="Windows 目录只读语义不同于 POSIX")`，并在实现里保留 `OSError` 传播。

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/shared/cloak.py tests/shared/cloak_test.py
git commit -m "feat(cloak): 每店固定指纹种子管理"
```

---

### Task 2: 配置项

**Files:**
- Modify: `backend/app/config.py:18-24`（Settings 字段区）
- Modify: `backend/app/config.py:47-55`（`__init__` 默认值区）
- Test: `backend/tests/config_test.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `Settings.use_cloak: bool`（默认 `True`）
  - `Settings.cloak_cache_dir: Path`（默认 `<data_dir>/browser`）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/config_test.py` 末尾追加：

```python
def test_cloak_defaults(tmp_path):
    s = Settings(_platform="win32", data_dir=tmp_path)

    assert s.use_cloak is True
    assert s.cloak_cache_dir == tmp_path / "browser"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/config_test.py::test_cloak_defaults -q`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'use_cloak'`

- [ ] **Step 3: 写实现**

在 `backend/app/config.py` 的 Settings 字段区（`browser_channel` 之后）加：

```python
    use_cloak: bool = True
    cloak_cache_dir: Path = Path()
```

在 `__init__` 里 `data_dir` 解析之后加：

```python
        if "cloak_cache_dir" not in self.model_fields_set:
            self.cloak_cache_dir = self.data_dir / "browser"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/config_test.py -q`
Expected: 全部通过（含原有 `test_browser_channel_default`）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/config.py tests/config_test.py
git commit -m "feat(config): 增加 CloakBrowser 开关与二进制缓存目录"
```

---

### Task 3: 登录适配器支持双通道

**Files:**
- Modify: `backend/app/adapter/browser/login.py:120-140`（`scan_login`）
- Modify: `backend/app/adapter/browser/login.py:1-30`（imports）
- Test: `backend/tests/adapter/cloak_launch_test.py`（新建）

**Interfaces:**
- Consumes: `get_or_create_seed`, `cloak_launch_args`（Task 1）
- Produces: `build_cloak_kwargs(profile_dir: Path, proxy: dict | None) -> dict`
- Produces: `scan_login(profile_dir, channel, proxy, timeout_s=300, use_cloak=False)`（新增末位参数）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/adapter/cloak_launch_test.py`：

```python
"""CloakBrowser 启动参数构造：不真正启动浏览器，只验证参数形态。"""

from app.adapter.browser.login import build_cloak_kwargs
from app.shared.cloak import SEED_MAX, SEED_MIN


def test_build_cloak_kwargs_carries_fingerprint(tmp_path):
    kwargs = build_cloak_kwargs(tmp_path, None)

    assert kwargs["user_data_dir"] == str(tmp_path)
    assert kwargs["headless"] is False
    assert kwargs["proxy"] is None
    seed_arg = kwargs["args"][0]
    assert seed_arg.startswith("--fingerprint=")
    assert SEED_MIN <= int(seed_arg.split("=")[1]) <= SEED_MAX


def test_build_cloak_kwargs_passes_proxy_dict_through(tmp_path):
    proxy = {"server": "http://1.2.3.4:8080", "username": "u", "password": "p"}

    kwargs = build_cloak_kwargs(tmp_path, proxy)

    assert kwargs["proxy"] == proxy


def test_build_cloak_kwargs_is_stable_across_calls(tmp_path):
    first = build_cloak_kwargs(tmp_path, None)["args"]
    second = build_cloak_kwargs(tmp_path, None)["args"]

    assert first == second


def test_scan_login_reports_missing_package(monkeypatch, tmp_path):
    """cloakbrowser 未安装时必须给出可执行的提示，而不是裸 ImportError。"""
    import asyncio
    import sys

    import pytest

    import app.adapter.browser.login as login_mod

    monkeypatch.setitem(sys.modules, "cloakbrowser", None)

    with pytest.raises(RuntimeError, match="cloakbrowser"):
        asyncio.run(login_mod.scan_login(tmp_path, "chrome", None, use_cloak=True))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/adapter/cloak_launch_test.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_cloak_kwargs'`

- [ ] **Step 3: 写实现**

在 `backend/app/adapter/browser/login.py` 的 imports 区加：

```python
from app.shared.cloak import cloak_launch_args, get_or_create_seed
```

在 `scan_login` 之前加：

```python
def build_cloak_kwargs(profile_dir: Path, proxy: dict | None) -> dict:
    """CloakBrowser 启动参数。proxy 已由 playwright_proxy() 转成 dict。

    有头模式下不叠加 viewport：CloakBrowser 的屏幕/窗口尺寸由种子派生，
    额外指定 viewport 会破坏 outerWidth >= innerWidth 的自洽性。
    """
    return {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "proxy": proxy,
        "args": cloak_launch_args(get_or_create_seed(profile_dir)),
    }
```

把 `scan_login` 改成：

```python
async def scan_login(
    profile_dir: Path, channel: str, proxy: str | None, timeout_s: int = 300,
    use_cloak: bool = False,
) -> LoginResult:
    """打开订单页等待人工扫码。超时抛 TimeoutError，关窗抛 LoginCancelled。

    use_cloak 为真时走 CloakBrowser 定制 Chromium（每店固定指纹）；
    否则用系统浏览器（channel 指定）。
    """
    playwright_proxy_value = playwright_proxy(proxy)
    if use_cloak:
        try:
            from cloakbrowser import launch_persistent_context_async
        except ImportError as exc:
            raise RuntimeError(
                "未安装 cloakbrowser，请先执行：pip install cloakbrowser==0.3.30"
            ) from exc

        ctx = await launch_persistent_context_async(
            **build_cloak_kwargs(profile_dir, playwright_proxy_value),
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            token, headers, cookies = await await_login(ctx, page, timeout_s)
        finally:
            try:
                await ctx.close()
            except Exception:  # noqa: BLE001 - 用户已关窗时 close 会报错
                pass
        return LoginResult(cookies, token, session_expiry(cookies, datetime.now(UTC)), headers)

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(profile_dir), channel=channel, headless=False, proxy=playwright_proxy_value,
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            token, headers, cookies = await await_login(ctx, page, timeout_s)
        finally:
            try:
                await ctx.close()
            except Exception:  # noqa: BLE001 - 用户已关窗时 close 会报错
                pass
    return LoginResult(cookies, token, session_expiry(cookies, datetime.now(UTC)), headers)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/adapter/cloak_launch_test.py -q`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/adapter/browser/login.py tests/adapter/cloak_launch_test.py
git commit -m "feat(browser): 登录通道支持 CloakBrowser"
```

---

### Task 4: 服务层与接线

**Files:**
- Modify: `backend/app/service/shop_login.py:20-25,28-60`（`_USER_FACING` + 构造与 `profile` 生成）
- Modify: `backend/app/wiring.py:112-116`（`login_flow` 构造）
- Modify: `backend/app/main.py:70-82`（启动时设 CloakBrowser 环境变量）
- Modify: `backend/app/shared/cloak.py`（追加 `apply_env`）
- Modify: `backend/app/adapter/browser/login.py`（新增 `CloakUnavailable` 领域异常）
- Test: `backend/tests/service/shop_login_flow_test.py`（新建）
- Test: `backend/tests/shared/cloak_test.py`（追加 `apply_env` 测试）

**Interfaces:**
- Consumes: `scan_login(..., use_cloak=...)`（Task 3）、`Settings.use_cloak` / `Settings.cloak_cache_dir`（Task 2）
- Produces: `ShopLoginFlow(..., use_cloak: bool = False)`

- [ ] **Step 1: 写失败测试**

新建或追加 `backend/tests/service/shop_login_flow_test.py`：

```python
"""ShopLoginFlow 把 use_cloak 透传给 scan_login。"""

import inspect

from app.service.shop_login import ShopLoginFlow


def test_flow_accepts_use_cloak_flag():
    params = inspect.signature(ShopLoginFlow.__init__).parameters

    assert "use_cloak" in params
    assert params["use_cloak"].default is False


def test_cloak_unavailable_is_user_facing():
    """CloakBrowser 不可用的提示必须能出现在用户可见的错误里，否则安装提示被吞成「登录失败」。"""
    from app.adapter.browser.login import CloakUnavailable
    from app.service.shop_login import _USER_FACING

    assert CloakUnavailable in _USER_FACING


def test_scan_job_passes_use_cloak_and_proxy_to_scanner(tmp_path):
    """接线行为测试：use_cloak 与店铺代理必须真的到达扫码函数，不能只靠签名检查。"""
    import asyncio

    from app.adapter.browser.login import LoginResult

    calls: list[dict] = []

    async def fake_scan(profile, channel, proxy, timeout_s, use_cloak=False):
        calls.append({"proxy": proxy, "use_cloak": use_cloak})
        return LoginResult(
            cookies=[], token="tok", expires_at="2030-01-01T00:00:00Z", device_headers={},
        )

    class FakeRunner:
        def proxy_for(self, shop_id):
            return "http://user:pass@1.2.3.4:8080"

    class FakeSessions:
        def save_login(self, shop_id, result):
            pass

    flow = ShopLoginFlow(
        FakeRunner(), FakeSessions(), None, None, tmp_path, "chrome",
        scan=fake_scan, use_cloak=True,
    )
    asyncio.run(flow._scan_job(1)(None))

    assert len(calls) == 1
    assert calls[0]["use_cloak"] is True
    assert calls[0]["proxy"] == "http://user:pass@1.2.3.4:8080"
```

在 `backend/tests/shared/cloak_test.py` 末尾追加（并把 `apply_env` 加入该文件顶部的 import）：

```python
def test_apply_env_pins_cache_dir_and_disables_auto_update(monkeypatch, tmp_path):
    import os

    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_AUTO_UPDATE", raising=False)

    apply_env(tmp_path)

    assert os.environ["CLOAKBROWSER_CACHE_DIR"] == str(tmp_path)
    assert os.environ["CLOAKBROWSER_AUTO_UPDATE"] == "false"


def test_apply_env_forces_auto_update_off_even_if_preset(monkeypatch, tmp_path):
    """禁用自动更新是硬约束：外部把它设成 true，调用后也必须变 false。"""
    import os

    monkeypatch.setenv("CLOAKBROWSER_AUTO_UPDATE", "true")

    apply_env(tmp_path)

    assert os.environ["CLOAKBROWSER_AUTO_UPDATE"] == "false"


def test_apply_env_keeps_explicit_cache_dir(monkeypatch, tmp_path):
    """缓存目录是用户可配置项，显式设置必须被尊重。"""
    import os

    custom = str(tmp_path / "custom")
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", custom)

    apply_env(tmp_path)

    assert os.environ["CLOAKBROWSER_CACHE_DIR"] == custom
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/service/shop_login_flow_test.py -q`
Expected: FAIL — `assert 'use_cloak' in params`

- [ ] **Step 3: 写实现**

`backend/app/adapter/browser/login.py` 在 `LoginResult` 定义之后加：

```python
class CloakUnavailable(RuntimeError):
    """CloakBrowser 不可用（未安装或启动失败）；消息面向用户，可直接展示。"""
```

把 `scan_login` 里的 `raise RuntimeError(...)` 改为 `raise CloakUnavailable(...)`。它继承 `RuntimeError`，所以 Task 3 已有的 `pytest.raises(RuntimeError, match="cloakbrowser")` 仍然通过，无需改那条测试。

`backend/app/service/shop_login.py` 顶部把 `CloakUnavailable` 加进 `app.adapter.browser.login` 的 import，并把 `_USER_FACING` 补上它：

```python
_USER_FACING = (DoudianError, EgressNotReady, EgressConflict, ShopPaused, NotFound,
                LoginCancelled, CloakUnavailable)
```

`backend/app/service/shop_login.py` 构造函数签名末尾加 `use_cloak: bool = False`，保存为 `self._use_cloak = use_cloak`；调用 `scan_login(...)` 处传 `use_cloak=self._use_cloak`。

`backend/app/wiring.py` 的 `login_flow` 构造改为：

```python
        "login_flow": ShopLoginFlow(
            runner, sessions, base_data, events, settings.profiles_dir,
            settings.browser_channel, use_cloak=settings.use_cloak, **login_kw,
        ),
```

`backend/app/shared/cloak.py` 追加：

```python
def apply_env(cache_dir: Path) -> None:
    """把 CloakBrowser 的缓存目录锁到项目内，并**强制**关闭全部自动更新。

    CLOAKBROWSER_AUTO_UPDATE 无条件写小写字面量 "false"：禁用自动更新是硬约束，
    外部环境变量不得覆盖——库只在值为 false 时才跳过「二进制更新」和「PyPI 包
    更新」两个后台检查。必须在 import cloakbrowser 之前调用。

    缓存目录用 setdefault：那是用户可配置项，显式设置应当被尊重。
    """
    os.environ.setdefault("CLOAKBROWSER_CACHE_DIR", str(cache_dir))
    os.environ["CLOAKBROWSER_AUTO_UPDATE"] = "false"
```

`backend/app/main.py` 的 `lifespan` 开头（`settings.data_dir.mkdir` 之后）加：

```python
        apply_env(settings.cloak_cache_dir)
```

并在 imports 区补 `from app.shared.cloak import apply_env`。

- [ ] **Step 4: 跑全量后端测试**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: 全部通过（当前基线 653 passed, 1 skipped）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/service/shop_login.py app/wiring.py app/main.py tests/service/shop_login_flow_test.py
git commit -m "feat(login): 接线 CloakBrowser 开关与二进制缓存目录"
```

---

### Task 5: 依赖与文档

**Files:**
- Modify: `backend/pyproject.toml`（dependencies）
- Modify: `docs/engineering-rules.md:214`
- Modify: `docs/gaps.md`（DEC-11 行）
- Modify: `docs/design/backend.md:410`（出口方式行附近）

**Interfaces:**
- Consumes: 无
- Produces: 无（纯配置与文档）

- [ ] **Step 1: 钉版本**

在 `backend/pyproject.toml` 的 `dependencies` 数组中加入（保持与其他依赖同样的引号与缩进风格）：

```toml
    "cloakbrowser==0.3.30",
```

- [ ] **Step 2: 安装并验证版本**

Run: `cd backend && uv pip install cloakbrowser==0.3.30 && .venv/Scripts/python.exe -c "import cloakbrowser; print(cloakbrowser.CHROMIUM_VERSION)"`
Expected: `146.0.7680.177.5`

- [ ] **Step 3: 更新规范**

`docs/engineering-rules.md:214` 的「禁止伪造设备指纹」改为：

```
- **每店固定指纹**（design/backend.md 5.17）：浏览器统一使用 CloakBrowser 定制 Chromium；每店一个固定指纹种子（`profiles/<shop_id>/.cloak-seed`），跨会话不变；**禁止轮换指纹种子**（同一店铺不得在会话间改变设备身份）
```

`docs/gaps.md` 的 DEC-11 行补一句：

```
2026-11-26 追加：浏览器统一改为 CloakBrowser 定制 Chromium（Chromium 146，免费版无 license）；每店固定指纹种子，不轮换。
```

`docs/design/backend.md` 5.17 表格中「出口方式」行下方新增一行：

```
| 浏览器 | 统一使用 CloakBrowser 定制 Chromium（`cloakbrowser==0.3.30`，Chromium 146）；二进制缓存在 `<data_dir>/browser/`；每店固定指纹种子存 `profiles/<shop_id>/.cloak-seed` |
```

- [ ] **Step 4: 提交**

```bash
git add backend/pyproject.toml docs/engineering-rules.md docs/gaps.md docs/design/backend.md
git commit -m "docs: 浏览器改为 CloakBrowser 固定指纹（更新 DEC-11）"
```

---

### Task 6: 端到端验证

**Files:** 无代码改动（人工验证）

**Interfaces:**
- Consumes: 全部前序任务
- Produces: 验证结论

详细步骤见 `.superpowers/sdd/2026-11-26-cloakbrowser-integration/task-6-checklist.md`，共 6 步：二进制下载到项目目录 → 重启服务 → 扫码登录 → 指纹稳定 → **出口 IP 验证** → 记录结果。

（该清单原在本文档内，因本文件触发 `docs/*.md` 600 行硬上限而移出，要求与内容不变。）

---

## 后续可选项（不在本计划范围）

- **离线安装**：把 `%LOCALAPPDATA%\doudian-multishop\browser\` 打进安装包，避免首次下载。当前默认走自动下载。
- **升级通道**：`cloakbrowser` 0.4+ 起引入 Pro license。若将来需要更新反检测能力，需另行评估 Pro 订阅。
