import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(), base_url="http://127.0.0.1:8787") as c:
        yield c
