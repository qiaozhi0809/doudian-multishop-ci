from datetime import timedelta
from typing import get_args

import pytest

from app.domain.notification_rules import (
    LEVEL_BY_KIND,
    REOPEN_SILENT_WITHIN,
    Kind,
    link_for,
    state_key,
    title_for,
)

STRONG = {"new_aftersale", "login_expired", "egress_unreachable", "egress_changed",
          "egress_duplicate", "risk_paused", "ship_deadline"}
MEDIUM = {"new_order", "batch_failed", "sync_failed"}
WEAK = {"batch_done", "sync_done", "reconcile_done", "recovered"}


def test_每个种类都有档位且与约定一致():
    kinds = set(get_args(Kind))
    assert set(LEVEL_BY_KIND) == kinds
    assert {k for k, v in LEVEL_BY_KIND.items() if v == "strong"} == STRONG
    assert {k for k, v in LEVEL_BY_KIND.items() if v == "medium"} == MEDIUM
    assert {k for k, v in LEVEL_BY_KIND.items() if v == "weak"} == WEAK


def test_每个种类都有跳转链接():
    for kind in get_args(Kind):
        assert link_for(kind, 7).startswith("/")


def test_跳转链接使用前端现有参数名():
    assert link_for("new_order", 3) == "/orders?shops=3"
    assert link_for("new_aftersale", 3) == "/aftersale?view=todo&shops=3"
    assert link_for("ship_deadline", 3) == "/orders?quick=exp_ship&shops=3"
    for kind in ("login_expired", "egress_unreachable", "egress_changed",
                 "egress_duplicate", "risk_paused"):
        assert link_for(kind, 3) == "/shops?shop=3"
    assert link_for("batch_done", None) == "/labeling"
    assert link_for("batch_failed", None) == "/labeling"
    assert link_for("reconcile_done", None) == "/reconcile"


@pytest.mark.parametrize("sync_type,path", [
    ("orders", "/orders"), ("aftersales", "/aftersale"), ("products", "/catalog"),
    ("stock", "/stock"), ("fund", "/fund"),
])
def test_同步通知按同步类型跳转(sync_type, path):
    assert link_for("sync_done", 3, sync_type=sync_type) == f"{path}?shops=3"
    assert link_for("sync_failed", None, sync_type=sync_type) == path


def test_没有店铺时不带店铺参数():
    assert link_for("new_order", None) == "/orders"


@pytest.mark.parametrize("kind,count,detail,expected", [
    ("new_order", 5, None, "店A 新增 5 单待发货"),
    ("new_aftersale", 2, None, "店A 新增 2 个售后"),
    ("login_expired", 0, None, "店A 登录失效"),
    ("egress_unreachable", 0, None, "店A 出口不通"),
    ("egress_changed", 0, None, "店A 出口 IP 已变化"),
    ("egress_duplicate", 0, None, "店A 出口 IP 与其他店重复"),
    ("risk_paused", 0, None, "店A 风控暂停"),
    ("ship_deadline", 3, None, "店A 3 单临近发货超时"),
    ("recovered", 0, "出口不通", "店A 已恢复：出口不通"),
])
def test_店铺类标题逐字一致(kind, count, detail, expected):
    assert title_for(kind, shop_name="店A", count=count, detail=detail) == expected


def test_打单标题():
    done = title_for("batch_done", shop_name=None, count=12, detail=None)
    failed = title_for("batch_failed", shop_name=None, count=12, detail="1")
    assert done == "打单完成：成功 12，失败 0"
    assert failed == "打单完成：成功 12，失败 1"


def test_同步与对账标题():
    assert title_for("sync_done", shop_name="店A", count=0, detail="订单") == "店A 订单同步完成"
    assert title_for("sync_failed", shop_name="店A", count=0, detail="订单") == "店A 订单同步失败"
    assert title_for("reconcile_done", shop_name=None, count=0, detail=None) == "对账完成"


def test_state_key与静默窗口():
    assert state_key("egress", 3) == "egress:3"
    assert state_key("login", 1) == "login:1"
    assert REOPEN_SILENT_WITHIN == timedelta(minutes=30)
