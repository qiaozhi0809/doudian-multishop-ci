from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_startup_creates_data_dir(tmp_path):
    data_dir = tmp_path / "not" / "yet"
    assert not data_dir.exists()
    with TestClient(create_app(Settings(data_dir=data_dir)), base_url="http://127.0.0.1:8787"):
        assert (data_dir / "app.db").is_file()
