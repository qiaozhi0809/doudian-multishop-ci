"""飞鸽适配器只读守卫：静态扫描 app/adapter/flybird 源码（实施计划 Global Constraints）。

不构造、不发送帧，不伪造请求，不输入内容；拦截只在 read_guard.py 且只丢弃，
点击与置前窗口只在 focus.py。
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "app" / "adapter" / "flybird"
WRITE_TOKENS = (
    ".send(", "encode", ".request.", "fetch(", ".fill(", ".type(", "keyboard",
    ".press(", ".dispatch_event(", "fulfill", "continue_",
)
ROUTE_TOKENS = (".route(", "add_init_script")
FOCUS_TOKENS = (".click(", "bring_to_front", "setWindowBounds")
ROUTE_MODULE = "read_guard.py"
FOCUS_MODULE = "focus.py"


def _sources() -> dict[str, str]:
    sources = {
        path.relative_to(PACKAGE).as_posix(): path.read_text(encoding="utf-8")
        for path in PACKAGE.rglob("*.py")
    }
    # 目录改名或扫空时守卫不得静默通过
    assert {"__init__.py", "endpoints.py", "parse.py"} <= sources.keys()
    return sources


def _hits(sources: dict[str, str], tokens: tuple[str, ...], *, allowed: str = "") -> list[str]:
    return [
        f"{name}: {token}"
        for name, text in sources.items() if name != allowed
        for token in tokens if token in text
    ]


def _handler_only_aborts(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """route 处理函数对 route 参数只做一件事：调用 abort()。"""
    params = [arg.arg for arg in function.args.args if arg.arg not in ("self", "cls")]
    if not params:
        return False
    abort_targets = {
        id(node.func.value)
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == "abort"
    }
    uses = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Name) and node.id == params[0]
    ]
    return bool(uses) and all(id(node) in abort_targets for node in uses)


def _route_violations(source: str) -> list[str]:
    """每个 `.route(...)` 的处理函数都必须是本模块里只调用 abort 的具名函数。"""
    tree = ast.parse(source)
    functions = {
        node.name: node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    violations = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "route"):
            continue
        handlers = node.args[1:2] + [k.value for k in node.keywords if k.arg == "handler"]
        handler = handlers[0] if handlers else None
        name = getattr(handler, "id", None) or getattr(handler, "attr", None)
        if name not in functions or not _handler_only_aborts(functions[name]):
            violations.append(f"第 {node.lineno} 行的 route 处理函数不是只调用 abort")
    return violations


def test_flybird_adapter_has_no_write_paths():
    assert _hits(_sources(), WRITE_TOKENS) == []


def test_route_only_in_read_guard():
    sources = _sources()
    assert _hits(sources, ROUTE_TOKENS, allowed=ROUTE_MODULE) == []
    if ROUTE_MODULE in sources:
        assert _route_violations(sources[ROUTE_MODULE]) == []


def test_click_only_in_focus_module():
    assert _hits(_sources(), FOCUS_TOKENS, allowed=FOCUS_MODULE) == []


# read_guard.py 由后续任务添加；先用样本源码确认检查本身能拦住违规写法
_INSTALL = "async def install(context):\n    await context.route('**/x*', {handler})\n"


def test_route_check_accepts_abort_only_handler():
    source = (
        "async def _abort(route):\n    global n\n    await route.abort()\n    n += 1\n"
        + _INSTALL.format(handler="_abort")
    )
    assert _route_violations(source) == []


@pytest.mark.parametrize("body", [
    "await route.fallback()",
    "await route.abort()\n    await route.fallback()",
    "await route.abort()\n    await forward(route)",
    "pass",
])
def test_route_check_rejects_other_handlers(body):
    source = f"async def _h(route):\n    {body}\n" + _INSTALL.format(handler="_h")
    assert len(_route_violations(source)) == 1


def test_route_check_rejects_unnamed_handler():
    source = _INSTALL.format(handler="lambda route: route.abort()")
    assert len(_route_violations(source)) == 1
