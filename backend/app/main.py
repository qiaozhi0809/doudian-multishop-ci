"""应用工厂与启动流程。"""

import argparse
import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from pathlib import Path

from argon2 import PasswordHasher
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.adapter.print.component import PrintComponent
from app.api import aftersale as aftersale_api
from app.api import auth as auth_api
from app.api import catalog as catalog_api
from app.api import event as event_api
from app.api import fund as fund_api
from app.api import label as label_api
from app.api import order as order_api
from app.api import print as print_api
from app.api import shop as shop_api
from app.api.common_schemas import ErrorEnvelope, Health
from app.api.deps import require_admin
from app.api.errors import envelope, install_error_handlers
from app.api.host_guard import HostGuard, allowed_hosts
from app.config import Settings
from app.service.egress_probe import FetchIp
from app.service.periodic import (
    ORDER_SYNC_INTERVAL_S,
    PROBE_INTERVAL_S,
    SYSTEM_ACTOR,
    for_each_active_shop,
    probe_session,
    run_every,
)
from app.service.shop_login import ScanFn
from app.service.shop_runner import ClientFactory
from app.store.db import DB_FILE_NAME, make_engine
from app.store.migrate import upgrade_to_head
from app.wiring import Overrides, build_services


def create_app(
    settings: Settings | None = None, *, clock: Callable[[], datetime] | None = None,
    hasher: PasswordHasher | None = None, client_factory: ClientFactory | None = None,
    fetch_ip: FetchIp | None = None, scan: ScanFn | None = None,
    print_component: PrintComponent | None = None,
) -> FastAPI:
    settings = settings or Settings()
    overrides = Overrides(clock, hasher, client_factory, fetch_ip, scan, print_component)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = settings.data_dir / DB_FILE_NAME
        upgrade_to_head(db_path)
        engine = make_engine(db_path)
        for name, service in build_services(settings, engine, overrides).items():
            setattr(app.state, name, service)

        stop = asyncio.Event()
        runner, order_sync = app.state.runner, app.state.order_sync
        probe_all = partial(for_each_active_shop, engine, partial(probe_session, runner))
        sync_all = partial(
            for_each_active_shop, engine, lambda sid: order_sync.sync_pending(sid, SYSTEM_ACTOR)
        )
        tasks = [
            asyncio.create_task(run_every(PROBE_INTERVAL_S, probe_all, stop)),
            asyncio.create_task(run_every(ORDER_SYNC_INTERVAL_S, sync_all, stop)),
        ]
        try:
            yield
        finally:
            stop.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await app.state.tasks.shutdown()
            engine.dispose()

    app = FastAPI(
        title="抖店多店铺管理 本地 API", lifespan=lifespan,
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
        auth_api, shop_api, order_api, label_api, print_api, event_api,
        aftersale_api, catalog_api, fund_api,
    ):
        app.include_router(module.router)
    _mount_frontend(app, settings)
    return app


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
