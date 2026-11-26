"""飞鸽常驻页的组装与启停顺序：共用登记表、让出钩子、启动清理做完才开、退出时最先关。"""

import asyncio
import threading
import time

from fastapi.testclient import TestClient

from app.adapter.flybird.page import ImPage
from app.config import Settings
from app.main import create_app
from app.service.background import TaskRegistry
from app.service.im_watcher import ImWatcher
from app.service.notification_feed import NotificationFeed
from app.wiring import Overrides, build_services
from tests.api.browser_upkeep_test import FakeBrowsers
from tests.conftest import FAST_HASHER

BASE_URL = "http://127.0.0.1:8787"


def settings_in(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data", frontend_dist=tmp_path / "no-dist")


def wait_for(condition, timeout: float = 3.0) -> None:
    end = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < end, "等待条件超时"
        time.sleep(0.005)


def test_wiring_connects_watcher(tmp_path, clock):
    browsers = FakeBrowsers()
    settings = settings_in(tmp_path)
    app = create_app(settings, clock=clock, hasher=FAST_HASHER, browsers=browsers)
    with TestClient(app, base_url=BASE_URL):
        im = app.state.im
        assert im._browsers is browsers
        assert im._runner is app.state.runner
        assert im._profiles_dir == settings.profiles_dir
        assert im._slots._value == settings.im_max_browsers
        assert im._attach == ImPage.attach
        assert im._clock is clock
        assert app.state.login_flow._yield_profile == im.yield_profile
        assert app.state.shop_profile._yield_profile == im.yield_profile


def test_attach_can_be_overridden(engine, tmp_path):
    async def attach(context, **_callbacks):
        raise AssertionError("不打开页面")

    services = build_services(settings_in(tmp_path), engine, Overrides(im_attach=attach))

    assert services["im"]._attach is attach


def test_start_after_cleanup_and_feed_stop_before_tasks_and_browsers(
    tmp_path, clock, monkeypatch
):
    release = threading.Event()
    calls: list[str] = []

    class Browsers(FakeBrowsers):
        async def startup_cleanup(self, profiles_dir):
            await asyncio.to_thread(release.wait, 5)
            calls.append("cleaned")

        async def close_all(self, reason):
            calls.append("close_all")

    async def feed_run(_self, _bus, stop):
        calls.append("feed_run")
        await stop.wait()

    async def im_run(_self, bus, stop):
        calls.append("im_run")
        assert bus is app.state.events
        await stop.wait()

    async def im_shutdown(_self):
        calls.append("im_shutdown")

    async def tasks_shutdown(_self):
        calls.append("tasks_shutdown")

    monkeypatch.setattr(NotificationFeed, "run", feed_run)
    monkeypatch.setattr(ImWatcher, "run", im_run)
    monkeypatch.setattr(ImWatcher, "shutdown", im_shutdown)
    monkeypatch.setattr(TaskRegistry, "shutdown", tasks_shutdown)
    app = create_app(settings_in(tmp_path), clock=clock, hasher=FAST_HASHER, browsers=Browsers())

    with TestClient(app, base_url=BASE_URL) as client:
        assert client.get("/api/health").status_code == 200
        time.sleep(0.05)
        assert "im_run" not in calls  # 启动清理还没做完
        release.set()
        wait_for(lambda: "im_run" in calls)

    assert calls == [
        "feed_run", "cleaned", "im_run", "im_shutdown", "tasks_shutdown", "close_all"]


def test_watcher_starts_even_if_startup_cleanup_fails(tmp_path, clock, monkeypatch):
    calls: list[str] = []

    class Browsers(FakeBrowsers):
        async def startup_cleanup(self, profiles_dir):
            raise OSError("cleanup failed")

    async def im_run(_self, _bus, stop):
        calls.append("im_run")
        await stop.wait()

    monkeypatch.setattr(ImWatcher, "run", im_run)
    app = create_app(settings_in(tmp_path), clock=clock, hasher=FAST_HASHER, browsers=Browsers())

    with TestClient(app, base_url=BASE_URL):
        wait_for(lambda: calls == ["im_run"])


def test_exit_during_cleanup_never_starts_watcher(tmp_path, clock, monkeypatch):
    release = threading.Event()
    calls: list[str] = []

    class Browsers(FakeBrowsers):
        async def startup_cleanup(self, profiles_dir):
            await asyncio.to_thread(release.wait, 5)

    async def im_run(_self, _bus, _stop):
        calls.append("im_run")

    monkeypatch.setattr(ImWatcher, "run", im_run)
    app = create_app(settings_in(tmp_path), clock=clock, hasher=FAST_HASHER, browsers=Browsers())

    with TestClient(app, base_url=BASE_URL):
        # 退出开始之后才放行清理
        threading.Timer(0.2, release.set).start()

    assert calls == []
