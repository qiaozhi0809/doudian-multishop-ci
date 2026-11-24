import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapter.doudian.errors import (
    BizRejected,
    EgressUnavailable,
    ParseError,
    RiskBlocked,
    SessionExpired,
    TransientError,
)
from app.api.errors import install_error_handlers
from app.service.egress import EgressConflict, EgressNotReady
from app.service.shop_runner import ShopPaused

CASES = [
    (SessionExpired("x"), 409),
    (EgressNotReady("x"), 409),
    (EgressConflict("x"), 409),
    (ShopPaused(3, "risk_blocked:1"), 409),
    (RiskBlocked("602502151", "x"), 429),
    (BizRejected("602500705", "x"), 422),
    (TransientError("x"), 503),
    (EgressUnavailable("x"), 503),
    (ParseError("x"), 502),
    (LookupError("x"), 404),
]


@pytest.mark.parametrize(("exc", "status"), CASES, ids=[type(c[0]).__name__ for c in CASES])
def test_error_mapping(exc, status):
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise exc

    r = TestClient(app).get("/boom")
    assert r.status_code == status
    error = r.json()["error"]
    assert error["type"] == type(exc).__name__
    assert set(error) == {"type", "message", "shop_id", "detail"}


def test_shop_id_carried_for_shop_paused():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise ShopPaused(3, "risk_blocked:1")

    assert TestClient(app).get("/boom").json()["error"]["shop_id"] == 3


def test_unexpected_error_is_500_without_leaking():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internals")

    r = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert "secret" not in r.text and r.json()["error"]["type"] == "InternalError"
