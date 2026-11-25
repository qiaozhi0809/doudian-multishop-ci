"""服务组装：lifespan 里创建所有服务并挂到 app.state。测试可替换外部依赖。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from argon2 import PasswordHasher
from sqlalchemy import Engine

from app.adapter.print.component import PrintComponent
from app.config import Settings
from app.service.aftersale import AftersaleService
from app.service.auth import AuthService
from app.service.background import TaskRegistry
from app.service.base_data import BaseDataService
from app.service.catalog import CatalogService
from app.service.egress import EgressService
from app.service.egress_probe import FetchIp, make_fetch_ip
from app.service.events import EventBus
from app.service.fund import FundService
from app.service.label_pool import LabelPoolService
from app.service.label_preview import LabelPreviewService
from app.service.labeling import LabelingService
from app.service.order_query import OrderQueryService
from app.service.order_sync import OrderSyncService
from app.service.printing import PrintingService
from app.service.receiver import ReceiverService
from app.service.reconcile import ReconcileService
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shipping import ShippingService
from app.service.shop_admin import ShopAdminService
from app.service.shop_login import ScanFn, ShopLoginFlow
from app.service.shop_runner import ClientFactory, ShopRunner, default_client_factory
from app.shared.secret_box import make_secret_box


@dataclass
class Overrides:
    """测试用：替换时钟、哈希器、抖店客户端工厂、出口探测、扫码、打印组件。"""

    clock: Callable[[], datetime] | None = None
    hasher: PasswordHasher | None = None
    client_factory: ClientFactory | None = None
    fetch_ip: FetchIp | None = None
    scan: ScanFn | None = None
    print_component: PrintComponent | None = None


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
    tasks = TaskRegistry()
    label_preview = LabelPreviewService(
        engine, dry_run=settings.dry_run, **clock_kw)
    return {
        "engine": engine, "events": events, "sessions": sessions, "egress": egress,
        "runner": runner, "base_data": base_data, "tasks": tasks,
        "order_sync": OrderSyncService(
            engine, runner, sessions, events, on_synced=order_query.invalidate),
        "order_query": order_query,
        # M5 只读聚合：售后 / 商品与库存 / 资金
        "aftersale": AftersaleService(engine, runner, **clock_kw),
        "catalog": CatalogService(engine, runner, **clock_kw),
        "fund": FundService(engine, runner, **clock_kw),
        "label_preview": label_preview,
        "labeling": LabelingService(
            engine, runner, label_preview, events,
            printer_name=settings.printer_name, dry_run=settings.dry_run,
            tasks=tasks, **clock_kw,
        ),
        "label_pool": LabelPoolService(engine),
        "receiver": ReceiverService(engine, runner, **clock_kw),
        "printing": PrintingService(
            engine, runner, ov.print_component or PrintComponent(), events,
            dry_run=settings.dry_run, default_printer=settings.printer_name,
            tasks=tasks, **clock_kw,
        ),
        # M4 发货 + 对账
        "shipping": ShippingService(
            engine, runner, events, dry_run=settings.dry_run, tasks=tasks, **clock_kw,
        ),
        "reconcile": ReconcileService(engine, runner, events, tasks=tasks, **clock_kw),
        "shop_admin": ShopAdminService(engine, events, **clock_kw),
        "login_flow": ShopLoginFlow(
            runner, sessions, base_data, events, settings.profiles_dir,
            settings.browser_channel, **login_kw,
        ),
        "auth": AuthService(
            engine, **clock_kw, **({"hasher": ov.hasher} if ov.hasher else {})
        ),
    }
