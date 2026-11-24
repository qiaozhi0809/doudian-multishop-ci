"""应用工厂与启动流程。"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from app.config import Settings
from app.service.egress import EgressService
from app.service.egress_probe import make_fetch_ip
from app.service.events import EventBus
from app.service.periodic import PROBE_INTERVAL_S, for_each_active_shop, probe_session, run_every
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shop_runner import ShopRunner
from app.shared.secret_box import make_secret_box
from app.store.db import DB_FILE_NAME, make_engine
from app.store.migrate import upgrade_to_head


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

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

        stop = asyncio.Event()
        probe_all = partial(for_each_active_shop, engine, partial(probe_session, runner))
        tasks = [asyncio.create_task(run_every(PROBE_INTERVAL_S, probe_all, stop))]
        try:
            yield
        finally:
            stop.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            engine.dispose()

    app = FastAPI(title="doudian-multishop", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
