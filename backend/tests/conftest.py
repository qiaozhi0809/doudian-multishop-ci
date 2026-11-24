import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store.db import make_engine
from app.store.migrate import upgrade_to_head


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data"))
    with TestClient(app, base_url="http://127.0.0.1:8787") as c:
        yield c


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "app.db"
    upgrade_to_head(db)
    eng = make_engine(db)
    yield eng
    eng.dispose()
