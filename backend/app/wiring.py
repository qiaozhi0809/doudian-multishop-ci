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
from app.service.backup import BackupService
from app.service.base_data import BaseDataService
from app.service.catalog import CatalogService
from app.service.egress import EgressService
from app.service.egress_probe import FetchIp, Probe, make_fetch_ip, make_probe
from app.service.events import EventBus
from app.service.fund import FundService
from app.service.label_pool import LabelPoolService
from app.service.label_preview import LabelPreviewService
from app.service.labeling import LabelingService
from app.service.notification_feed import NotificationFeed
from app.service.notifications import NotificationService
from app.service.order_query import OrderQueryService
from app.service.order_sync import OrderSyncService
from app.service.printing import PrintingService
from app.service.proxy_pool import ProxyPoolService
from app.service.receiver import ReceiverService
from app.service.reconcile import ReconcileService
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.ship_deadline import ShipDeadlineWatcher
from app.service.shipping import ShippingService
from app.service.shop_admin import ShopAdminService
from app.service.shop_login import ScanFn, ShopLoginFlow
from app.service.shop_profile import ShopProfileService
from app.service.shop_runner import ClientFactory, ShopRunner, default_client_factory
from app.shared.secret_box import make_secret_box


@dataclass
class Overrides:
    """测试用：替换时钟、哈希器、抖店客户端工厂、出口探测（fetch_ip / probe）、扫码、打印组件。"""

    clock: Callable[[], datetime] | None = None
    hasher: PasswordHasher | None = None
    client_factory: ClientFactory | None = None
    fetch_ip: FetchIp | None = None
    scan: ScanFn | None = None
    print_component: PrintComponent | None = None
    probe: Probe | None = None  # 放在末尾：测试按位置传参


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
    shop_profile = ShopProfileService(
        engine, runner, profiles_dir=settings.profiles_dir, **clock_kw)
    order_query = OrderQueryService(engine, runner, **clock_kw)
    login_kw = {"scan": ov.scan} if ov.scan else {}
    tasks = TaskRegistry()
    label_preview = LabelPreviewService(
        engine, dry_run=settings.dry_run, **clock_kw)
    notifications = NotificationService(engine, events, **clock_kw)
    return {
        "engine": engine, "events": events, "sessions": sessions, "egress": egress,
        "proxy_pool": ProxyPoolService(
            engine, box, events, ov.probe or make_probe(settings.egress_echo_url), **clock_kw),
        "runner": runner, "base_data": base_data, "shop_profile": shop_profile, "tasks": tasks,
        "order_sync": OrderSyncService(
            engine, runner, sessions, events, on_synced=order_query.invalidate),
        "order_query": order_query,
        # M5 只读聚合：售后 / 商品与库存 / 资金
        "aftersale": AftersaleService(engine, runner, events=events, **clock_kw),
        "catalog": CatalogService(engine, runner, events=events, **clock_kw),
        "fund": FundService(engine, runner, events=events, **clock_kw),
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
        "reconcile": ReconcileService(
            engine, runner, events, tasks=tasks,
            default_window_days=settings.reconcile_window_days, **clock_kw,
        ),
        # M7 打磨：备份 / 临近超时告警
        "backup": BackupService(
            engine, settings.backups_dir, keep=settings.backup_keep, **clock_kw),
        "ship_deadline": ShipDeadlineWatcher(
            engine, events, warn_hours=settings.ship_deadline_warn_hours, **clock_kw),
        # 通知中心：统一写入口 + 事件翻译（lifespan 里启动订阅循环）
        "notifications": notifications,
        "notification_feed": NotificationFeed(engine, notifications),
        "shop_admin": ShopAdminService(engine, events, egress, **clock_kw),
        "login_flow": ShopLoginFlow(
            runner, sessions, base_data, events, settings.profiles_dir,
            settings.browser_channel, use_cloak=settings.use_cloak,
            profile=shop_profile, **login_kw,
        ),
        "auth": AuthService(
            engine, **clock_kw, **({"hasher": ov.hasher} if ov.hasher else {})
        ),
    }
