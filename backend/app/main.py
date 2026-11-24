"""应用工厂与启动流程。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.store.db import DB_FILE_NAME, make_engine
from app.store.migrate import upgrade_to_head


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = settings.data_dir / DB_FILE_NAME
        upgrade_to_head(db_path)
        app.state.engine = make_engine(db_path)
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(title="doudian-multishop", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
