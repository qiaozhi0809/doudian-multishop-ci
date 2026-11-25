"""商品 / 库存接口的响应模型（只读聚合）。"""

from pydantic import BaseModel


class ProductDisplay(BaseModel):
    img: str | None = None
    product_url: str | None = None
    category_name: str | None = None
    quality_score: int | None = None
    sell_num_30d: int | None = None


class ProductRow(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    product_id: str
    name: str | None
    status: str | None
    tab: str | None
    price_lower_cents: int | None
    price_higher_cents: int | None
    stock_num: int | None
    sell_num: int | None
    synced_at: str
    display: ProductDisplay


class ProductPage(BaseModel):
    items: list[ProductRow]
    total: int
    page: int
    page_size: int


class ShopProductCounts(BaseModel):
    shop_id: int
    source: str
    counts: dict[str, int] | None = None
    error: str | None = None
    fetched_at: str | None = None


class ProductCountsResponse(BaseModel):
    shops: list[ShopProductCounts]


class ShopProductSync(BaseModel):
    shop_id: int
    fetched: int
    complete: bool
    error: str | None = None
    synced_at: str | None = None


class ProductSyncResponse(BaseModel):
    shops: list[ShopProductSync]


class GroupItem(BaseModel):
    group_id: str
    name: str | None = None


class ShopGroups(BaseModel):
    shop_id: int
    source: str
    items: list[GroupItem] | None = None
    error: str | None = None
    fetched_at: str | None = None


class ProductGroupsResponse(BaseModel):
    shops: list[ShopGroups]


class StockRow(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    product_id: str
    name: str | None = None
    total_stock_num: int | None
    spot_stock_num: int | None
    future_stock_num: int | None  # 未来库存与现货分开展示，禁止相加（附录 D.4）
    total_occupied_stock_num: int | None
    total_unoccupied_stock_num: int | None
    is_alarming: bool
    synced_at: str


class StockPage(BaseModel):
    items: list[StockRow]
    total: int
    page: int
    page_size: int


class StockSummary(BaseModel):
    total: int
    alarm_count: int
    sold_out_count: int


class ShopStockSync(BaseModel):
    shop_id: int
    fetched: int
    complete: bool
    alarm_count: int = 0
    sold_out_count: int = 0
    error: str | None = None
    synced_at: str | None = None


class StockSyncResponse(BaseModel):
    shops: list[ShopStockSync]


class WarehouseItem(BaseModel):
    warehouse_id: str
    name: str | None = None


class ShopWarehouses(BaseModel):
    shop_id: int
    source: str
    items: list[WarehouseItem] | None = None
    error: str | None = None
    fetched_at: str | None = None


class WarehousesResponse(BaseModel):
    shops: list[ShopWarehouses]

