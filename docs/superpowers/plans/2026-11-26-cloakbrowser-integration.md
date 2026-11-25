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
- 每店固定出口：CloakBrowser 启动时必须继续传该店代理，**不得**因为换浏览器而改变出口语义。
- 不伪造会话级身份：同一店铺的 seed 永远不变；不同店铺的 seed 必须不同。

## Review Focus

- **seed 文件损坏或越界**（如被手工改成 `abc` 或 `1`）——应当自动重建为合法值而不是崩溃或沿用非法值。
- **profile 目录只读**——写入 `.cloak-seed` 失败时应给出可读错误，而不是静默用随机值（否则身份不稳定）。
- **cloakbrowser 未安装**——导入失败时应落到系统浏览器或给出明确提示，不能让整个登录流程不可用。
- **代理参数格式**——`playwright_proxy()` 返回 dict，CloakBrowser 的 `proxy` 参数同时接受字符串与 dict，需确保 dict 形式被正确透传。
- **headless 与窗口尺寸**——CloakBrowser 文档指出有头模式下不要叠 viewport，否则 outerWidth/innerWidth 不自洽。

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
- Modify: `backend/app/service/shop_login.py:28-60`（构造与 `profile` 生成）
- Modify: `backend/app/wiring.py:112-116`（`login_flow` 构造）
- Modify: `backend/app/main.py:70-82`（启动时设 `CLOAKBROWSER_CACHE_DIR`）
- Test: `backend/tests/service/shop_login_flow_test.py`（若已存在则追加）

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/service/shop_login_flow_test.py -q`
Expected: FAIL — `assert 'use_cloak' in params`

- [ ] **Step 3: 写实现**

`backend/app/service/shop_login.py` 构造函数签名末尾加 `use_cloak: bool = False`，保存为 `self._use_cloak = use_cloak`；调用 `scan_login(...)` 处传 `use_cloak=self._use_cloak`。

`backend/app/wiring.py` 的 `login_flow` 构造改为：

```python
        "login_flow": ShopLoginFlow(
            runner, sessions, base_data, events, settings.profiles_dir,
            settings.browser_channel, use_cloak=settings.use_cloak, **login_kw,
        ),
```

`backend/app/main.py` 的 `lifespan` 开头（`settings.data_dir.mkdir` 之后）加：

```python
        os.environ.setdefault("CLOAKBROWSER_CACHE_DIR", str(settings.cloak_cache_dir))
```

并在文件顶部补 `import os`（若无）。

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

**Files:**
- 无代码改动（人工验证）

**Interfaces:**
- Consumes: 全部前序任务
- Produces: 验证结论，记录到本计划的「验证结果」小节

- [ ] **Step 1: 确认二进制会被下载到项目目录**

Run: `cd backend && .venv/Scripts/python.exe -c "import os; os.environ['CLOAKBROWSER_CACHE_DIR']=r'%LOCALAPPDATA%\doudian-multishop\browser'; import cloakbrowser; print(cloakbrowser.ensure_binary())"`
Expected: 输出路径以 `doudian-multishop\browser\chromium-146` 开头（首次运行会下载约 200MB）

- [ ] **Step 2: 重启服务**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1`
Expected: `已启动（PID …）`

- [ ] **Step 3: 触发扫码登录**

在界面「店铺管理」点「扫码登录」，确认：
- 弹出的是 CloakBrowser（窗口标题与图标非系统 Chrome）
- `%LOCALAPPDATA%\doudian-multishop\profiles\1\.cloak-seed` 已生成
- 登录成功后 `cookies` 表有记录

- [ ] **Step 4: 验证指纹稳定**

关闭后再次触发登录，确认 `.cloak-seed` **内容未变**，且浏览器指纹（`navigator.hardwareConcurrency`、WebGL renderer）与首次一致。

- [ ] **Step 5: 记录结果**

在本计划末尾追加「验证结果」小节，写明：二进制路径、seed 值是否稳定、指纹是否一致、遇到的偏差。

---

## 验证结果

（Task 6 完成后填写）

---

## 后续可选项（不在本计划范围）

- **离线安装**：把 `%LOCALAPPDATA%\doudian-multishop\browser\` 打进安装包，避免首次下载。当前默认走自动下载。
- **升级通道**：`cloakbrowser` 0.4+ 起引入 Pro license。若将来需要更新反检测能力，需另行评估 Pro 订阅。
