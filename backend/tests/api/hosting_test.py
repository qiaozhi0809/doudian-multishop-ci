import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import FAST_HASHER


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html>INDEX</html>", encoding="utf-8")
    (d / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (d / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")
    return d


def make_client(tmp_path, dist, **kw):
    app = create_app(Settings(data_dir=tmp_path / "data", frontend_dist=dist, **kw),
                     hasher=FAST_HASHER)
    return TestClient(app, base_url="http://127.0.0.1:8787")


def test_serves_index_assets_and_spa_fallback(tmp_path, dist):
    with make_client(tmp_path, dist) as c:
        assert "INDEX" in c.get("/").text
        assert "INDEX" in c.get("/orders").text  # 前端路由
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/favicon.svg").text == "<svg/>"


def test_api_paths_unaffected_and_unknown_api_is_json_404(tmp_path, dist):
    with make_client(tmp_path, dist) as c:
        assert c.get("/api/health").json() == {"status": "ok"}
        r = c.get("/api/does-not-exist")
        assert r.status_code == 401  # 未登录先挡住，不泄露哪些路径存在
        c.post("/api/auth/setup", json={"username": "a", "password": "p" * 8})
        c.post("/api/auth/login", json={"username": "a", "password": "p" * 8})
        r = c.get("/api/does-not-exist")
        assert r.status_code == 404 and r.json()["error"]["type"] == "NotFound"


def test_path_traversal_does_not_leak_files(tmp_path, dist):
    with make_client(tmp_path, dist) as c:
        r = c.get("/..%2Fsecret.txt")
        assert "outside" not in r.text
        r = c.get("/../secret.txt")
        assert "outside" not in r.text


def test_not_hosted_without_build_or_in_dev_mode(tmp_path, dist):
    with make_client(tmp_path, tmp_path / "missing") as c:
        assert c.get("/").status_code == 404
    with make_client(tmp_path, dist, dev_mode=True) as c:
        assert c.get("/").status_code == 404


def test_host_guard_still_applies_to_frontend(tmp_path, dist):
    with make_client(tmp_path, dist) as c:
        assert c.get("/", headers={"Host": "evil.example.com"}).status_code == 421
