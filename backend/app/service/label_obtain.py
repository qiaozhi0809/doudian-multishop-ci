"""取号 / 一体执行（backend 5.5、flows 7.3）：请求、结果处理、超时查回。"""

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.errors import BizRejected, ParseError, TransientError
from app.adapter.doudian.label_parsers import (
    parse_fetch_and_ship_result,
    parse_fetch_result,
    parse_product_types,
)
from app.adapter.doudian.label_request import (
    fetch_and_ship_body,
    obtain_body,
    order_list_payload,
)
from app.domain.labeling_rules import order_blockers
from app.domain.models import FetchSuccess
from app.service.label_preview import MODE_FETCH_AND_SHIP, PreviewRecord, ShopPlan
from app.service.label_recovery import find_tracking_no
from app.service.label_run import (
    BUSY_LABEL_REASON,
    DEFAULT_EXP_TYPE,
    LABEL_NOT_FOUND_MSG,
    PARTIAL_RESULT_REASON,
    Counter,
    RunContext,
)

PRODUCT_TYPES_FAILED = "查询产品类型失败"
FETCH_TIMEOUT_REASON = "取号响应超时"


class ObtainRunner:
    def __init__(self, ctx: RunContext) -> None:
        self._ctx = ctx

    async def run_shop(self, record: PreviewRecord, plan: ShopPlan, counter: Counter) -> None:
        async def job(client: FxgClient) -> None:
            await self._batch(client, record, plan, counter)

        await self._ctx.runner.run(plan.shop_id, job, actor=record.actor)

    async def _batch(
        self, client: FxgClient, record: PreviewRecord, plan: ShopPlan, counter: Counter
    ) -> None:
        ctx = self._ctx
        rows, items = ctx.reload(plan.order_ids)
        active = ctx.active_waybills([r["id"] for r in rows])
        attempts: list[tuple[dict, dict, int]] = []
        for row in rows:
            reasons = order_blockers(
                row["platform_status"], row["combine_id"], items[row["id"]],
                row["id"] in active, row["status"])
            if reasons:
                counter.skipped += 1
                ctx.publish(record, row, "skipped", reason="；".join(reasons))
                continue
            outcome, task, seq = ctx.prepare_label_task(row, record.mode, record.actor)
            if outcome == "done":
                counter.ok += 1
                tracking = (active.get(row["id"]) or {}).get("waybill_no")
                ctx.publish(record, row, "success", tracking_no=tracking)
            elif outcome == "busy":
                counter.skipped += 1
                ctx.publish(record, row, "skipped", reason=BUSY_LABEL_REASON)
            else:
                attempts.append((row, task, seq))
        if not attempts:
            return
        merged = [{**row, "items": items[row["id"]]} for row, _, _ in attempts]
        order_list = order_list_payload(merged)
        exp_type = await self._exp_type(client, plan, [r["id"] for r, _, _ in attempts])
        if exp_type is None:
            for row, task, _ in attempts:
                ctx.finish_failed(record, row, task, counter, PRODUCT_TYPES_FAILED)
            return
        try:
            if record.mode == MODE_FETCH_AND_SHIP:
                body = fetch_and_ship_body(
                    courier_code=plan.courier_code, template_code=plan.template_code,
                    address=plan.address, exp_type=exp_type, ebill_id=plan.ebill_id,
                    net_code=plan.net_code, order_list=order_list, printer=ctx.printer,
                )
                resp = await client.call(ep.LABEL_FETCH_AND_SHIP, body=body)
                result = parse_fetch_and_ship_result(resp)
            else:
                body = obtain_body(
                    courier_code=plan.courier_code, template_code=plan.template_code,
                    address=plan.address, exp_type=exp_type, ebill_id=plan.ebill_id,
                    net_code=plan.net_code, order_list=order_list, printer=ctx.printer,
                )
                resp = await client.call(ep.LABEL_FETCH, body=body)
                result = parse_fetch_result(resp)
        except TransientError:
            await self._recover(client, record, attempts, counter, FETCH_TIMEOUT_REASON)
            return
        except BizRejected as e:
            for row, task, _ in attempts:
                ctx.finish_failed(record, row, task, counter, str(e))
            return
        await self._apply_result(client, record, plan, attempts, result, counter)

    async def _apply_result(
        self, client: FxgClient, record: PreviewRecord, plan: ShopPlan,
        attempts: list[tuple[dict, dict, int]], result, counter: Counter,
    ) -> None:
        ctx = self._ctx
        by_order = {no: s for s in result.success for no in s.order_nos}
        failed: dict[str, str] = {}
        unref: list[str] = []
        for f in result.failures:
            if f.order_nos:
                for no in f.order_nos:
                    failed[no] = f.fail_msg
            else:
                unref.append(f.fail_msg)
        needs_recovery: list[tuple[dict, dict, int]] = []
        for row, task, seq in attempts:
            no = row["order_no"]
            if no in by_order:
                ctx.record_success(record, plan, row, task, seq, by_order[no], counter)
                continue
            msg = failed.get(no) or (unref[0] if unref else PARTIAL_RESULT_REASON)
            if LABEL_NOT_FOUND_MSG in msg:
                needs_recovery.append((row, task, seq))
            else:
                ctx.finish_failed(record, row, task, counter, msg)
        if needs_recovery:
            await self._recover(client, record, needs_recovery, counter, LABEL_NOT_FOUND_MSG)

    async def _recover(
        self, client: FxgClient, record: PreviewRecord,
        attempts: list[tuple[dict, dict, int]], counter: Counter, reason: str,
    ) -> None:
        """结果不明：查回运单号；查到补写面单，查不到保持待核实（backend 5.12）。"""
        ctx = self._ctx
        for row, task, seq in attempts:
            tracking: str | None = None
            try:
                tracking = await find_tracking_no(client, row["order_no"])
            except (TransientError, BizRejected, ParseError):
                tracking = None
            if tracking:
                plan = ctx.plan_of(record, row["shop_id"])
                success = FetchSuccess(
                    (row["order_no"],), plan.courier_code, tracking, plan.template_code,
                    None, None)
                ctx.record_success(record, plan, row, task, seq, success, counter)
            else:
                ctx.finish_verifying(record, row, task, counter, reason)

    async def _exp_type(
        self, client: FxgClient, plan: ShopPlan, order_ids: list[int]
    ) -> str | None:
        try:
            resp = await client.call(ep.PRODUCT_TYPES, body={
                "logistics_company_code": plan.courier_code,
                "shop_order_ids": [str(i) for i in order_ids],
            })
        except (TransientError, BizRejected, ParseError):
            return None
        return parse_product_types(resp).exp_type or DEFAULT_EXP_TYPE
