"""商品状态（附录 D.1）：列表条目的 `tab` 与计数接口的六个口径对应，界面文案、排序、快捷筛选共用。

平台条目里的 `tab` 形态不统一：接口样本是英文代码 `onSale`（计数键为 `onsale`，按小写比较），
实际同步到的是中文文案（「售卖中」「已下架」）；
同一口径还有新旧两个值（如 `unpass` / `unpass_new`）。
这些都归到同一项；没对上的值排在已知状态之后，也不会被任何快捷筛选选中。
"""

# 顺序即界面展示顺序（计数卡从左到右），也是「状态」列的排序顺序
PRODUCT_STATES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("onsale", "在售", ("onsale", "售卖中", "在售")),
    ("draft", "草稿", ("draft", "草稿", "草稿箱")),
    ("audit", "审核中", ("audit", "审核中", "待审核")),
    ("sell_out_new", "售罄", ("sell_out_new", "sell_out", "soldout", "已售罄", "售罄")),
    ("unpass", "未通过", ("unpass", "unpass_new", "审核未通过", "审核驳回", "未通过")),
    ("forbidden", "禁售 / 下架", ("forbidden", "已下架", "下架", "禁售", "封禁中", "已封禁")),
)
PRODUCT_STATE_KEYS: tuple[str, ...] = tuple(key for key, _, _ in PRODUCT_STATES)


def tab_aliases(state: str) -> tuple[str, ...]:
    return next(aliases for key, _, aliases in PRODUCT_STATES if key == state)
