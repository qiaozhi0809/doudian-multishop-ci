import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { priceRange, productStateLabel, type ProductRow } from "../logic/catalog-page";
import styles from "../catalog-page.module.css";

const columns: DataColumn<ProductRow>[] = [
  { key: "shop_name", label: "店铺", sortable: false, width: 110 },
  {
    key: "name", label: "商品", sortable: false, width: 260,
    render: (_, row) => (
      <span className={styles.productCell}>
        <span className={styles.productName}>{row.name ?? "未命名商品"}</span>
        <span className={styles.muted}>{row.product_id}</span>
      </span>
    ),
  },
  {
    key: "tab", label: "状态", sortable: false, width: 100,
    render: (_, row) => productStateLabel(row),
  },
  {
    key: "price", label: "价格", sortable: false, numeric: true, width: 150,
    render: (_, row) => priceRange(row),
  },
  {
    key: "stock_num", label: "库存", sortable: false, numeric: true, width: 90,
    render: (v) => (v === null ? "暂无" : String(v)),
  },
  {
    key: "sell_num", label: "销量", sortable: false, numeric: true, width: 90,
    render: (v) => (v === null ? "暂无" : String(v)),
  },
  {
    key: "category", label: "类目", sortable: false, width: 140,
    render: (_, row) => row.display.category_name ?? "—",
  },
  {
    key: "sell_num_30d", label: "30 天销量", sortable: false, numeric: true, width: 100,
    render: (_, row) => (row.display.sell_num_30d === null ? "暂无" : String(row.display.sell_num_30d)),
  },
];

/** 快照列表由服务端分页（按销量倒序），客户端不排序。 */
export function ProductTable({ rows }: { rows: ProductRow[] }) {
  return (
    <div className={styles.tableWrap}>
      <SortableDataTable<ProductRow>
        rows={rows}
        columns={columns}
        rowKey={(row) => String(row.id)}
        caption="商品列表"
        emptyMessage="没有符合条件的商品；商品快照为空时先点「同步商品」"
      />
    </div>
  );
}
