from app.domain.models import OrderDTO, OrderItemDTO


def make_item(sku_order_id: str = "so1", **kw) -> OrderItemDTO:
    base = dict(
        sku_order_id=sku_order_id, product_id="p1", product_name="商品", sku_spec="规格",
        quantity=1, price_cents=1000, sku_id="s1",
    )
    return OrderItemDTO(**{**base, **kw})


def make_order(order_no: str, **kw) -> OrderDTO:
    base = dict(
        order_no=order_no, platform_order_id="pid-" + order_no, combine_id=None,
        platform_status=2, amount_cents=1000, create_time="2026-11-24T10:00:00Z",
        pay_time="2026-11-24T10:01:00Z", exp_ship_time="2026-11-26T10:00:00Z",
        buyer_nick="买家", receiver_name="张*", receiver_phone="138****0000",
        receiver_region="省 市 区", items=(make_item(),), raw={"k": "v"},
    )
    return OrderDTO(**{**base, **kw})
