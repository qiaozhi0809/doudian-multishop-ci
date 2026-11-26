import { DataTable, type TableColumn } from "@/components/custom/data-table/data-table";
import { shopStatusSortValue } from "../logic/shop-status";
import { orEmpty } from "@/lib/empty-text";
import type { ShopRow } from "@/lib/use-shops";
import styles from "../shop-page.module.css";
import { ActionsCell, EgressCell, ExpiryCell, ReadyCell, StatusCell, type RowActions } from "./shop-cells";

interface ShopTableProps {
  shops: ShopRow[];
  pending: string[];
  waitingShopIds: number[];
  actionsFor: (row: ShopRow) => RowActions & { onResume: () => void };
}

/** 店铺列表（一次全量返回，前端排序）：序号由 DataTable 按显示顺序编号；店铺名、平台店铺名、状态、到期可排序。 */
export function ShopTable({ shops, pending, waitingShopIds, actionsFor }: ShopTableProps) {
  const columns: TableColumn<ShopRow>[] = [
    { key: "name", label: "店铺", sortable: true, width: 110, render: (v) => <span className={styles.shopName}>{String(v)}</span> },
    {
      key: "shop_name",
      label: "平台店铺名",
      sortable: true,
      width: 150,
      render: (v) => orEmpty(v as string | null),
    },
    { key: "admin_name", label: "负责人", width: 100, render: (v) => orEmpty(v as string | null) },
    {
      key: "status",
      label: "状态",
      sortable: true,
      width: 100,
      sortValue: (row) => shopStatusSortValue(row),
      render: (_, row) => <StatusCell row={row} waiting={waitingShopIds.includes(row.id)} onResume={actionsFor(row).onResume} />,
    },
    { key: "egress_status", label: "出口", width: 240, render: (_, row) => <EgressCell row={row} /> },
    { key: "expires_at", label: "到期", sortable: true, width: 90, render: (_, row) => <ExpiryCell row={row} /> },
    { key: "ready_for_label", label: "取号就绪", width: 80, render: (_, row) => <ReadyCell row={row} /> },
    {
      key: "actions",
      label: "操作",
      width: 130,
      render: (_, row) => (
        <ActionsCell row={row} actions={actionsFor(row)} pending={pending} waiting={waitingShopIds.includes(row.id)} />
      ),
    },
  ];
  return (
    <DataTable<ShopRow>
      className={styles.tableWrap}
      rows={shops}
      columns={columns}
      rowKey={(row) => String(row.id)}
      caption="店铺列表"
      emptyMessage="没有符合条件的店铺"
    />
  );
}
