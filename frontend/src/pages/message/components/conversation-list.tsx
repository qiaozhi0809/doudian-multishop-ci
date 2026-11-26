import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { ListPager } from "@/components/custom/list-pager/list-pager";
import { LoadError } from "@/components/custom/load-error/load-error";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import type { MessagePageState } from "../hooks/use-message-page";
import { PAGE_SIZE, selectionKey } from "../logic/message-page";
import styles from "../message-page.module.css";
import { ConversationRow } from "./conversation-row";

/** 左栏：会话列表 → 分页（未读等筛选用上方计数卡）。 */
export function ConversationList({ page }: { page: MessagePageState }) {
  const data = page.list.data;
  const selected = page.selection && selectionKey(page.selection.shopId, page.selection.conversationId);
  return (
    <div className={styles.listColumn}>
      <div className={styles.listBox}>
        <div className={styles.listScroll}>
          {page.list.isLoading && <Skeleton label="正在读取会话" lines={SKELETON_LINES.list} />}
          {page.list.isError && (
            <LoadError
              size="sm"
              className={styles.inset}
              title="读取会话失败，请确认本地服务正常后重试"
              onRetry={() => void page.list.refetch()}
            />
          )}
          {data && data.items.length === 0 && <p className="panel-empty">暂无会话</p>}
          {data && data.items.length > 0 && (
            <ul className={styles.rows} aria-label="会话列表">
              {data.items.map((item) => {
                const key = selectionKey(item.shop_id, item.conversation_id);
                return (
                  <li key={key}>
                    <ConversationRow
                      conversation={item}
                      now={page.now}
                      selected={key === selected}
                      onSelect={() => page.select({ shopId: item.shop_id, conversationId: item.conversation_id })}
                    />
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
      {data && (
        <ListPager total={data.total} page={page.page} pageSize={PAGE_SIZE} onPageChange={page.setPage} label="会话分页" noun="个会话" pageUnit="个" />
      )}
    </div>
  );
}
