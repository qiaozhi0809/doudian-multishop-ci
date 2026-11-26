"""列表排序：白名单字段名 → SQL 表达式，在 SQL 里排好序再分页。

空值不论升降都排在最后（与前端表格一致）；末尾补 id 同向排序，保证翻页时顺序稳定。
字段名由接口层的 Literal 校验（非白名单 422），这里收到未知字段视为程序缺陷。
"""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

import sqlalchemy as sa

from app.store.schema import shop

SortOrder = Literal["asc", "desc"]


def shop_name_of(shop_id_col: Any) -> Any:
    """按店铺名排序用：行上的 shop_id 对应的店铺名（相关子查询，免得改动原查询的 join）。"""
    return sa.select(shop.c.name).where(shop.c.id == shop_id_col).scalar_subquery()


def order_by(
    columns: Mapping[str, Any], sort: str | None, order: SortOrder,
    default: Sequence[Any], tiebreak: Any,
) -> list[Any]:
    """sort 为 None 用列表自己的默认排序；否则按白名单字段排序，空值在后、id 兜底。"""
    if sort is None:
        return list(default)
    expr = columns[sort]
    if order == "asc":
        return [expr.is_(None), expr.asc(), tiebreak.asc()]
    return [expr.is_(None), expr.desc(), tiebreak.desc()]


def rank_of(expr: Any, ordered: Sequence[Any]) -> Any:
    """状态列按界面显示顺序排序：ordered 里的值依次得 0、1、2…；不在其中的排在已知值之后，
    空值仍为 NULL（由 order_by 排到最后）。避免按内部代码的字典序排出和界面对不上的顺序。"""
    whens = [(expr == value, i) for i, value in enumerate(ordered)]
    return sa.case((expr.is_(None), None), *whens, else_=len(ordered))
