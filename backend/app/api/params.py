"""查询参数解析。"""

from app.domain.errors import InvalidRequest


def parse_shop_ids(raw: str | None) -> list[int] | None:
    """`shop_ids=1,2,3`；省略 = None（全部启用店铺）。"""
    if raw is None or raw.strip() == "":
        return None
    try:
        return [int(p) for p in raw.split(",") if p.strip()]
    except ValueError:
        raise InvalidRequest("shop_ids 必须是逗号分隔的整数") from None
