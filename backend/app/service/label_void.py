"""面单作废执行（api/write.md A.2.6）：按运单号取消，成功后订单回 pending_label。"""

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.errors import BizRejected, TransientError
from app.adapter.doudian.label_parsers import parse_cancel_result
from app.adapter.doudian.label_request import cancel_body
from app.domain.labeling_rules import VOIDABLE_STATUSES
from app.service.label_preview import PreviewRecord, VoidPlan
from app.service.label_run import (
    BUSY_VOID_REASON,
    CHANGED_REASON,
    VOID_UNKNOWN_REASON,
    Counter,
    RunContext,
)
from app.store import order_store, waybill_store

NO_VOID_RESULT = "平台未返回该面单的作废结果"


class VoidRunner:
    def __init__(self, ctx: RunContext) -> None:
        self._ctx = ctx

    async def run_shop(self, record: PreviewRecord, plan: VoidPlan, counter: Counter) -> None:
        async def job(client: FxgClient) -> None:
            await self._batch(client, record, plan, counter)

        await self._ctx.runner.run(plan.shop_id, job, actor=record.actor)

    async def _batch(
        self, client: FxgClient, record: PreviewRecord, plan: VoidPlan, counter: Counter
    ) -> None:
        ctx = self._ctx
        with ctx.engine.connect() as conn:
            waybills = waybill_store.by_ids(conn, plan.waybill_ids)
            orders = {r["id"]: r for r in order_store.get_by_ids(
                conn, [w["order_id"] for w in waybills])}
        attempts = []
        for w in waybills:
            order = orders.get(w["order_id"])
            if order is None or w["status"] not in ("active", "printed") \
                    or order["status"] not in VOIDABLE_STATUSES:
                counter.skipped += 1
                ctx.publish(record, order or {"order_no": str(w["order_id"])},
                            "skipped", reason=CHANGED_REASON)
                continue
            outcome, task = ctx.prepare_void_task(w, record.actor)
            if outcome == "done":
                counter.ok += 1
                ctx.publish(record, order, "success", tracking_no=w["waybill_no"])
            elif outcome == "busy":
                counter.skipped += 1
                ctx.publish(record, order, "skipped", reason=BUSY_VOID_REASON)
            else:
                attempts.append((w, order, task))
        if not attempts:
            return
        body = cancel_body([w for w, _, _ in attempts])
        try:
            resp = await client.call(ep.CANCEL_TRACKING_NOS, body=body)
        except (TransientError, BizRejected) as e:
            reason = VOID_UNKNOWN_REASON if isinstance(e, TransientError) else str(e)
            for _w, order, task in attempts:
                ctx.finish_failed(record, order, task, counter, reason)
            return
        result = parse_cancel_result(resp)
        ok_tracking = {s.tracking_no for s in result.success}
        fail_msg = {f.tracking_no: f.fail_msg for f in result.failures if f.tracking_no}
        for w, order, task in attempts:
            if w["waybill_no"] in ok_tracking:
                ctx.record_void(order, task, w, counter, record)
            else:
                msg = (fail_msg.get(w["waybill_no"]) or result.fail_msg or NO_VOID_RESULT)
                ctx.finish_failed(record, order, task, counter, msg)
