"""打印组件消息协议（flows 10 节实测结构）：纯函数翻译，不含连接与等待。"""

import base64
import binascii
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 2
CMD_GET_PRINTERS = "getPrinters"
CMD_PRINT = "print"
CMD_NOTIFY_PRINT_RESULT = "notifyPrintResult"
CMD_NOTIFY_TASK_RESULT = "notifyTaskResult"
CMD_NOTIFY_DOC_RESULT = "notifyDocResult"
NOTIFY_COMMANDS = frozenset({
    CMD_NOTIFY_PRINT_RESULT, CMD_NOTIFY_TASK_RESULT, CMD_NOTIFY_DOC_RESULT,
})
PREVIEW_TYPE = "pdf"
PRINT_CONFIG_WAYBILL = "waybill"
STATUS_SUCCESS = "success"

# 打印结果码（print_job.result_code）：
RESULT_SUCCESS = "success"
RESULT_COMPONENT_FAILED = "component_failed"  # 组件明确回执失败
RESULT_UNRECOGNIZED = "unrecognized_result"  # 回执无法判断成败：不得当作成功
RESULT_NO_RESPONSE = "no_response"  # 等回执超时
RESULT_UNAVAILABLE = "component_unavailable"  # 连不上组件（未启动 / 端口不通）

_DETAIL_MAX = 2000


@dataclass(frozen=True)
class DocumentSpec:
    """一张面单的打印数据（取号响应或补打接口返回，flows 10 节）。"""

    waybill_no: str
    print_data: str
    sign: str | None
    template_url: str | None
    params: str | None
    custom_print_data: str | None
    custom_template_url: str | None


@dataclass(frozen=True)
class PrintOutcome:
    ok: bool
    code: str
    detail: str = ""


def build_documents(specs: Sequence[DocumentSpec]) -> list[dict[str, Any]]:
    """按页面源码的字段映射组装 documents；空字段用空串（与页面一致）。"""
    documents: list[dict[str, Any]] = []
    for spec in specs:
        document: dict[str, Any] = {
            "documentID": spec.waybill_no,
            "standard": {
                "signature": spec.sign or "",
                "encryptedData": spec.print_data,
                "templateURL": spec.template_url or "",
                "params": spec.params or "",
            },
        }
        if spec.custom_template_url:
            document["custom"] = {
                "data": spec.custom_print_data or "",
                "templateURL": spec.custom_template_url,
            }
        documents.append(document)
    return documents


def build_get_printers(request_id: str) -> dict[str, Any]:
    return {"cmd": CMD_GET_PRINTERS, "requestID": request_id, "version": PROTOCOL_VERSION}


def build_print_message(
    *, request_id: str, printer: str, documents: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "cmd": CMD_PRINT,
        "requestID": request_id,
        "version": PROTOCOL_VERSION,
        "isOpen": False,
        "previewType": PREVIEW_TYPE,
        "task": {
            "taskID": request_id,
            "preview": False,
            "printConfig": PRINT_CONFIG_WAYBILL,
            "printer": printer,
            "documents": documents,
        },
    }


def parse_printers(message: dict[str, Any]) -> tuple[str | None, tuple[str, ...]]:
    default = message.get("defaultPrinter") or message.get("default_printer")
    names = tuple(
        str(p["name"]) for p in message.get("printers") or []
        if isinstance(p, dict) and p.get("name")
    )
    return (str(default) if default else None, names)


def parse_ack(message: dict[str, Any]) -> tuple[bool, str]:
    """`print` 的即时响应：只表示请求被接受，不代表已打印。"""
    status = str(message.get("status") or "")
    if status == STATUS_SUCCESS:
        return True, ""
    detail = str(message.get("msg") or message.get("message") or "")
    return False, detail or f"组件拒绝了打印请求（{status or '未知状态'}）"


def parse_print_result(message: dict[str, Any]) -> PrintOutcome:
    """`notifyPrintResult` 回执：没有明确成功证据时一律不算成功（flows 7.4）。"""
    status = str(message.get("status") or message.get("result") or "")
    raw_items = message.get("printStatus") or message.get("print_status") or []
    items = raw_items if isinstance(raw_items, list) else []
    details: list[str] = []
    item_failed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        detail = _decode_detail(item.get("detail"))
        if detail:
            details.append(detail)
        item_status = str(item.get("status") or "")
        if item_status and item_status != STATUS_SUCCESS:
            item_failed = True
    detail_text = _join(details)
    if status:
        ok = status == STATUS_SUCCESS and not item_failed
        return PrintOutcome(ok, RESULT_SUCCESS if ok else RESULT_COMPONENT_FAILED, detail_text)
    if items:
        ok = not item_failed
        return PrintOutcome(ok, RESULT_SUCCESS if ok else RESULT_COMPONENT_FAILED, detail_text)
    return PrintOutcome(False, RESULT_UNRECOGNIZED, detail_text)


def _decode_detail(value: Any) -> str:
    """组件回执里的 detail 是 base64 文本；解不开就原样保留。"""
    if not value:
        return ""
    text = str(value)
    try:
        decoded = base64.b64decode(text, validate=True).decode("utf-8").strip()
        if decoded:
            return decoded[:_DETAIL_MAX]
    except (binascii.Error, UnicodeDecodeError, ValueError):
        pass
    return text[:_DETAIL_MAX]


def _join(parts: Sequence[str]) -> str:
    return "\n".join(p for p in parts if p)[:_DETAIL_MAX]
