import pytest

from app.store.db import make_engine
from app.store.migrate import upgrade_to_head

NOW = "2026-11-25T00:00:00Z"
LATER = "2026-11-25T00:05:00Z"


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "app.db"
    upgrade_to_head(db)
    eng = make_engine(db)
    yield eng
    eng.dispose()
