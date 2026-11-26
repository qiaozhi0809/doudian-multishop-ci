import { MessagePageView } from "./components/message-page-view";
import { useMessagePage } from "./hooks/use-message-page";
import { useThread } from "./hooks/use-thread";
import { selectedRow } from "./logic/message-page";

/** 客服消息页（只读）：只做装配。 */
export default function MessagePage() {
  const page = useMessagePage();
  const thread = useThread(page.selection, selectedRow(page.list.data?.items, page.selection));
  return <MessagePageView page={page} thread={thread} />;
}
