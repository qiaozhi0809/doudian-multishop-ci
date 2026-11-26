from datetime import UTC, datetime

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store.db import make_engine
from app.store.migrate import upgrade_to_head

ADMIN_USER = "admin"
ADMIN_PASSWORD = "pw_" + "x" * 8
FAST_HASHER = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)  # 测试用，加快哈希


class FakeClock:
    """可调的时钟，供需要控制时间的测试使用。"""

    def __init__(self) -> None:
        self.now = datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture(autouse=True)
def _isolated_browsers(monkeypatch):
    """每个测试一张新的浏览器登记表，配空进程表：不共享状态，不碰本机真实进程。"""
    import app.adapter.browser.browser_registry as browser_registry
    import app.wiring as wiring
    from app.adapter.browser.browser_registry import BrowserRegistry
    from tests.fakes import NullProcesses

    registry = BrowserRegistry(NullProcesses())
    monkeypatch.setattr(browser_registry, "REGISTRY", registry)
    monkeypatch.setattr(wiring, "REGISTRY", registry)
    return registry


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def app(tmp_path, clock):
    # frontend_dist 指向不存在的目录：测试结果不受本机是否构建过前端影响
    settings = Settings(data_dir=tmp_path / "data", frontend_dist=tmp_path / "no-dist")
    return create_app(settings, clock=clock, hasher=FAST_HASHER)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://127.0.0.1:8787") as c:
        yield c


@pytest.fixture
def logged_in_client(client):
    """已创建管理员并登录的客户端（Cookie 保存在客户端里）。"""
    assert client.post("/api/auth/setup", json={
        "username": ADMIN_USER, "password": ADMIN_PASSWORD}).status_code == 201
    assert client.post("/api/auth/login", json={
        "username": ADMIN_USER, "password": ADMIN_PASSWORD}).status_code == 200
    return client


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "app.db"
    upgrade_to_head(db)
    eng = make_engine(db)
    yield eng
    eng.dispose()
