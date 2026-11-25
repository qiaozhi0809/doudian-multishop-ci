"""打印接口：组件状态、提交打印任务、任务回执、面单可打印信息（flows 7.4 / 10）。"""

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_admin
from app.api.params import parse_waybill_ids
from app.api.print_schemas import (
    PrinterStatus,
    PrintJobRow,
    PrintRequest,
    PrintStarted,
    WaybillPrintList,
    WaybillPrintRow,
)

router = APIRouter(prefix="/api/print", tags=["print"])


@router.get("/status", response_model=PrinterStatus)
async def status(request: Request) -> PrinterStatus:
    return PrinterStatus(**await request.app.state.printing.status())


@router.post("/jobs", response_model=PrintStarted, status_code=202)
async def submit(
    request: Request, payload: PrintRequest, admin: str = Depends(require_admin)
) -> PrintStarted:
    started = await request.app.state.printing.submit(
        payload.waybill_ids, admin, payload.printer_name)
    return PrintStarted(job_ids=started.job_ids, waybill_ids=started.waybill_ids)


@router.get("/jobs/{job_id}", response_model=PrintJobRow)
def job(request: Request, job_id: int) -> PrintJobRow:
    return PrintJobRow(**request.app.state.printing.job(job_id))


@router.get("/waybills", response_model=WaybillPrintList)
def waybills(request: Request, waybill_ids: str = Query(...)) -> WaybillPrintList:
    ids = parse_waybill_ids(waybill_ids)
    rows = request.app.state.printing.waybill_views(ids)
    return WaybillPrintList(items=[WaybillPrintRow(**r) for r in rows])
