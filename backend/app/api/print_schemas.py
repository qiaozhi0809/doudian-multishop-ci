"""打印接口的请求 / 响应模型。"""

from pydantic import BaseModel, Field

MAX_PRINT_BATCH = 200


class PrinterStatus(BaseModel):
    available: bool
    printers: list[str]
    default_printer: str | None
    error: str | None
    checked_at: str


class PrintRequest(BaseModel):
    waybill_ids: list[int] = Field(min_length=1, max_length=MAX_PRINT_BATCH)
    printer_name: str | None = None


class PrintStarted(BaseModel):
    job_ids: list[int]
    waybill_ids: list[int]
    simulated: bool = False


class PrintJobRow(BaseModel):
    id: int
    waybill_id: int
    printer_name: str
    status: str
    result_code: str | None
    result_detail: str | None
    attempts: int
    created_at: str
    finished_at: str | None


class WaybillPrintRow(BaseModel):
    waybill_id: int
    waybill_no: str | None
    waybill_status: str
    has_print_data: bool
    job: PrintJobRow | None


class WaybillPrintList(BaseModel):
    items: list[WaybillPrintRow]
