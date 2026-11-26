"""在飞鸽中回复：经该店队列置前常驻页并点开会话；审计与日志里没有会话编号和买家昵称。"""

import asyncio
from dataclasses import replace

import pytest
import sqlalchemy as sa
from structlog.testing import capture_logs

from app.domain.errors import InvalidRequest
from app.service.shop_runner import ShopPaused
from tests.service.im_session_test import msg
from tests.service.im_watcher_support import ADMIN, Rig, drain, until

CONV = "conv-test-1"
BUYER = "测试买家"
MINE = f"{BUYER} 在吗"
OTHER = "测试顾客 你好"


@pytest.fixture
async def rig(engine, tmp_path):
    rig = Rig(engine, tmp_path)
    yield rig
    await rig.watcher.shutdown()


async def receiving(rig: Rig, conversations: list[str]):
    """跑起常驻页，快照里有带昵称的 CONV；返回假的 Playwright 页面。"""
    await rig.start()
    im_page = rig.attach.pages[0]
    im_page.on_messages([replace(msg("msg-test-1", conv=CONV), buyer_name=BUYER)])
    await until(lambda: rig.watcher.snapshot(rig.shop_id))
    im_page.page.conversations = list(conversations)
    return im_page.page


def focus(rig: Rig, conversation_id: str = CONV):
    return rig.watcher.focus(rig.shop_id, conversation_id, actor=ADMIN)


def occupy_queue(rig: Rig) -> tuple[asyncio.Event, asyncio.Task]:
    release = asyncio.Event()
    busy = asyncio.create_task(
        rig.env.runner.run(rig.shop_id, lambda _c: release.wait(), actor=ADMIN))
    return release, busy


def audit_rows(rig: Rig) -> list[str]:
    with rig.engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT * FROM audit_log")).mappings()
        return [str(dict(r)) for r in rows]


async def test_focus_runs_in_shop_queue(rig):
    page = await receiving(rig, [MINE, OTHER])
    release, busy = occupy_queue(rig)
    await drain()

    task = asyncio.create_task(focus(rig))
    await drain()
    assert page.calls == []

    release.set()
    await busy
    assert await asyncio.wait_for(task, 2) == "opened"
    assert page.clicked() == [MINE]


async def test_focus_passes_snapshot_buyer_name(rig):
    page = await receiving(rig, [OTHER, MINE])

    assert await focus(rig) == "opened"
    assert page.clicked() == [MINE]

    page.conversations = [OTHER, "测试顾客二号 在吗"]
    assert await focus(rig) == "not_found"
    assert page.clicked() == [MINE]


async def test_focus_not_running_rejected(rig):
    with pytest.raises(InvalidRequest, match="该店飞鸽未在接收"):
        await focus(rig)

    assert rig.env.egress.ready_calls == []  # 不进队列、不做出口检查
    assert rig.registry.opened == []


async def test_focus_page_stopped_while_queued_rejected(rig):
    page = await receiving(rig, [MINE])
    release, busy = occupy_queue(rig)
    await drain()
    task = asyncio.create_task(focus(rig))
    await drain()

    await rig.watcher.stop(rig.shop_id, reason="ineligible", actor=ADMIN)
    release.set()
    await busy

    with pytest.raises(InvalidRequest, match="该店飞鸽未在接收"):
        await asyncio.wait_for(task, 2)
    assert page.calls == []
    assert rig.audits("im.focus")[0]["result"] == "error"


async def test_focus_audit_has_no_conversation_id_or_name(rig):
    page = await receiving(rig, [MINE])

    await focus(rig)
    page.conversations = []
    await focus(rig)

    audits = rig.audits("im.focus")
    assert [(a["shop_id"], a["actor"], a["result"], a["resp"]) for a in audits] == [
        (rig.shop_id, ADMIN, "ok", {"result": "opened"}),
        (rig.shop_id, ADMIN, "ok", {"result": "not_found"}),
    ]
    assert [a["req_summary"] for a in audits] in ([None, None], ["{}", "{}"])
    assert not any(CONV in row or BUYER in row for row in audit_rows(rig))
    assert not any(BUYER in str(data) for _, data in rig.published)


async def test_focus_page_error_hides_buyer_name(rig):
    """页面报错原文带着定位条件（含昵称）：只记类型，抛固定提示。"""
    page = await receiving(rig, [MINE])
    page.click_error = TimeoutError(f"waiting for locator(has_text='{BUYER}') {CONV}")

    with capture_logs() as logs, pytest.raises(InvalidRequest) as error:
        await focus(rig)

    assert BUYER not in str(error.value) and CONV not in str(error.value)
    assert error.value.__cause__ is None and error.value.__suppress_context__
    assert {"event": "im.focus_failed", "error": "TimeoutError"}.items() <= logs[-1].items()
    assert BUYER not in str(logs) and CONV not in str(logs)
    audits = rig.audits("im.focus")
    assert (audits[0]["result"], audits[0]["resp"]) == ("error", {"result": "error"})
    assert not any(BUYER in row for row in audit_rows(rig))
    assert rig.state() == "running"


async def test_focus_paused_shop_raises_and_audits(rig):
    page = await receiving(rig, [MINE])
    rig.pause(rig.shop_id)

    with pytest.raises(ShopPaused):
        await focus(rig)

    assert page.calls == []
    assert rig.audits("im.focus")[0]["result"] == "error"
