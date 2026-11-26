"""应用工厂与启动流程。"""

import argparse
import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import structlog
from argon2 import PasswordHasher
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.adapter.print.component import PrintComponent
from app.api import aftersale as aftersale_api
from app.api import auth as auth_api
from app.api import backup as backup_api
from app.api import catalog as catalog_api
from app.api import event as event_api
from app.api import fund as fund_api
from app.api import label as label_api
from app.api import notification as notification_api
from app.api import order as order_api
from app.api import print as print_api
from app.api import proxy_pool as proxy_pool_api
from app.api import reconcile as reconcile_api
from app.api import shipping as shipping_api
from app.api import shop as shop_api
from app.api import system as system_api
from app.api.common_schemas import ErrorEnvelope, Health
from app.api.deps import require_admin
from app.api.errors import envelope, install_error_handlers
from app.api.host_guard import HostGuard, allowed_hosts
from app.config import Settings
from app.service.egress_probe import FetchIp, Probe
from app.service.periodic import (
    ORDER_SYNC_INTERVAL_S,
    PROBE_INTERVAL_S,
    SYSTEM_ACTOR,
    for_each_active_shop,
    probe_session,
    run_daily_at,
    run_every,
)
from app.service.shop_login import ScanFn
from app.service.shop_runner import ClientFactory
from app.shared.cloak import apply_env
from app.shared.version import APP_VERSION
from app.store import task_store
from app.store.db import DB_FILE_NAME, make_engine
from app.store.migrate import backup_before_upgrade, upgrade_to_head
from app.wiring import Overrides, build_services

log = structlog.get_logger()
ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_app(
    settings: Settings | None = None, *, clock: Callable[[], datetime] | None = None,
    hasher: PasswordHasher | None = None, client_factory: ClientFactory | None = None,
    fetch_ip: FetchIp | None = None, scan: ScanFn | None = None,
    print_component: PrintComponent | None = None, probe: Probe | None = None,
) -> FastAPI:
    settings = settings or Settings()
    overrides = Overrides(clock, hasher, client_factory, fetch_ip, scan, print_component, probe)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        apply_env(settings.cloak_cache_dir)
        db_path = settings.data_dir / DB_FILE_NAME
        backup = backup_before_upgrade(
            db_path, settings.backups_dir, (overrides.clock or _utc_now)())
        if backup is not None:
            log.info("db.pre_upgrade_backup", file=backup.name)
        upgrade_to_head(db_path)
        engine = make_engine(db_path)
        now_iso = (overrides.clock or _utc_now)().strftime(ISO_FMT)
        with engine.begin() as conn:  # backend 5.7：重启把 running 任务复位
            task_store.recover_after_restart(conn, now_iso)
        for name, service in build_services(settings, engine, overrides).items():
            setattr(app.state, name, service)
        app.state.clock = overrides.clock or _utc_now
        app.state.proxy_pool.rehash_legacy()  # 补算迁移留下的 legacy: identity

        stop = asyncio.Event()
        runner, order_sync = app.state.runner, app.state.order_sync
        probe_all = partial(for_each_active_shop, engine, partial(probe_session, runner))
        sync_all = partial(
            for_each_active_shop, engine, lambda sid: order_sync.sync_pending(sid, SYSTEM_ACTOR)
        )
        aftersale = app.state.aftersale
        aftersale_all = partial(  # 售后定时检查：每轮一次计数，变了才完整同步
            for_each_active_shop, engine, lambda sid: aftersale.check_new(sid, SYSTEM_ACTOR)
        )
        tasks = [
            asyncio.create_task(app.state.notification_feed.run(app.state.events, stop)),
            asyncio.create_task(run_every(PROBE_INTERVAL_S, probe_all, stop)),
            asyncio.create_task(run_every(ORDER_SYNC_INTERVAL_S, sync_all, stop)),
            asyncio.create_task(run_every(ORDER_SYNC_INTERVAL_S, aftersale_all, stop)),
            asyncio.create_task(run_every(
                settings.ship_deadline_scan_interval_s, _deadline_scan(app), stop)),
        ]
        if settings.reconcile_daily:
            tasks.append(asyncio.create_task(run_daily_at(
                settings.reconcile_hour,
                partial(app.state.reconcile.run_daily, SYSTEM_ACTOR), stop)))
        if settings.backup_daily:
            tasks.append(asyncio.create_task(run_daily_at(
                settings.backup_hour, _daily_backup(app), stop)))
        try:
            yield
        finally:
            stop.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await app.state.tasks.shutdown()
            engine.dispose()

    app = FastAPI(
        title="抖店多店铺管理 本地 API", version=APP_VERSION, lifespan=lifespan,
        dependencies=[Depends(require_admin)],
        responses={"default": {"model": ErrorEnvelope, "description": "错误信封"}},
    )
    app.add_middleware(HostGuard, hosts=allowed_hosts(settings.port, settings.dev_mode))
    install_error_handlers(app)
    app.state.settings = settings

    @app.get("/api/health", response_model=Health)
    async def health() -> Health:
        return Health(status="ok")

    for module in (
        auth_api, shop_api, proxy_pool_api, order_api, label_api, print_api, event_api,
        aftersale_api, catalog_api, fund_api, shipping_api, reconcile_api,
        backup_api, system_api, notification_api,
    ):
        app.include_router(module.router)
    _mount_frontend(app, settings)
    return app


def _deadline_scan(app: FastAPI) -> Callable[[], Awaitable[object]]:
    async def scan() -> object:
        return await asyncio.to_thread(app.state.ship_deadline.scan)

    return scan


def _daily_backup(app: FastAPI) -> Callable[[], Awaitable[object]]:
    async def backup() -> object:
        # 备份在专用线程执行：sqlite 在线备份可能持续数秒，不能卡住事件循环
        result = await asyncio.to_thread(app.state.backup.create, None, "daily")
        # 备份之后清理已读超过 30 天的通知（先备份，清掉的仍可从快照找回）；
        # 清理失败只记日志，不算备份失败
        try:
            purged = await asyncio.to_thread(app.state.notifications.purge, app.state.clock())
            log.info("notifications.purged", count=purged)
        except Exception:
            log.exception("notifications.purge_failed")
        return result

    return backup


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    """生产模式托管前端构建产物；/api 下未知路径仍返回 JSON 错误信封。"""
    dist = settings.frontend_dist
    index = dist / "index.html"
    if settings.dev_mode or not index.is_file():
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/"):
            return envelope("NotFound", "接口不存在", 404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


def export_openapi(target: Path) -> None:
    schema = create_app(Settings()).openapi()
    target.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m app.main")
    parser.add_argument("--export-openapi", type=Path, required=True, metavar="PATH")
    export_openapi(parser.parse_args().export_openapi)
