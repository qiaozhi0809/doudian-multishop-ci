"""M7 掉线重登 / 断点续跑：重启恢复与会话失效时的任务边界。"""

import sqlalchemy as sa

from app.domain.task_status import TaskStatus, TaskType
from app.store import task_store
from tests.service.label_support import add_shop
from tests.service.support import NOW, Env


def _start(engine, *, shop_id: int, key: str, type_: TaskType, status: str) -> int:
    with engine.begin() as conn:
        row = task_store.start(
            conn, key=key, shop_id=shop_id, type=type_.value, payload={},
            actor="admin", now=NOW,
        )
        if status != TaskStatus.RUNNING.value:
            conn.execute(
                sa.update(task_store.tasks).where(task_store.tasks.c.id == row["id"]).values(
                    status=status))
        return int(row["id"])


def _status(engine, task_id: int) -> str:
    with engine.connect() as conn:
        return conn.execute(
            sa.select(task_store.tasks.c.status).where(task_store.tasks.c.id == task_id)
        ).scalar_one()


def test_recover_after_restart_sends_unknown_writes_to_verifying(engine):
    shop_id = add_shop(engine)
    obtain = _start(engine, shop_id=shop_id, key="label:s1:o1:0",
                    type_=TaskType.OBTAIN_LABEL, status=TaskStatus.RUNNING.value)
    ship = _start(engine, shop_id=shop_id, key="ship:1:zt:79200000000001",
                  type_=TaskType.SHIP, status=TaskStatus.RUNNING.value)
    recover = _start(engine, shop_id=shop_id, key="recover:s1:o1",
                     type_=TaskType.RECOVER_LABEL, status=TaskStatus.RUNNING.value)
    done = _start(engine, shop_id=shop_id, key="label:s1:o2:0",
                  type_=TaskType.OBTAIN_LABEL, status=TaskStatus.SUCCESS.value)

    with engine.begin() as conn:
        counts = task_store.recover_after_restart(conn, NOW)

    assert counts == {"verifying": 2, "queued": 1}
    assert _status(engine, obtain) == TaskStatus.VERIFYING.value
    assert _status(engine, ship) == TaskStatus.VERIFYING.value
    assert _status(engine, recover) == TaskStatus.QUEUED.value  # 只读任务可安全重跑
    assert _status(engine, done) == TaskStatus.SUCCESS.value  # 已完成的不动


def test_mark_expired_releases_running_tasks_of_that_shop(engine, tmp_path, clock):
    env = Env(engine, tmp_path)
    task_id = _start(engine, shop_id=env.shop_id, key="label:s1:o1:0",
                     type_=TaskType.OBTAIN_LABEL, status=TaskStatus.RUNNING.value)

    env.sessions.mark_expired(env.shop_id)

    assert _status(engine, task_id) == TaskStatus.VERIFYING.value
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(task_store.tasks).where(task_store.tasks.c.id == task_id)
        ).mappings().one()
    assert "重新登录" in row["last_error"]
    # 重登后可重新提交：幂等键复用 verifying 行，attempts+1，而不是永远 busy
    with engine.begin() as conn:
        again = task_store.start(
            conn, key="label:s1:o1:0", shop_id=env.shop_id,
            type=TaskType.OBTAIN_LABEL.value, payload={}, actor="admin", now=NOW,
        )
    assert again["status"] == TaskStatus.RUNNING.value
    assert again["attempts"] == 2
