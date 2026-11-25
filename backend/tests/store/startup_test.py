from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_startup_creates_data_dir(tmp_path):
    data_dir = tmp_path / "not" / "yet"
    assert not data_dir.exists()
    with TestClient(create_app(Settings(data_dir=data_dir)), base_url="http://127.0.0.1:8787"):
        assert (data_dir / "app.db").is_file()


def test_lifespan_wires_services_and_shuts_down_cleanly(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data"))
    with TestClient(app, base_url="http://127.0.0.1:8787"):
        for name in ("engine", "events", "sessions", "egress", "runner", "base_data", "order_sync"):
            assert hasattr(app.state, name)


def test_startup_pins_cloak_env(tmp_path, monkeypatch):
    """lifespan 必须强制关掉 CloakBrowser 自动更新，并把缓存目录指到项目内。"""
    import os

    # 先清空，否则前序测试泄漏的值会让本测试在 apply_env 被删掉时仍然假绿
    monkeypatch.delenv("CLOAKBROWSER_CACHE_DIR", raising=False)
    monkeypatch.delenv("CLOAKBROWSER_AUTO_UPDATE", raising=False)

    settings = Settings(data_dir=tmp_path / "data")
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8787"):
        assert os.environ["CLOAKBROWSER_AUTO_UPDATE"] == "false"
        assert os.environ["CLOAKBROWSER_CACHE_DIR"] == str(settings.cloak_cache_dir)
