"""OpenAPI 导出。frontend/openapi.json 由后端导出，CI 校验二者一致。"""

import json
from pathlib import Path

from app.config import Settings
from app.main import create_app, export_openapi


def test_export_is_deterministic_and_complete(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    export_openapi(a)
    export_openapi(b)
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
    spec = json.loads(a.read_text(encoding="utf-8"))
    assert {"/api/shops", "/api/proxy-pool", "/api/shops/{shop_id}/egress/check", "/api/orders",
            "/api/events", "/api/auth/status", "/api/orders/sync", "/api/im/status",
            "/api/im/shops/{shop_id}/restart", "/api/im/conversations",
            "/api/im/conversations/counts",
            "/api/im/conversations/{shop_id}/{conversation_id}/messages"} <= set(spec["paths"])
    assert a.read_text(encoding="utf-8").endswith("}\n")


def test_every_api_operation_declares_the_error_envelope():
    spec = create_app(Settings()).openapi()
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert "default" in op["responses"], (method, path)


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
