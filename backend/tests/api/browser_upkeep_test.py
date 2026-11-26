"""后端启动时清理孤儿浏览器与残留锁，退出时关闭全部已登记浏览器。"""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import FAST_HASHER


class FakeBrowsers:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def startup_cleanup(self, profiles_dir):
        self.calls.append(("startup", profiles_dir))

    async def sweep(self, profiles_dir):
        self.calls.append(("sweep", profiles_dir))

    async def close_all(self, reason):
        self.calls.append(("close_all", reason))


def test_lifespan_cleans_up_on_start_and_closes_on_exit(tmp_path, clock):
    settings = Settings(data_dir=tmp_path / "data", frontend_dist=tmp_path / "no-dist")
    browsers = FakeBrowsers()
    app = create_app(settings, clock=clock, hasher=FAST_HASHER, browsers=browsers)
    with TestClient(app, base_url="http://127.0.0.1:8787") as client:
        assert client.get("/api/health").status_code == 200
        assert app.state.browsers is browsers
    assert browsers.calls[0] == ("startup", settings.profiles_dir)
    assert browsers.calls[-1] == ("close_all", "shutdown")
    assert ("sweep", settings.profiles_dir) not in browsers.calls  # 巡检要等满一个间隔
