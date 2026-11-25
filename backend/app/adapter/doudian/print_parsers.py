"""补打面单数据解析（batchGetPrintInfos，flows 10 节）。

返回结构未实测（只知请求体），按常见包裹形态容错解析；字段名兼容
snake_case / camelCase。解析为空不报错——上层据此走「无打印数据 → 手动补打」。
"""

from typing import Any

from app.adapter.doudian.errors import ParseError
from app.domain.models import PrintInfo

# data 下可能出现的列表包裹键（平台接口常见写法）
_LIST_KEYS = (
    "print_infos", "printInfos", "print_info_list", "printInfoList",
    "list", "infos", "data", "result", "records",
)
_TRACKING_KEYS = (
    "tracking_no", "trackingNo", "track_no", "trackNo",
    "trackInfo", "track_info", "waybill_no", "waybillNo",
)
_PRINT_DATA_KEYS = ("print_data", "printData")
_SIGN_KEYS = ("sign",)
_TEMPLATE_KEYS = ("template_url", "templateUrl")
_PARAMS_KEYS = ("OAuth", "oauth", "params")
_CUSTOM_DATA_KEYS = ("custom_print_data", "customPrintData")
_CUSTOM_TEMPLATE_KEYS = ("custom_template_url", "customTemplateUrl")


def parse_print_infos(resp: dict) -> dict[str, PrintInfo]:
    data = resp.get("data") if isinstance(resp, dict) else None
    if data is None:
        raise ParseError("补打响应缺少 data")
    out: dict[str, PrintInfo] = {}
    for item in _items(data):
        tracking = _first(item, _TRACKING_KEYS)
        if not tracking:
            continue
        out[str(tracking)] = PrintInfo(
            tracking_no=str(tracking),
            print_data=_opt_str(_first(item, _PRINT_DATA_KEYS)),
            sign=_opt_str(_first(item, _SIGN_KEYS)),
            template_url=_opt_str(_first(item, _TEMPLATE_KEYS)),
            params=_opt_str(_first(item, _PARAMS_KEYS)),
            custom_print_data=_opt_str(_first(item, _CUSTOM_DATA_KEYS)),
            custom_template_url=_opt_str(_first(item, _CUSTOM_TEMPLATE_KEYS)),
        )
    return out


def _items(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [i for i in data if isinstance(i, dict)]
    if not isinstance(data, dict):
        raise ParseError("补打响应 data 既不是列表也不是对象")
    for key in _LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            return [i for i in value if isinstance(i, dict)]
        if isinstance(value, dict):
            return _mapping_items(value)
    if _has_record_fields(data):
        return [data]
    return _mapping_items(data)


def _mapping_items(mapping: dict) -> list[dict]:
    """`{运单号: {打印字段}}` 形式的映射。"""
    out: list[dict] = []
    for key, value in mapping.items():
        if isinstance(value, dict):
            item = dict(value)
            item.setdefault("tracking_no", key)
            out.append(item)
    return out


def _has_record_fields(item: dict) -> bool:
    return any(item.get(k) for k in (*_TRACKING_KEYS, *_PRINT_DATA_KEYS))


def _first(item: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _opt_str(value: Any) -> str | None:
    return None if value in (None, "") else str(value)
