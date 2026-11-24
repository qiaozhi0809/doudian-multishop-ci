"""OpenAPI 导出，以及与前端手写契约（frontend/openapi.json）的兼容性。"""

import json
from pathlib import Path

import pytest

from app.config import REPO_ROOT, Settings
from app.main import create_app, export_openapi

FRONTEND_SPEC = REPO_ROOT / "frontend" / "openapi.json"


def test_export_is_deterministic_and_complete(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    export_openapi(a)
    export_openapi(b)
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
    spec = json.loads(a.read_text(encoding="utf-8"))
    assert {"/api/shops", "/api/shops/{shop_id}/egress/check", "/api/orders", "/api/events",
            "/api/auth/status", "/api/orders/sync"} <= set(spec["paths"])
    assert a.read_text(encoding="utf-8").endswith("}\n")


def test_every_api_operation_declares_the_error_envelope():
    spec = create_app(Settings()).openapi()
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert "default" in op["responses"], (method, path)


@pytest.mark.skipif(not FRONTEND_SPEC.is_file(), reason="前端契约文件不存在")
def test_backend_covers_frontend_contract():
    mine = create_app(Settings()).openapi()
    theirs = json.loads(FRONTEND_SPEC.read_text(encoding="utf-8"))
    for path, ops in theirs["paths"].items():
        for method, op in ops.items():
            assert method in mine["paths"].get(path, {}), (method, path)
            expected = {p["name"] for p in op.get("parameters", [])}
            actual = {p["name"] for p in mine["paths"][path][method].get("parameters", [])}
            assert expected <= actual, (method, path, expected - actual)
    for name, schema in theirs["components"]["schemas"].items():
        got = mine["components"]["schemas"].get(name)
        assert got is not None, f"后端缺少模型 {name}"
        assert set(schema["properties"]) <= set(got["properties"]), name  # 后端可以有更多可选字段
        assert set(schema.get("required", [])) == set(got.get("required", [])), name


def test_cli_entry_writes_file(tmp_path):
    import subprocess
    import sys

    target = tmp_path / "openapi.json"
    backend = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, "-m", "app.main", "--export-openapi", str(target)],
        cwd=backend, check=True,
    )
    assert json.loads(target.read_text(encoding="utf-8"))["info"]["title"]
