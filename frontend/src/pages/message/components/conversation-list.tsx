import { MessageSquare } from "lucide-react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Checkbox } from "@/components/arc/checkbox/checkbox";
import { EmptyState } from "@/components/arc/empty-state/empty-state";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { ListPager } from "@/components/custom/list-pager/list-pager";
import type { MessagePageState } from "../hooks/use-message-page";
import { PAGE_SIZE, selectionKey } from "../logic/message-page";
import styles from "../message-page.module.css";
import { ConversationRow } from "./conversation-row";

/** 左栏：只看未读 → 会话列表 → 分页。 */
export function ConversationList({ page }: { page: MessagePageState }) {
  const data = page.list.data;
  const selected = page.selection && selectionKey(page.selection.shopId, page.selection.conversationId);
  return (
    <div className={styles.listColumn}>
      <div className={styles.listBox}>
        <div className={styles.listToolbar}>
          <Checkbox label="只看未读" checked={page.unreadOnly} onCheckedChange={(value) => page.setUnreadOnly(value === true)} />
        </div>
        <div className={styles.listScroll}>
          {page.list.isLoading && <Skeleton label="正在读取会话" lines={6} />}
          {page.list.isError && (
            <div className={styles.inset}>
              <Alert tone="danger" title="读取会话失败，请确认本地服务正常后重试" />
              <div>
                <Button variant="secondary" size="sm" onClick={() => void page.list.refetch()}>
                  重新读取
                </Button>
              </div>
            </div>
          )}
          {data && data.items.length === 0 && (
            <EmptyState icon={<MessageSquare size={24} strokeWidth={1.75} aria-hidden="true" />} title="暂无会话" />
          )}
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
