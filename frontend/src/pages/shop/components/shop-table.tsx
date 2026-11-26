import { DataTable, type TableColumn } from "@/components/custom/data-table/data-table";
import { shopStatusSortValue } from "../logic/shop-status";
import type { ShopRow } from "@/lib/use-shops";
import styles from "../shop-page.module.css";
import { ActionsCell, EgressCell, ExpiryCell, NameCell, ReadyCell, StatusCell, TextCell, type RowActions } from "./shop-cells";

interface ShopTableProps {
  shops: ShopRow[];
  pending: string[];
  waitingShopIds: number[];
  actionsFor: (row: ShopRow) => RowActions;
  /** 通知跳转来的店（`?shop=<id>`）：高亮并滚动到该行 */
  highlightId: number | null;
  /** 该店这次高亮是否还没滚动过（每个 ?shop= 只滚一次） */
  claimScroll: (id: number) => boolean;
}

/** 店铺列表（一次全量返回，前端排序）：序号由 DataTable 按显示顺序编号；店铺名、平台店铺名、状态、到期可排序。 */
export function ShopTable({ shops, pending, waitingShopIds, actionsFor, highlightId, claimScroll }: ShopTableProps) {
  // 列宽之和（含序号 56）不超过 1366 宽下的内容区，避免横向滚动时固定的操作列盖住「取号就绪」
  const columns: TableColumn<ShopRow>[] = [
    { key: "name", label: "店铺", sortable: true, width: 84, render: (v, row) => <NameCell name={String(v)} highlighted={row.id === highlightId} onMark={() => claimScroll(row.id)} /> },
    { key: "shop_name", label: "平台店铺名", sortable: true, width: 112, render: (v) => <TextCell value={v as string | null} /> },
    { key: "admin_name", label: "负责人", width: 70, render: (v) => <TextCell value={v as string | null} /> },
    {
      key: "status",
      label: "状态",
      sortable: true,
      width: 156,
      sortValue: (row) => shopStatusSortValue(row),
      render: (_, row) => <StatusCell row={row} waiting={waitingShopIds.includes(row.id)} />,
    },
    { key: "egress_status", label: "出口", width: 224, render: (_, row) => <EgressCell row={row} /> },
    { key: "expires_at", label: "到期", sortable: true, width: 78, render: (_, row) => <ExpiryCell row={row} /> },
    { key: "ready_for_label", label: "取号就绪", width: 84, render: (_, row) => <ReadyCell row={row} /> },
    {
      key: "actions",
      label: "操作",
      width: 146,
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
