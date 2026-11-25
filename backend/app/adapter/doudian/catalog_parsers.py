"""商品 / 库存接口响应 → DTO（docs/api/catalog.md 附录 D）。"""

from typing import Any

from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.parse_fields import (
    find_list,
    int_fields,
    list_with_total,
    opt_int,
    opt_str,
    require_data,
    require_str,
)
from app.domain.aggregate_models import GroupDTO, ProductDTO, StockDTO, StockSummary, WarehouseDTO


def _parse_product(p: dict) -> ProductDTO:
    return ProductDTO(
        product_id=require_str(p, "product_id", "商品"),
        name=opt_str(p.get("name")),
        status=opt_str(p.get("status")),
        tab=opt_str(p.get("tab")),
        price_lower_cents=opt_int(p.get("price_lower")),
        price_higher_cents=opt_int(p.get("price_higher")),
        stock_num=opt_int(p.get("stock_num")),
        sell_num=opt_int(p.get("sell_num")),
        raw=p,
    )


def parse_products(resp: dict) -> tuple[list[ProductDTO], int]:
    rows, total = list_with_total(resp)
    return [_parse_product(p) for p in rows], total


def parse_product_counts(resp: dict) -> dict[str, int]:
    """状态计数：onsale / audit / unpass / draft / forbidden / sell_out_new …（附录 D.1）。"""
    data = require_data(resp)
    if not isinstance(data, dict):
        raise ParseError("商品计数的 data 不是对象")
    return int_fields(data)


def parse_product_groups(resp: dict) -> list[GroupDTO]:
    rows = find_list(require_data(resp), ("list", "groups", "group_list", "items"))
    if rows is None:
        raise ParseError("商品分组缺少列表")
    out: list[GroupDTO] = []
    for g in rows:
        if not isinstance(g, dict):
            continue
        group_id = g.get("group_id", g.get("id"))
        if group_id in (None, ""):
            continue
        out.append(GroupDTO(
            group_id=str(group_id),
            name=opt_str(g.get("name") or g.get("group_name")),
            raw=g,
        ))
    return out


def _parse_stock(s: dict) -> StockDTO:
    return StockDTO(
        product_id=require_str(s, "product_id", "库存"),
        total_stock_num=opt_int(s.get("total_stock_num")),
        spot_stock_num=opt_int(s.get("spot_stock_num")),
        # 现货与未来库存分开展示，禁止相加（附录 D.4 第 2 条）
        future_stock_num=opt_int(s.get("future_stock_num")),
        total_occupied_stock_num=opt_int(s.get("total_occupied_stock_num")),
        total_unoccupied_stock_num=opt_int(s.get("total_unoccupied_stock_num")),
        is_alarming=bool(s.get("is_alarming")),
        raw=s,
    )


_SUMMARY_KEYS = (
    "stock_alarm_cnt", "sold_out_cnt", "stock_subscribe_cnt", "activity_stock_occupy_cnt",
    "channel_stock_occupy_cnt", "advised_increase_spot_cnt",
)


def parse_stock(resp: dict) -> tuple[list[StockDTO], StockSummary]:
    """库存列表 + 顶层统计（附录 D.2）。"""
    data = require_data(resp)
    if not isinstance(data, dict):
        raise ParseError("库存列表的 data 不是对象")
    rows = find_list(data)
    if rows is None:
        raise ParseError("库存列表缺少列表字段")
    items = [_parse_stock(s) for s in rows if isinstance(s, dict)]
    stats = int_fields(data)
    total = opt_int(data.get("total"))
    return items, StockSummary(
        total=len(items) if total is None else total,
        **{k: stats.get(k, 0) for k in _SUMMARY_KEYS},
    )


def parse_warehouses(resp: dict) -> list[WarehouseDTO]:
    rows = find_list(require_data(resp), ("warehouse_list", "list", "warehouses", "items"))
    if rows is None:
        raise ParseError("仓库列表缺少列表字段")
    out: list[WarehouseDTO] = []
    for w in rows:
        if not isinstance(w, dict):
            continue
        warehouse_id = w.get("warehouse_id", w.get("id"))
        if warehouse_id in (None, ""):
            continue
        out.append(WarehouseDTO(
            warehouse_id=str(warehouse_id),
            name=opt_str(w.get("name") or w.get("warehouse_name")),
            raw=w,
        ))
    return out


def product_display(raw: dict) -> dict[str, Any]:
    """商品条目 192 字段中的展示用选摘（只读展示，不落库）。"""
    return {
        "img": opt_str(raw.get("img")),
        "product_url": opt_str(raw.get("product_url")),
        "category_name": opt_str(raw.get("category_name")),
        "quality_score": opt_int(raw.get("quality_score")),
        "sell_num_30d": opt_int(raw.get("sell_num_30d")),
    }
