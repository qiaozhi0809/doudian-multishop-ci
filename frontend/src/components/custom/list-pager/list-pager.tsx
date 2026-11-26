import { Pagination } from "@/components/arc/pagination/pagination";
import styles from "./list-pager.module.css";

interface ListPagerProps {
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  /** 分页导航的无障碍名称，如「订单分页」。 */
  label: string;
  /** 合计的量词与名词，如「单」「个商品」「条异常」。 */
  noun: string;
  /** 每页的量词，默认同 noun（「个商品」配「个」）。 */
  pageUnit?: string;
}

/** 分页列表的脚注（全站共用）：「共 N 单，每页 50 单」+ 翻页。没有数据整条不显示，只有一页时不显示翻页。 */
export function ListPager({ total, page, pageSize, onPageChange, label, noun, pageUnit = noun }: ListPagerProps) {
  if (total <= 0) return null;
  const pageCount = Math.ceil(total / pageSize);
  return (
    <div className={styles.pager}>
      <span>
        共 {total} {noun}，每页 {pageSize} {pageUnit}
      </span>
      {pageCount > 1 && <Pagination page={page} pageCount={pageCount} onPageChange={onPageChange} label={label} />}
    </div>
  );
}
