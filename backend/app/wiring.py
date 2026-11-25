"""服务组装：lifespan 里创建所有服务并挂到 app.state。测试可替换外部依赖。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from argon2 import PasswordHasher
from sqlalchemy import Engine

from app.config import Settings
from app.service.auth import AuthService
from app.service.background import TaskRegistry
from app.service.base_data import BaseDataService
from app.service.egress import EgressService
from app.service.egress_probe import FetchIp, make_fetch_ip
from app.service.events import EventBus
from app.service.order_query import OrderQueryService
from app.service.order_sync import OrderSyncService
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shop_admin import ShopAdminService
from app.service.shop_login import ScanFn, ShopLoginFlow
from app.service.shop_runner import ClientFactory, ShopRunner, default_client_factory
from app.shared.secret_box import make_secret_box


@dataclass
class Overrides:
    """测试用：替换时钟、哈希器、抖店客户端工厂、出口探测、扫码。"""

    clock: Callable[[], datetime] | None = None
    hasher: PasswordHasher | None = None
    client_factory: ClientFactory | None = None
    fetch_ip: FetchIp | None = None
    scan: ScanFn | None = None


def build_services(settings: Settings, engine: Engine, ov: Overrides) -> dict[str, Any]:
    box = make_secret_box(settings.data_dir)
    events = EventBus()
    clock_kw = {"clock": ov.clock} if ov.clock else {}
    sessions = SessionManager(engine, box, events, **clock_kw)
    egress = EgressService(
        engine, box, events, ov.fetch_ip or make_fetch_ip(settings.egress_echo_url), **clock_kw
    )
    runner = ShopRunner(
        engine, ShopScheduler(settings.max_concurrent_shops), egress, sessions,
        ov.client_factory or default_client_factory, **clock_kw,
    )
    base_data = BaseDataService(engine, runner, events)
    order_query = OrderQueryService(engine, runner, **clock_kw)
    login_kw = {"scan": ov.scan} if ov.scan else {}
    return {
        "engine": engine, "events": events, "sessions": sessions, "egress": egress,
        "runner": runner, "base_data": base_data, "tasks": TaskRegistry(),
        "order_sync": OrderSyncService(
            engine, runner, sessions, events, on_synced=order_query.invalidate),
        "order_query": order_query,
        "shop_admin": ShopAdminService(engine, events, **clock_kw),
        "login_flow": ShopLoginFlow(
            runner, sessions, base_data, events, settings.profiles_dir,
            settings.browser_channel, **login_kw,
        ),
        "auth": AuthService(
            engine, **clock_kw, **({"hasher": ov.hasher} if ov.hasher else {})
        ),
    }
