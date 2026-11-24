"""应用工厂与启动流程。"""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial

from argon2 import PasswordHasher
from fastapi import Depends, FastAPI

from app.api import auth as auth_api
from app.api.deps import require_admin
from app.api.errors import install_error_handlers
from app.api.host_guard import HostGuard, allowed_hosts
from app.config import Settings
from app.service.auth import AuthService
from app.service.base_data import BaseDataService
from app.service.egress import EgressService
from app.service.egress_probe import make_fetch_ip
from app.service.events import EventBus
from app.service.order_sync import OrderSyncService
from app.service.periodic import (
    ORDER_SYNC_INTERVAL_S,
    PROBE_INTERVAL_S,
    SYSTEM_ACTOR,
    for_each_active_shop,
    probe_session,
    run_every,
)
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shop_runner import ShopRunner
from app.shared.secret_box import make_secret_box
from app.store.db import DB_FILE_NAME, make_engine
from app.store.migrate import upgrade_to_head


def create_app(
    settings: Settings | None = None, *, clock: Callable[[], datetime] | None = None,
    hasher: PasswordHasher | None = None,
) -> FastAPI:
    settings = settings or Settings()
    auth_kwargs = {k: v for k, v in {"clock": clock, "hasher": hasher}.items() if v is not None}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = settings.data_dir / DB_FILE_NAME
        upgrade_to_head(db_path)
        engine = make_engine(db_path)
        box = make_secret_box(settings.data_dir)
        events = EventBus()
        sessions = SessionManager(engine, box, events)
        egress = EgressService(engine, box, events, make_fetch_ip(settings.egress_echo_url))
        runner = ShopRunner(engine, ShopScheduler(settings.max_concurrent_shops), egress, sessions)
        app.state.engine = engine
        app.state.events = events
        app.state.sessions = sessions
        app.state.egress = egress
        app.state.runner = runner
        app.state.auth = AuthService(engine, **auth_kwargs)
        app.state.base_data = BaseDataService(engine, runner, events)
        order_sync = OrderSyncService(engine, runner, sessions, events)
        app.state.order_sync = order_sync

        stop = asyncio.Event()
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
            engine.dispose()

    app = FastAPI(
        title="doudian-multishop", lifespan=lifespan, dependencies=[Depends(require_admin)]
    )
    app.add_middleware(
        HostGuard, hosts=allowed_hosts(settings.port, settings.dev_mode)
    )
    install_error_handlers(app)
    app.include_router(auth_api.router)
    app.state.settings = settings

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
