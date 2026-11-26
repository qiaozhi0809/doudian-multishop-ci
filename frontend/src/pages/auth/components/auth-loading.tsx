import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { SKELETON_LINES } from "@/lib/skeleton-lines";

export function AuthLoading() {
  return <Skeleton label="正在读取登录状态" lines={SKELETON_LINES.card} />;
}
