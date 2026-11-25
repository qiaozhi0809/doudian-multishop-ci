import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import type { ShopRow } from "@/lib/use-shops";
import styles from "../shop-page.module.css";
import { ActionsCell, EgressCell, ExpiryCell, ReadyCell, StatusCell, type RowActions } from "./shop-cells";

interface ShopTableProps {
  shops: ShopRow[];
  pending: string[];
  waitingShopIds: number[];
  actionsFor: (row: ShopRow) => RowActions & { onResume: () => void };
}

/** Arc 表格的列默认可排序（sortable !== false），只有店铺名与到期时间有意义，其余列显式关闭。 */
export function ShopTable({ shops, pending, waitingShopIds, actionsFor }: ShopTableProps) {
  const columns: DataColumn<ShopRow>[] = [
    { key: "name", label: "店铺", sortable: true, width: 110, render: (v) => <span className={styles.shopName}>{String(v)}</span> },
    {
      key: "status",
      label: "状态",
      sortable: false,
      width: 100,
      render: (_, row) => <StatusCell row={row} waiting={waitingShopIds.includes(row.id)} onResume={actionsFor(row).onResume} />,
    },
    { key: "egress_status", label: "出口", sortable: false, width: 240, render: (_, row) => <EgressCell row={row} /> },
    { key: "expires_at", label: "到期", sortable: true, width: 90, render: (_, row) => <ExpiryCell row={row} /> },
    { key: "ready_for_label", label: "取号就绪", sortable: false, width: 80, render: (_, row) => <ReadyCell row={row} /> },
    {
      key: "actions",
      label: "操作",
      sortable: false,
      width: 130,
      render: (_, row) => (
        <ActionsCell row={row} actions={actionsFor(row)} pending={pending} waiting={waitingShopIds.includes(row.id)} />
      ),
    },
  ];
  return (
    <div className={styles.tableWrap}>
      <SortableDataTable<ShopRow>
        rows={shops}
        columns={columns}
        rowKey={(row) => String(row.id)}
        caption="店铺列表"
        emptyMessage="没有符合筛选的店铺"
      />
    </div>
  );
}
