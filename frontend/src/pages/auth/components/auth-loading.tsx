import { Skeleton } from "@/components/arc/skeleton/skeleton";

export function AuthLoading() {
  return <Skeleton label="正在读取登录状态" lines={4} />;
}
